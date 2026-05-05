"""
内容创作 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List

from utils.auth import get_current_user
from utils.logger import logger
from services.prompt_templates import prompt_templates
from services.model_router import model_router
from services.provider.base import Message
from services.provider.openai import openai_provider
from services.billing import billing_service
from config import plan_config


router = APIRouter(prefix="/v1/content", tags=["内容创作"])


# ==================== 请求/响应模型 ====================

class ContentWriteRequest(BaseModel):
    """内容创作请求"""
    type: str = Field(default="article", description="内容类型: article, seo, marketing, social")
    topic: str = Field(..., description="主题/话题")
    length: str = Field(default="medium", description="长度: short, medium, long, ultra")
    style: str = Field(default="professional", description="风格: professional, casual, friendly, formal")
    keywords: Optional[List[str]] = Field(default=None, description="SEO 关键词（用于 SEO 类型）")
    audience: Optional[str] = Field(default=None, description="目标受众（用于营销类型）")
    extra: Optional[dict] = Field(default=None, description="额外参数")


class ContentResponse(BaseModel):
    """内容创作响应"""
    content_id: str
    content: str
    word_count: int
    model: str
    price: float
    remaining_balance: float


# ==================== 路由实现 ====================

@router.post("/write", response_model=ContentResponse)
async def write_content(
    request: ContentWriteRequest,
    user: dict = Depends(get_current_user)
):
    """
    AI 内容创作接口
    
    按结果收费，支持多种内容类型：
    - article: 文章（博客、新闻、指南等）
    - seo: SEO 优化文章
    - marketing: 营销文案
    - social: 社交媒体内容
    """
    try:
        # 检查套餐是否包含此功能
        plan_info = plan_config.PLANS.get(user.get("plan", "free"), {})
        features = plan_info.get("features", [])
        
        if "content_write" not in features and "all" not in features:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前套餐不支持内容创作功能，请升级到专业版或企业版"
            )
        
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
        
        # 计算价格
        price = billing_service.get_vertical_api_price("content/write", request.length)
        
        # 检查余额
        if not billing_service.check_balance(user, price):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"余额不足，当前余额: {user.get('balance', 0):.2f} 元，需要: {price:.2f} 元"
            )
        
        # 生成提示词
        system_prompt = prompt_templates.CONTENT_WRITE_SYSTEM
        
        user_prompt = prompt_templates.get_content_prompt(
            content_type=request.type,
            topic=request.topic,
            length=request.length,
            style=request.style,
            keywords=request.keywords or [],
            audience=request.audience or ""
        )
        
        # 构造消息
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt)
        ]
        
        # 智能选择模型（优先选择性价比高的）
        # 内容创作不需要最强的模型
        selected = model_router.select_model(
            task_type="creative",
            user_plan=user.get("plan", "free")
        )
        model = selected["model"]
        
        logger.info(f"Content write - User: {user['user_id']}, Type: {request.type}, Model: {model}")
        
        # 调用模型
        response = await openai_provider.chat_completion(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=_get_max_tokens(request.length)
        )
        
        # 提取内容
        content = response.choices[0].get("message", {}).get("content", "")
        word_count = len(content)
        
        # 扣费
        user_manager.deduct_balance(user["user_id"], price)
        
        # 记录用量
        usage_manager = __import__('models.usage', fromlist=['usage_manager']).usage_manager
        usage_manager.record_usage(
            user_id=user["user_id"],
            endpoint="/v1/content/write",
            model=model,
            input_tokens=response.usage.get("prompt_tokens", 0),
            output_tokens=response.usage.get("completion_tokens", 0),
            cost=0,
            revenue=price,
            metadata={"content_type": request.type, "word_count": word_count}
        )
        
        # 获取更新后的余额
        updated_user = user_manager.get_user(user["user_id"])
        
        import secrets
        return ContentResponse(
            content_id=f"content_{secrets.token_hex(8)}",
            content=content,
            word_count=word_count,
            model=model,
            price=price,
            remaining_balance=updated_user.balance if updated_user else 0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Content write error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内容创作失败: {str(e)}"
        )


@router.get("/types")
async def list_content_types(user: dict = Depends(get_current_user)):
    """列出支持的内容类型"""
    return {
        "types": [
            {
                "id": "article",
                "name": "文章",
                "description": "博客文章、新闻、指南等",
                "lengths": ["short", "medium", "long", "ultra"]
            },
            {
                "id": "seo",
                "name": "SEO文章",
                "description": "搜索引擎优化的文章",
                "lengths": ["medium", "long"]
            },
            {
                "id": "marketing",
                "name": "营销文案",
                "description": "产品介绍、广告语等",
                "lengths": ["short", "medium"]
            },
            {
                "id": "social",
                "name": "社交媒体",
                "description": "微博、朋友圈、小红书等",
                "lengths": ["short", "medium"]
            }
        ],
        "pricing": {
            "short": 2.0,
            "medium": 5.0,
            "long": 10.0,
            "ultra": 20.0
        }
    }


def _get_max_tokens(length: str) -> int:
    """根据长度获取最大 token 数"""
    mapping = {
        "short": 2000,
        "medium": 4000,
        "long": 8000,
        "ultra": 16000
    }
    return mapping.get(length, 4000)
