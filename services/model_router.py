"""
智能模型路由服务
"""
import re
from typing import List, Optional, Dict
from config import model_config, plan_config


class ModelRouter:
    """智能模型路由器"""
    
    def __init__(self):
        self.providers = model_config.PROVIDERS
        self.routing_rules = model_config.ROUTING_RULES
        self.free_tier_models = model_config.FREE_TIER_MODELS
    
    def detect_task_type(self, messages: List[Dict]) -> str:
        """
        根据消息内容检测任务类型
        
        Args:
            messages: 消息列表
            
        Returns:
            任务类型: simple, coding, analysis, creative
        """
        # 合并所有消息内容
        content = " ".join(
            msg.get("content", "") for msg in messages 
            if isinstance(msg, dict)
        ).lower()
        
        # 代码相关关键词
        code_keywords = [
            "code", "python", "javascript", "java", "function", "class",
            "def ", "import ", "bug", "debug", "api", "sql", "debug",
            "编程", "代码", "函数", "程序", "软件"
        ]
        
        # 分析相关关键词
        analysis_keywords = [
            "analyze", "analysis", "report", "data", "statistic",
            "chart", "graph", "trend", "research", "study",
            "分析", "报告", "数据", "统计", "研究"
        ]
        
        # 创意相关关键词
        creative_keywords = [
            "write", "create", "story", "poem", "song", "creative",
            "design", "marketing", "advertisement",
            "写作", "创作", "故事", "创意", "营销"
        ]
        
        # 计算关键词匹配度
        code_score = sum(1 for kw in code_keywords if kw in content)
        analysis_score = sum(1 for kw in analysis_keywords if kw in content)
        creative_score = sum(1 for kw in creative_keywords if kw in content)
        
        # 判断任务类型
        if code_score >= 2:
            return "coding"
        elif analysis_score >= 2:
            return "analysis"
        elif creative_score >= 2:
            return "creative"
        else:
            return "simple"
    
    def select_model(
        self,
        task_type: str = "simple",
        user_plan: str = "free",
        preferred_provider: str = None,
        force_model: str = None
    ) -> Dict[str, str]:
        """
        选择最优模型
        
        Args:
            task_type: 任务类型
            user_plan: 用户套餐
            preferred_provider: 首选供应商
            force_model: 强制使用某模型
            
        Returns:
            {"provider": str, "model": str}
        """
        # 如果强制指定模型
        if force_model:
            provider = self._find_model_provider(force_model)
            if provider:
                return {"provider": provider, "model": force_model}
        
        # 获取可用模型列表
        available_models = self._get_available_models(user_plan)
        
        # 根据任务类型获取候选模型
        candidate_models = self.routing_rules.get(
            task_type, 
            self.routing_rules["default"]
        )
        
        # 筛选可用模型
        available_candidates = [
            m for m in candidate_models 
            if m in available_models or plan_config.PLANS.get(user_plan, {}).get("models") == "all"
        ]
        
        if not available_candidates:
            # 默认使用免费层模型
            available_candidates = [self.free_tier_models[0]]
        
        # 如果指定了首选供应商
        if preferred_provider:
            for model in available_candidates:
                if self._find_model_provider(model) == preferred_provider:
                    return {"provider": preferred_provider, "model": model}
        
        # 默认选择第一个候选
        selected_model = available_candidates[0]
        provider = self._find_model_provider(selected_model)
        
        return {"provider": provider, "model": selected_model}
    
    def _get_available_models(self, plan: str) -> List[str]:
        """获取套餐可用模型"""
        plan_info = plan_config.PLANS.get(plan, {})
        models = plan_info.get("models", [])
        
        if models == "all":
            # 返回所有模型
            all_models = []
            for provider_models in self.providers.values():
                all_models.extend(provider_models.get("models", {}).keys())
            return all_models
        
        return models
    
    def _find_model_provider(self, model: str) -> Optional[str]:
        """查找模型所属供应商"""
        for provider, info in self.providers.items():
            if model in info.get("models", {}):
                return provider
        return "openai"  # 默认
    
    def get_model_info(self, model: str) -> Optional[Dict]:
        """获取模型信息"""
        for provider, info in self.providers.items():
            if model in info.get("models", {}):
                return {
                    "provider": provider,
                    "provider_name": info.get("name"),
                    "model": model,
                    **info["models"][model]
                }
        return None
    
    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, float]:
        """估算成本"""
        from config import settings
        
        model_info = self.get_model_info(model)
        if not model_info:
            return {"cost_cny": 0, "cost_usd": 0}
        
        input_cost = model_info.get("input_cost", 0) / 1_000_000 * input_tokens
        output_cost = model_info.get("output_cost", 0) / 1_000_000 * output_tokens
        cost_usd = input_cost + output_cost
        
        return {
            "cost_usd": cost_usd,
            "cost_cny": cost_usd * settings.token_rate_usd,
            "input_cost": input_cost * settings.token_rate_usd,
            "output_cost": output_cost * settings.token_rate_usd
        }
    
    def calculate_price(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, float]:
        """计算向用户收取的价格（成本 * 加价倍率）"""
        from config import settings
        
        costs = self.estimate_cost(model, input_tokens, output_tokens)
        cost_cny = costs["cost_cny"]
        
        price = cost_cny * settings.markup_ratio
        
        return {
            **costs,
            "price_cny": price,
            "price_usd": price / settings.token_rate_usd,
            "profit": price - cost_cny,
            "margin": (price - cost_cny) / price * 100 if price > 0 else 0
        }


# 全局路由器实例
model_router = ModelRouter()
