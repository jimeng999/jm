"""
计费服务
"""
from typing import Dict, Optional
from config import settings, plan_config, model_config
from models.user import user_manager
from models.usage import usage_manager


class BillingService:
    """计费服务"""
    
    # 垂直 API 定价（按结果收费）
    VERTICAL_API_PRICES = {
        "content/write": {
            "short": 2.0,      # 短内容 ¥2
            "medium": 5.0,     # 中等内容 ¥5
            "long": 10.0,     # 长内容 ¥10
            "ultra": 20.0     # 超长内容 ¥20
        },
        "code/review": {
            "basic": 3.0,      # 基础审查 ¥3
            "standard": 8.0,   # 标准审查 ¥8
            "detailed": 15.0   # 详细审查 ¥15
        },
        "data/analyze": {
            "simple": 30.0,    # 简单分析 ¥30
            "standard": 80.0,  # 标准分析 ¥80
            "detailed": 150.0, # 详细报告 ¥150
            "enterprise": 200.0 # 企业级报告 ¥200
        },
        "chat/smart": {
            "per_turn": 0.5    # 每轮对话 ¥0.5
        }
    }
    
    def __init__(self):
        self.token_rate = settings.token_rate_usd
        self.markup_ratio = settings.markup_ratio
    
    def check_daily_limit(self, user: Dict) -> Dict:
        """检查每日限制"""
        plan = user.get("plan", "free")
        plan_info = plan_config.PLANS.get(plan, {})
        daily_limit = plan_info.get("requests_limit", 100)
        daily_requests = user.get("daily_requests", 0)
        
        if daily_limit == -1:
            return {
                "allowed": True,
                "remaining": -1,
                "limit": -1,
                "message": "无限制"
            }
        
        remaining = max(0, daily_limit - daily_requests)
        
        return {
            "allowed": remaining > 0,
            "remaining": remaining,
            "limit": daily_limit,
            "message": f"今日剩余 {remaining} 次"
        }
    
    def check_balance(self, user: Dict, required: float) -> bool:
        """检查余额是否足够"""
        balance = user.get("balance", 0)
        return balance >= required
    
    def calculate_token_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, float]:
        """计算 Token 成本"""
        # 获取模型成本
        input_cost_per_token = 0
        output_cost_per_token = 0
        
        for provider_models in model_config.PROVIDERS.values():
            if model in provider_models.get("models", {}):
                model_info = provider_models["models"][model]
                input_cost_per_token = model_info.get("input_cost", 0) / 1_000_000
                output_cost_per_token = model_info.get("output_cost", 0) / 1_000_000
                break
        
        # 计算成本
        input_cost = input_tokens * input_cost_per_token
        output_cost = output_tokens * output_cost_per_token
        total_cost_usd = input_cost + output_cost
        
        # 转换为人民币
        cost_cny = total_cost_usd * self.token_rate
        
        return {
            "input_cost_usd": input_cost,
            "output_cost_usd": output_cost,
            "total_cost_usd": total_cost_usd,
            "cost_cny": cost_cny
        }
    
    def calculate_price(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, float]:
        """计算向用户收取的价格"""
        cost = self.calculate_token_cost(model, input_tokens, output_tokens)
        
        price = cost["cost_cny"] * self.markup_ratio
        
        return {
            **cost,
            "price_cny": price,
            "price_usd": price / self.token_rate,
            "profit": price - cost["cost_cny"],
            "margin": (price - cost["cost_cny"]) / price * 100 if price > 0 else 0
        }
    
    def get_vertical_api_price(
        self,
        endpoint: str,
        tier: str = "standard"
    ) -> float:
        """获取垂直 API 价格"""
        endpoint_prices = self.VERTICAL_API_PRICES.get(endpoint, {})
        return endpoint_prices.get(tier, endpoint_prices.get("standard", 5.0))
    
    def charge_user(
        self,
        user_id: str,
        amount: float,
        description: str
    ) -> bool:
        """扣费"""
        if amount <= 0:
            return True
        
        success = user_manager.deduct_balance(user_id, amount)
        if success:
            # 记录用量
            usage_manager.record_usage(
                user_id=user_id,
                endpoint="charge",
                model=None,
                input_tokens=0,
                output_tokens=0,
                cost=0,
                revenue=amount,
                metadata={"description": description}
            )
        return success
    
    def record_api_usage(
        self,
        user_id: str,
        endpoint: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> Dict:
        """记录 API 用量"""
        # 计算成本和收入
        pricing = self.calculate_price(model, input_tokens, output_tokens)
        cost = pricing["cost_cny"]
        revenue = pricing["price_cny"]
        
        # 记录用量
        record = usage_manager.record_usage(
            user_id=user_id,
            endpoint=endpoint,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            revenue=revenue
        )
        
        # 扣费
        if not self.charge_user(user_id, revenue, f"{endpoint} - {model}"):
            return {"success": False, "error": "余额不足"}
        
        return {
            "success": True,
            "usage_id": record.usage_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "price": revenue,
            "balance_after": user_manager.get_user(user_id).balance if user_manager.get_user(user_id) else 0
        }
    
    def get_user_balance_info(self, user_id: str) -> Dict:
        """获取用户余额信息"""
        user = user_manager.get_user(user_id)
        if not user:
            return {"error": "用户不存在"}
        
        usage_stats = usage_manager.get_user_stats(user_id)
        
        return {
            "user_id": user_id,
            "balance": user.balance,
            "plan": user.plan,
            "total_spent": usage_stats.get("total_revenue", 0),
            "total_requests": usage_stats.get("total_requests", 0),
            "total_tokens": usage_stats.get("total_tokens", 0)
        }
    
    def get_subscription_info(self, plan: str) -> Dict:
        """获取订阅信息"""
        plan_info = plan_config.PLANS.get(plan, {})
        
        return {
            "plan": plan,
            "name": plan_info.get("name", "未知"),
            "price": plan_info.get("price", 0),
            "period": plan_info.get("period", "monthly"),
            "requests_limit": plan_info.get("requests_limit", 0),
            "features": plan_info.get("features", []),
            "models": plan_info.get("models", [])
        }


# 全局计费服务实例
billing_service = BillingService()
