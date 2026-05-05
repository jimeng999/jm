"""
通用对话 API 路由 (BYOK 版本)
支持 Bring Your Own Key 模式
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from utils.auth import get_current_user
from utils.logger import logger
from utils.encryption import key_encryptor
from utils.simple_store import get_user_byok_key, get_free_trial_count, increment_free_trial
from services.model_router import model_router
from services.provider.base import Message
from services.provider.openai import OpenAIProvider
from services.provider.anthropic import AnthropicProvider
from services.provider.deepseek import DeepSeekProvider
from services.provider.gemini import GeminiProvider
from services.billing import billing_service
from config import settings, plan_config


router = APIRouter(prefix="/v1/chat", tags=["对话"])


# ==================== 请求/响应模型 ====================

class ChatMessage(BaseModel):
    """消息模型"""
    role: str = Field(..., description="角色: system, user, assistant")
    content: str = Field(..., description="消息内容")


class ChatCompletionRequest(BaseModel):
    """聊天补全请求"""
    model: str = Field(default="auto", description="模型: auto, gpt-4o-mini, gpt-4o, deepseek-chat 等")
    messages: List[ChatMessage] = Field(..., description="消息列表")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=4096, ge=1, le=128000, description="最大生成 token 数")
    stream: bool = Field(default=False, description="是否流式输出")
    top_p: float = Field(default=1.0, ge=0, le=1, description="top_p 参数")
    frequency_penalty: float = Field(default=0.0, ge=-2, le=2, description="频率惩罚")
    presence_penalty: float = Field(default=0.0, ge=-2, le=2, description="存在惩罚")


class UsageInfo(BaseModel):
    """用量信息"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatChoice(BaseModel):
    """聊天选项"""
    index: int
    message: Dict[str, str]
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    """聊天补全响应"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: UsageInfo


# ==================== BYOK Key 获取 ====================

def get_byok_key_for_provider(user_id: str, provider: str) -> Optional[str]:
    """获取用户的 BYOK Key（解密后）"""
    encrypted_key = get_user_byok_key(user_id, provider)
    if encrypted_key:
        return key_encryptor.decrypt(encrypted_key)
    return None


def get_effective_api_key(user_id: str, provider: str) -> tuple:
    """
    获取有效的 API Key
    
    返回: (api_key, is_byok, key_source)
    - is_byok: 是否使用用户的 BYOK Key
    - key_source: 'user_byok' | 'platform' | 'deepseek_trial' | 'none'
    """
    # 1. 优先使用用户的 BYOK Key
    byok_key = get_byok_key_for_provider(user_id, provider)
    if byok_key:
        return byok_key, True, "user_byok"
    
    # 2. 检查平台是否配置了该 Provider 的 Key
    platform_key = None
    if provider == "openai" and settings.openai_api_key:
        platform_key = settings.openai_api_key
    elif provider == "anthropic" and settings.anthropic_api_key:
        platform_key = settings.anthropic_api_key
    elif provider == "deepseek" and settings.deepseek_api_key:
        platform_key = settings.deepseek_api_key
    elif provider == "gemini" and settings.gemini_api_key:
        platform_key = settings.gemini_api_key
    
    if platform_key:
        return platform_key, False, "platform"
    
    # 3. 如果请求的是 DeepSeek 模型，尝试免费体验
    return None, False, "none"


# ==================== 路由实现 ====================

@router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    user: dict = Depends(get_current_user)
):
    """
    通用对话补全接口 (BYOK 模式)
    
    优先级:
    1. 用户的 BYOK Key - 零差价，直接调用
    2. 平台 Key - 加价 30%
    3. DeepSeek 免费体验 - 每日 5 次
    """
    try:
        # 检查每日限制
        limit_check = billing_service.check_daily_limit(user)
        if not limit_check["allowed"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"每日请求次数已达上限 ({limit_check['message']})"
            )
        
        # 增加请求计数
        user_manager = __import__('models.user', fromlist=['user_manager']).user_manager
        user_manager.increment_request_count(user["user_id"])
        
        # 处理自动模型选择
        if request.model == "auto":
            # 检测任务类型
            messages_dict = [m.model_dump() for m in request.messages]
            task_type = model_router.detect_task_type(messages_dict)
            
            # 智能选模型
            selected = model_router.select_model(
                task_type=task_type,
                user_plan=user.get("plan", "free")
            )
            provider_name = selected["provider"]
            model = selected["model"]
        else:
            model = request.model
            provider_name = model_router._find_model_provider(model)
        
        # 获取有效的 API Key
        api_key, is_byok, key_source = get_effective_api_key(user["user_id"], provider_name)
        
        # 处理无 Key 的情况
        if not api_key:
            # 尝试 DeepSeek 免费体验
            if provider_name in ["deepseek"]:
                used_count = get_free_trial_count(user["user_id"])
                if used_count < 5:
                    # 使用平台 DeepSeek Key 进行免费体验
                    if settings.deepseek_api_key:
                        api_key = settings.deepseek_api_key
                        is_byok = False
                        key_source = "deepseek_trial"
                        increment_free_trial(user["user_id"])
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="平台暂无可用 API Key，请设置您的 BYOK Key 或稍后重试"
                        )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="今日免费体验次数已用完（每日5次），请设置您的 BYOK Key"
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"请先设置您的 {provider_name} API Key，或使用 DeepSeek 模型（每日5次免费体验）"
                )
        
        logger.info(f"User {user['user_id']} - Model: {model} (Provider: {provider_name}, Source: {key_source}, BYOK: {is_byok})")
        
        # 转换消息格式
        messages = [
            Message(role=m.role, content=m.content) 
            for m in request.messages
        ]
        
        # 创建 Provider 实例
        provider = _create_provider(provider_name, api_key)
        
        # 记录开始时间
        import time
        start_time = time.time()
        
        # 发送请求
        response = await provider.chat_completion(
            model=model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty
        )
        
        # 计算成本和扣费
        usage = response.usage
        billing_result = billing_service.record_api_usage(
            user_id=user["user_id"],
            endpoint="/v1/chat/completions",
            model=model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            is_byok=is_byok,
            key_source=key_source
        )
        
        elapsed = time.time() - start_time
        cost_info = f"Cost: {billing_result.get('price', 0):.4f} CNY"
        if key_source == "deepseek_trial":
            cost_info = "Trial: FREE (今日已用 " + str(get_free_trial_count(user["user_id"])) + " 次)"
        elif is_byok:
            cost_info = "BYOK: 0 (用户自有Key)"
        
        logger.info(f"Request completed in {elapsed:.2f}s - {cost_info}")
        
        # 构建响应
        return ChatCompletionResponse(
            id=response.id,
            created=response.created,
            model=response.model,
            choices=[
                ChatChoice(
                    index=c.get("index", 0),
                    message=c.get("message", {}),
                    finish_reason=c.get("finish_reason", "stop")
                )
                for c in response.choices
            ],
            usage=UsageInfo(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0)
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"请求处理失败: {str(e)}"
        )


@router.get("/models")
async def list_models(user: dict = Depends(get_current_user)):
    """列出可用模型"""
    user_plan = user.get("plan", "free")
    plan_info = plan_config.PLANS.get(user_plan, {})
    available_models = plan_info.get("models", [])
    
    # 检查用户是否有 BYOK Keys
    user_id = user["user_id"]
    has_byok = bool(get_user_byok_key(user_id, "openai") or 
                    get_user_byok_key(user_id, "anthropic") or 
                    get_user_byok_key(user_id, "deepseek") or 
                    get_user_byok_key(user_id, "gemini"))
    
    models = []
    if available_models == "all" or "all" in available_models:
        # 返回所有模型
        for provider_name, provider_info in model_router.providers.items():
            for model_name, model_info in provider_info.get("models", {}).items():
                models.append({
                    "id": model_name,
                    "object": "model",
                    "provider": provider_name,
                    "provider_name": provider_info.get("name"),
                    "owned_by": provider_name,
                    "permission": [],
                    **model_info
                })
    else:
        # 只返回用户可用的模型
        for model_name in available_models:
            model_info = model_router.get_model_info(model_name)
            if model_info:
                models.append({
                    "id": model_name,
                    "object": "model",
                    "provider": model_info.get("provider"),
                    "provider_name": model_info.get("provider_name"),
                    "owned_by": model_info.get("provider"),
                    "permission": [],
                    "input_cost": model_info.get("input_cost"),
                    "output_cost": model_info.get("output_cost")
                })
    
    return {
        "object": "list",
        "data": models,
        "user_byok": {
            "enabled": has_byok,
            "free_trial_remaining": max(0, 5 - get_free_trial_count(user_id))
        }
    }


def _create_provider(provider_name: str, api_key: str):
    """创建 Provider 实例"""
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "deepseek": DeepSeekProvider,
        "gemini": GeminiProvider
    }
    provider_class = providers.get(provider_name, OpenAIProvider)
    return provider_class(api_key=api_key)
