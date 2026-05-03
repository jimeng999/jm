"""
AI 供应商基类
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, AsyncIterator, Any
from dataclasses import dataclass


@dataclass
class Message:
    """消息结构"""
    role: str
    content: str


@dataclass
class ChatCompletionRequest:
    """聊天补全请求"""
    model: str
    messages: List[Message]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: Optional[List[str]] = None


@dataclass
class ChatCompletionResponse:
    """聊天补全响应"""
    id: str
    model: str
    choices: List[Dict]
    usage: Dict[str, int]
    created: int


class BaseProvider(ABC):
    """AI 供应商基类"""
    
    provider_name: str = "base"
    
    def __init__(self, api_key: str, base_url: str = None):
        self.api_key = api_key
        self.base_url = base_url
    
    @abstractmethod
    async def chat_completion(
        self,
        model: str,
        messages: List[Message],
        **kwargs
    ) -> ChatCompletionResponse:
        """发送聊天补全请求"""
        pass
    
    @abstractmethod
    async def chat_completion_stream(
        self,
        model: str,
        messages: List[Message],
        **kwargs
    ) -> AsyncIterator[str]:
        """发送流式聊天补全请求"""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str, model: str = None) -> int:
        """计算 token 数量（估算）"""
        pass
    
    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str
    ) -> float:
        """计算成本"""
        from config import model_config, settings
        
        # 获取模型成本
        for provider_models in model_config.PROVIDERS.values():
            if model in provider_models.get("models", {}):
                model_info = provider_models["models"][model]
                input_cost = model_info.get("input_cost", 0) / 1_000_000
                output_cost = model_info.get("output_cost", 0) / 1_000_000
                
                cost = (input_tokens * input_cost) + (output_tokens * output_cost)
                # 转换为人民币
                return cost * settings.token_rate_usd
        
        # 默认成本（GPT-4o-mini 基准）
        default_cost = (input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000 * settings.token_rate_usd
        return default_cost
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass
