"""
配置管理模块
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用配置"""
    
    # 服务配置
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    debug: bool = Field(default=True, env="DEBUG")
    
    # API Keys
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", env="OPENAI_BASE_URL")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, env="DEEPSEEK_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    
    # 计费配置
    token_rate_usd: float = Field(default=7.2, env="TOKEN_RATE_USD")
    markup_ratio: float = Field(default=1.5, env="MARKUP_RATIO")
    free_tier_daily: int = Field(default=100, env="FREE_TIER_DAILY")
    
    # 管理配置
    admin_api_key: str = Field(default="admin_secret_key", env="ADMIN_API_KEY")
    
    # JWT 配置
    jwt_secret_key: str = Field(default="your-super-secret-jwt-key", env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=1440, env="JWT_EXPIRE_MINUTES")
    
    # 数据目录
    data_dir: Path = Field(default=Path("./data"), env="DATA_DIR")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()

# 确保数据目录存在
settings.data_dir.mkdir(parents=True, exist_ok=True)


# ==================== 模型配置 ====================

class ModelConfig:
    """模型配置"""
    
    # 模型供应商映射
    PROVIDERS = {
        "openai": {
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "models": {
                "gpt-4o-mini": {
                    "input_cost": 0.15,  # $/1M tokens
                    "output_cost": 0.60,
                    "capabilities": ["chat", "function", "vision"],
                    "max_tokens": 128000,
                    "tier": "fast"
                },
                "gpt-4o": {
                    "input_cost": 2.5,
                    "output_cost": 10.0,
                    "capabilities": ["chat", "function", "vision"],
                    "max_tokens": 128000,
                    "tier": "powerful"
                },
                "gpt-4-turbo": {
                    "input_cost": 10.0,
                    "output_cost": 30.0,
                    "capabilities": ["chat", "function", "vision"],
                    "max_tokens": 128000,
                    "tier": "powerful"
                }
            }
        },
        "anthropic": {
            "name": "Anthropic",
            "base_url": "https://api.anthropic.com/v1",
            "models": {
                "claude-3-5-sonnet-20241022": {
                    "input_cost": 3.0,
                    "output_cost": 15.0,
                    "capabilities": ["chat", "function"],
                    "max_tokens": 200000,
                    "tier": "powerful"
                },
                "claude-3-opus-20240229": {
                    "input_cost": 15.0,
                    "output_cost": 75.0,
                    "capabilities": ["chat", "function"],
                    "max_tokens": 200000,
                    "tier": "powerful"
                },
                "claude-3-haiku-20240307": {
                    "input_cost": 0.25,
                    "output_cost": 1.25,
                    "capabilities": ["chat", "function"],
                    "max_tokens": 200000,
                    "tier": "fast"
                }
            }
        },
        "deepseek": {
            "name": "DeepSeek",
            "base_url": "https://api.deepseek.com/v1",
            "models": {
                "deepseek-chat": {
                    "input_cost": 0.14,
                    "output_cost": 0.28,
                    "capabilities": ["chat", "function"],
                    "max_tokens": 128000,
                    "tier": "fast"
                },
                "deepseek-coder": {
                    "input_cost": 0.14,
                    "output_cost": 0.28,
                    "capabilities": ["chat", "function"],
                    "max_tokens": 128000,
                    "tier": "fast"
                }
            }
        },
        "gemini": {
            "name": "Google Gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "models": {
                "gemini-1.5-flash": {
                    "input_cost": 0.075,
                    "output_cost": 0.30,
                    "capabilities": ["chat", "function", "vision"],
                    "max_tokens": 1000000,
                    "tier": "fast"
                },
                "gemini-1.5-pro": {
                    "input_cost": 1.25,
                    "output_cost": 5.0,
                    "capabilities": ["chat", "function", "vision"],
                    "max_tokens": 1000000,
                    "tier": "powerful"
                }
            }
        }
    }
    
    # 模型路由规则
    ROUTING_RULES = {
        "simple": ["gpt-4o-mini", "claude-3-haiku-20240307", "deepseek-chat", "gemini-1.5-flash"],
        "coding": ["claude-3-5-sonnet-20241022", "deepseek-coder", "gpt-4o"],
        "analysis": ["claude-3-5-sonnet-20241022", "gpt-4o", "gemini-1.5-pro"],
        "creative": ["gpt-4o", "claude-3-5-sonnet-20241022"],
        "default": ["gpt-4o-mini", "claude-3-5-sonnet-20241022", "deepseek-chat"]
    }
    
    # 免费层可用模型
    FREE_TIER_MODELS = ["gpt-4o-mini"]


# ==================== 套餐配置 ====================

class PlanConfig:
    """订阅套餐配置"""
    
    PLANS = {
        "free": {
            "name": "免费层",
            "price": 0,
            "period": "daily",
            "requests_limit": 100,
            "models": ["gpt-4o-mini"],
            "features": ["basic_chat"]
        },
        "basic": {
            "name": "基础层",
            "price": 99,
            "period": "monthly",
            "requests_limit": 1000,
            "models": ["gpt-4o", "gpt-4o-mini", "claude-3-haiku-20240307"],
            "features": ["basic_chat", "basic_apis"]
        },
        "pro": {
            "name": "专业层",
            "price": 299,
            "period": "monthly",
            "requests_limit": 5000,
            "models": ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet-20241022", "deepseek-chat"],
            "features": ["basic_chat", "basic_apis", "content_write", "code_review", "data_analyze"]
        },
        "enterprise": {
            "name": "企业层",
            "price": 999,
            "period": "monthly",
            "requests_limit": -1,  # 无限制
            "models": "all",
            "features": ["all"],
            "sla": True,
            "priority": True
        }
    }


model_config = ModelConfig()
plan_config = PlanConfig()
