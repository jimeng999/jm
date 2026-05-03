"""
OpenAI 供应商适配器
"""
import httpx
import time
import secrets
from typing import List, AsyncIterator, Dict, Any

from .base import BaseProvider, Message, ChatCompletionResponse
from config import settings


class OpenAIProvider(BaseProvider):
    """OpenAI 供应商"""
    
    provider_name = "openai"
    
    def __init__(self, api_key: str = None, base_url: str = None):
        super().__init__(
            api_key=api_key or settings.openai_api_key,
            base_url=base_url or settings.openai_base_url
        )
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=120.0
        )
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Message],
        **kwargs
    ) -> ChatCompletionResponse:
        """发送聊天补全请求"""
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            **kwargs
        }
        
        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        
        return ChatCompletionResponse(
            id=data.get("id", f"chatcmpl-{secrets.token_hex(12)}"),
            model=data.get("model", model),
            choices=data.get("choices", []),
            usage=data.get("usage", {}),
            created=data.get("created", int(time.time()))
        )
    
    async def chat_completion_stream(
        self,
        model: str,
        messages: List[Message],
        **kwargs
    ) -> AsyncIterator[str]:
        """发送流式聊天补全请求"""
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            **kwargs
        }
        
        async with self.client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    yield data
    
    def count_tokens(self, text: str, model: str = None) -> int:
        """计算 token 数量（简单估算：中文约 2 字符/token，英文约 4 字符/token）"""
        # 简单估算公式
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 2 + other_chars / 4)
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            response = await self.client.get("/models")
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self):
        """关闭连接"""
        await self.client.aclose()


# 全局实例
openai_provider = OpenAIProvider()
