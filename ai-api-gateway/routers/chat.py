"""
通用对话 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from utils.auth import get_current_user
from utils.logger import logger
from services.model_router import model_router
from services.provider.base import Message
from services.provider.openai import openai_provider
from services.provider.anthropic import anthropic_provider
from services.provider.deepseek import deepseek_provider
from services.provider.gemini import gemini_provider
from services.billing import billing_service
from config import plan_config


router = APIRouter(prefix="/v1/chat", tags=["对话"])


# ==================== 请求/响应模型 ====================

class ChatMessage(BaseModel):
    """消息模型"""
    role: str = Field(..., description="角色: system, user, assistant")
    content: str = Field(..., description="消息内容")


class ChatCompletionRequest(BaseModel):
    """聊天补全请求"""
    model: str = Field(default="auto", description="模型: auto, gpt-4o-mini, gpt-4o 等")
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


# ==================== 路由实现 ====================

@router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    user: dict = Depends(get_current_user)
):
    """
    通用对话补全接口
    
    遵循 OpenAI 兼容格式，支持自动模型路由。
    """
    try:
        # 检查每日限制
        limit_check = billing_service.check_daily_limit(user)
        if not limit_check["allowed"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOGETHER_RETRY_AFTER,
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
        
        logger.info(f"User {user['user_id']} - Model: {model} (Provider: {provider_name})")
        
        # 转换消息格式
        messages = [
            Message(role=m.role, content=m.content) 
            for m in request.messages
        ]
        
        # 调用对应供应商
        provider = _get_provider(provider_name)
        
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
            output_tokens=usage.get("completion_tokens", 0)
        )
        
        elapsed = time.time() - start_time
        logger.info(f"Request completed in {elapsed:.2f}s - Cost: {billing_result.get('price', 0):.4f} CNY")
        
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
        "data": models
    }


def _get_provider(provider_name: str):
    """获取供应商实例"""
    providers = {
        "openai": openai_provider,
        "anthropic": anthropic_provider,
        "deepseek": deepseek_provider,
        "gemini": gemini_provider
    }
    return providers.get(provider_name, openai_provider)
