"""
计费与套餐 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

from utils.auth import get_current_user
from services.billing import billing_service
from config import plan_config


router = APIRouter(prefix="/v1/billing", tags=["计费"])


# ==================== 请求/响应模型 ====================

class BalanceResponse(BaseModel):
    """余额响应"""
    user_id: str
    balance: float
    plan: str
    plan_name: str
    daily_requests_used: int
    daily_requests_limit: int


class UsageStatsResponse(BaseModel):
    """用量统计响应"""
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_spent: float
    endpoint_stats: Dict[str, dict]
    model_stats: Dict[str, dict]


class SubscriptionRequest(BaseModel):
    """订阅请求"""
    plan: str = Field(..., description="套餐: free, basic, pro, enterprise")


class SubscriptionResponse(BaseModel):
    """订阅响应"""
    success: bool
    plan: str
    plan_name: str
    message: str


class RechargeRequest(BaseModel):
    """充值请求"""
    amount: float = Field(..., gt=0, description="充值金额（元）")


class RechargeResponse(BaseModel):
    """充值响应"""
    success: bool
    amount: float
    new_balance: float
    transaction_id: str


class PlanInfo(BaseModel):
    """套餐信息"""
    plan: str
    name: str
    price: float
    period: str
    requests_limit: int
    features: List[str]
    models: List[str]


# ==================== 路由实现 ====================

@router.get("/balance", response_model=BalanceResponse)
async def get_balance(user: dict = Depends(get_current_user)):
    """获取当前余额和用量信息"""
    plan = user.get("plan", "free")
    plan_info = plan_config.PLANS.get(plan, {})
    
    return BalanceResponse(
        user_id=user["user_id"],
        balance=user.get("balance", 0),
        plan=plan,
        plan_name=plan_info.get("name", "未知"),
        daily_requests_used=user.get("daily_requests", 0),
        daily_requests_limit=plan_info.get("requests_limit", 100)
    )


@router.get("/usage", response_model=UsageStatsResponse)
async def get_usage_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """获取用量统计"""
    usage_manager = __import__('models.usage', fromlist=['usage_manager']).usage_manager
    
    stats = usage_manager.get_user_stats(user["user_id"])
    
    return UsageStatsResponse(
        total_requests=stats.get("total_requests", 0),
        total_input_tokens=stats.get("total_input_tokens", 0),
        total_output_tokens=stats.get("total_output_tokens", 0),
        total_tokens=stats.get("total_tokens", 0),
        total_spent=stats.get("total_revenue", 0),
        endpoint_stats=stats.get("endpoint_stats", {}),
        model_stats=stats.get("model_stats", {})
    )


@router.get("/usage/history")
async def get_usage_history(
    limit: int = 100,
    user: dict = Depends(get_current_user)
):
    """获取用量历史记录"""
    usage_manager = __import__('models.usage', fromlist=['usage_manager']).usage_manager
    
    records = usage_manager.get_user_usage(user["user_id"], limit=limit)
    
    return {
        "records": [
            {
                "usage_id": r.usage_id,
                "endpoint": r.endpoint,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "revenue": r.revenue,
                "created_at": r.created_at
            }
            for r in records
        ]
    }


@router.get("/plans", response_model=List[PlanInfo])
async def list_plans():
    """列出所有可用套餐"""
    plans = []
    for plan_id, plan_info in plan_config.PLANS.items():
        plans.append(PlanInfo(
            plan=plan_id,
            name=plan_info.get("name", "未知"),
            price=plan_info.get("price", 0),
            period=plan_info.get("period", "monthly"),
            requests_limit=plan_info.get("requests_limit", 0),
            features=plan_info.get("features", []),
            models=plan_info.get("models", []) if plan_info.get("models") != "all" else ["all"]
        ))
    return plans


@router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe_plan(
    request: SubscriptionRequest,
    user: dict = Depends(get_current_user)
):
    """订阅套餐"""
    # 验证套餐存在
    if request.plan not in plan_config.PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不存在的套餐: {request.plan}"
        )
    
    plan_info = plan_config.PLANS[request.plan]
    price = plan_info.get("price", 0)
    
    # 免费套餐直接切换
    if price == 0:
        user_manager = __import__('models.user', fromlist=['user_manager']).user_manager
        user_manager.update_plan(user["user_id"], request.plan)
        
        return SubscriptionResponse(
            success=True,
            plan=request.plan,
            plan_name=plan_info.get("name"),
            message="已切换到免费套餐"
        )
    
    # 付费套餐需要检查余额
    if not billing_service.check_balance(user, price):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"余额不足，当前余额: {user.get('balance', 0):.2f} 元，套餐价格: {price:.2f} 元"
        )
    
    # 扣费并切换套餐
    user_manager = __import__('models.user', fromlist=['user_manager']).user_manager
    
    if billing_service.charge_user(user["user_id"], price, f"订阅{plan_info.get('name')}"):
        user_manager.update_plan(user["user_id"], request.plan)
        
        return SubscriptionResponse(
            success=True,
            plan=request.plan,
            plan_name=plan_info.get("name"),
            message=f"订阅成功，已扣除 {price:.2f} 元"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="订阅失败，请稍后重试"
        )


@router.post("/recharge", response_model=RechargeResponse)
async def recharge(
    request: RechargeRequest,
    user: dict = Depends(get_current_user)
):
    """
    余额充值
    
    注意：实际生产环境中需要接入支付渠道（支付宝、微信等）
    这里仅作为演示，实际不会真正到账
    """
    if request.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="充值金额必须大于 0"
        )
    
    if request.amount > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="单次充值金额不能超过 10000 元"
        )
    
    user_manager = __import__('models.user', fromlist=['user_manager']).user_manager
    updated_user = user_manager.add_balance(user["user_id"], request.amount)
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="充值失败，请稍后重试"
        )
    
    import secrets
    return RechargeResponse(
        success=True,
        amount=request.amount,
        new_balance=updated_user.balance,
        transaction_id=f"recharge_{secrets.token_hex(8)}"
    )


@router.get("/pricing")
async def get_pricing_info():
    """获取详细定价信息"""
    return {
        "subscription_plans": {
            plan_id: {
                "name": info.get("name"),
                "price": info.get("price"),
                "period": info.get("period"),
                "requests_limit": info.get("requests_limit"),
                "features": info.get("features")
            }
            for plan_id, info in plan_config.PLANS.items()
        },
        "token_pricing": {
            "currency": "CNY",
            "rate": "基于模型成本 × 1.5 加价倍率",
            "models": {
                "gpt-4o-mini": {"input": 1.08, "output": 4.32},  # ¥/1M tokens
                "gpt-4o": {"input": 18.0, "output": 72.0},
                "claude-3-5-sonnet": {"input": 21.6, "output": 108.0},
                "deepseek-chat": {"input": 1.0, "output": 2.0}
            }
        },
        "vertical_api_pricing": billing_service.VERTICAL_API_PRICES
    }
