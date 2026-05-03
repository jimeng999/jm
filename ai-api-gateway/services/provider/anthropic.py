"""
Anthropic 供应商适配器
"""
import httpx
import time
import secrets
from typing import List, AsyncIterator, Dict, Any

from .base import BaseProvider, Message, ChatCompletionResponse
from config import settings


class AnthropicProvider(BaseProvider):
    """Anthropic (Claude) 供应商"""
    
    provider_name = "anthropic"
    
    def __init__(self, api_key: str = None):
        super().__init__(
            api_key=api_key or settings.anthropic_api_key,
            base_url="https://api.anthropic.com/v1"
        )
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
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
        # 转换消息格式
        system_message = ""
        formatted_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_message += msg.content + "\n"
            else:
                formatted_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        payload = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 1.0),
        }
        
        if system_message:
            payload["system"] = system_message
        
        if kwargs.get("stream"):
            payload["stream"] = True
        
        if kwargs.get("stop"):
            payload["stop_sequences"] = kwargs["stop"]
        
        response = await self.client.post("/messages", json=payload)
        response.raise_for_status()
        data = response.json()
        
        # 转换响应格式为 OpenAI 格式
        return ChatCompletionResponse(
            id=f"chatcmpl-{secrets.token_hex(12)}",
            model=data.get("model", model),
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": data.get("content", [{"text": ""}])[0].get("text", "")
                },
                "finish_reason": data.get("stop_reason", "stop")
            }],
            usage={
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                "total_tokens": data.get("usage", {}).get("input_tokens", 0) + 
                               data.get("usage", {}).get("output_tokens", 0)
            },
            created=int(time.time())
        )
    
    async def chat_completion_stream(
        self,
        model: str,
        messages: List[Message],
        **kwargs
    ) -> AsyncIterator[str]:
        """发送流式聊天补全请求"""
        payload = await self._build_payload(model, messages, stream=True, **kwargs)
        
        async with self.client.stream("POST", "/messages", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    yield data
    
    async def _build_payload(self, model: str, messages: List[Message], **kwargs):
        """构建请求 payload"""
        system_message = ""
        formatted_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_message += msg.content + "\n"
            else:
                formatted_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        payload = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.7),
            "stream": kwargs.get("stream", False),
        }
        
        if system_message:
            payload["system"] = system_message
        
        return payload
    
    def count_tokens(self, text: str, model: str = None) -> int:
        """计算 token 数量"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 2 + other_chars / 4)
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # Anthropic 没有专门的健康检查端点，尝试获取 credit
            response = await self.client.get("/credits")
            return response.status_code in [200, 401]  # 401 也表示服务正常
        except Exception:
            return False
    
    async def close(self):
        """关闭连接"""
        await self.client.aclose()


# 全局实例
anthropic_provider = AnthropicProvider()
