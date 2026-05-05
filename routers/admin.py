"""
管理后台 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

from utils.auth import verify_admin
from utils.logger import logger
from models.user import user_manager
from models.usage import usage_manager


router = APIRouter(prefix="/v1/admin", tags=["管理后台"])


# ==================== 请求/响应模型 ====================

class AdminAuth(BaseModel):
    """管理员认证"""
    admin_key: str


class UserInfo(BaseModel):
    """用户信息"""
    user_id: str
    email: str
    plan: str
    balance: float
    is_active: bool
    created_at: str
    total_requests: int
    daily_requests: int


class AdminStats(BaseModel):
    """管理统计"""
    total_users: int
    active_users: int
    total_requests: int
    total_revenue: float
    total_cost: float
    profit: float
    profit_margin: float


class DailyStat(BaseModel):
    """每日统计"""
    date: str
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    total_revenue: float
    profit: float


# ==================== 认证依赖 ====================

async def verify_admin_key(x_admin_key: str = Header(..., alias="X-Admin-Key")):
    """验证管理员密钥"""
    if not verify_admin(x_admin_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的管理员密钥"
        )
    return True


# ==================== 路由实现 ====================

@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(_: bool = Depends(verify_admin_key)):
    """获取全局统计"""
    user_stats = user_manager.get_stats()
    usage_stats = usage_manager.get_overall_stats()
    
    return AdminStats(
        total_users=user_stats.get("total_users", 0),
        active_users=user_stats.get("active_users", 0),
        total_requests=usage_stats.get("total_requests", 0),
        total_revenue=usage_stats.get("total_revenue", 0),
        total_cost=usage_stats.get("total_cost", 0),
        profit=usage_stats.get("profit", 0),
        profit_margin=usage_stats.get("profit_margin", 0)
    )


@router.get("/users", response_model=List[UserInfo])
async def list_users(
    limit: int = 100,
    offset: int = 0,
    plan: Optional[str] = None,
    _: bool = Depends(verify_admin_key)
):
    """列出用户列表"""
    users = user_manager.list_users(limit=limit, offset=offset)
    
    result = []
    for user in users:
        if plan and user.plan != plan:
            continue
        result.append(UserInfo(
            user_id=user.user_id,
            email=user.email,
            plan=user.plan,
            balance=user.balance,
            is_active=user.is_active,
            created_at=user.created_at,
            total_requests=user.total_requests,
            daily_requests=user.daily_requests
        ))
    
    return result


@router.get("/users/{user_id}", response_model=UserInfo)
async def get_user_detail(
    user_id: str,
    _: bool = Depends(verify_admin_key)
):
    """获取用户详情"""
    user = user_manager.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    usage_stats = usage_manager.get_user_stats(user_id)
    
    return UserInfo(
        user_id=user.user_id,
        email=user.email,
        plan=user.plan,
        balance=user.balance,
        is_active=user.is_active,
        created_at=user.created_at,
        total_requests=usage_stats.get("total_requests", 0),
        daily_requests=user.daily_requests
    )


@router.post("/users/{user_id}/balance")
async def adjust_user_balance(
    user_id: str,
    amount: float,
    operation: str = "add",  # add or deduct
    reason: str = "管理员调整",
    _: bool = Depends(verify_admin_key)
):
    """调整用户余额"""
    user = user_manager.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if operation == "add":
        updated_user = user_manager.add_balance(user_id, amount)
        message = f"已添加 {amount:.2f} 元"
    else:
        if user.balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="余额不足"
            )
        success = user_manager.deduct_balance(user_id, amount)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="扣减失败"
            )
        updated_user = user_manager.get_user(user_id)
        message = f"已扣减 {amount:.2f} 元"
    
    # 记录操作
    usage_manager.record_usage(
        user_id=user_id,
        endpoint="admin_balance_adjust",
        model=None,
        input_tokens=0,
        output_tokens=0,
        cost=0,
        revenue=amount if operation == "add" else -amount,
        metadata={"reason": reason, "operation": operation}
    )
    
    return {
        "success": True,
        "message": message,
        "new_balance": updated_user.balance if updated_user else 0
    }


@router.post("/users/{user_id}/plan")
async def update_user_plan(
    user_id: str,
    plan: str,
    _: bool = Depends(verify_admin_key)
):
    """更新用户套餐"""
    from config import plan_config
    
    if plan not in plan_config.PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不存在的套餐: {plan}"
        )
    
    updated_user = user_manager.update_plan(user_id, plan)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return {
        "success": True,
        "message": f"已将用户套餐更新为 {plan_config.PLANS[plan].get('name')}",
        "plan": plan
    }


@router.post("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    is_active: bool,
    _: bool = Depends(verify_admin_key)
):
    """更新用户状态"""
    updated_user = user_manager.update_user(user_id, {"is_active": is_active})
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return {
        "success": True,
        "message": f"用户已 {'启用' if is_active else '禁用'}",
        "is_active": is_active
    }


@router.get("/usage/daily", response_model=List[DailyStat])
async def get_daily_stats(
    days: int = 30,
    _: bool = Depends(verify_admin_key)
):
    """获取每日统计"""
    stats = usage_manager.get_daily_stats(days=days)
    return [DailyStat(**s) for s in stats]


@router.get("/usage/overview")
async def get_usage_overview(
    _: bool = Depends(verify_admin_key)
):
    """获取用量概览"""
    overall = usage_manager.get_overall_stats()
    user_stats = user_manager.get_stats()
    
    # 按端点统计
    data = usage_manager._load_data()
    endpoint_stats = {}
    model_stats = {}
    
    for record in data.get("records", []):
        endpoint = record.get("endpoint", "unknown")
        if endpoint not in endpoint_stats:
            endpoint_stats[endpoint] = {"count": 0, "revenue": 0}
        endpoint_stats[endpoint]["count"] += 1
        endpoint_stats[endpoint]["revenue"] += record.get("revenue", 0)
        
        model = record.get("model", "unknown")
        if model not in model_stats:
            model_stats[model] = {"count": 0, "tokens": 0}
        model_stats[model]["count"] += 1
        model_stats[model]["tokens"] += record.get("input_tokens", 0) + record.get("output_tokens", 0)
    
    return {
        "overall": overall,
        "user_stats": user_stats,
        "endpoint_stats": endpoint_stats,
        "model_stats": model_stats
    }


@router.get("/health")
async def admin_health_check(
    _: bool = Depends(verify_admin_key)
):
    """管理后台健康检查"""
    from services.provider.openai import openai_provider
    from services.provider.anthropic import anthropic_provider
    from services.provider.deepseek import deepseek_provider
    from services.provider.gemini import gemini_provider
    
    providers_status = {}
    
    try:
        providers_status["openai"] = await openai_provider.health_check()
    except Exception as e:
        providers_status["openai"] = False
    
    try:
        providers_status["anthropic"] = await anthropic_provider.health_check()
    except Exception as e:
        providers_status["anthropic"] = False
    
    try:
        providers_status["deepseek"] = await deepseek_provider.health_check()
    except Exception as e:
        providers_status["deepseek"] = False
    
    try:
        providers_status["gemini"] = await gemini_provider.health_check()
    except Exception as e:
        providers_status["gemini"] = False
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "providers": providers_status
    }
