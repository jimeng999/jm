"""
Google Gemini 供应商适配器
"""
import httpx
import time
import secrets
import json
from typing import List, AsyncIterator, Dict, Any

from .base import BaseProvider, Message, ChatCompletionResponse
from config import settings


class GeminiProvider(BaseProvider):
    """Google Gemini 供应商"""
    
    provider_name = "gemini"
    
    # 模型映射
    MODEL_MAPPING = {
        "gemini-1.5-flash": "gemini-1.5-flash",
        "gemini-1.5-pro": "gemini-1.5-pro",
        "gemini-pro": "gemini-pro",
        "gemini-pro-vision": "gemini-pro-vision"
    }
    
    def __init__(self, api_key: str = None):
        super().__init__(
            api_key=api_key or settings.gemini_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta"
        )
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=120.0
        )
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Message],
        **kwargs
    ) -> ChatCompletionResponse:
        """发送聊天补全请求"""
        gemini_model = self.MODEL_MAPPING.get(model, model)
        
        # 转换消息格式
        contents = []
        for msg in messages:
            if msg.role == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": msg.content}]
                })
            elif msg.role == "assistant":
                contents.append({
                    "role": "model",
                    "parts": [{"text": msg.content}]
                })
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.7),
                "maxOutputTokens": kwargs.get("max_tokens", 4096),
                "topP": kwargs.get("top_p", 1.0),
            }
        }
        
        # 安全设置
        payload["safetySettings"] = [
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        ]
        
        url = f"/models/{gemini_model}:generateContent?key={self.api_key}"
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # 转换响应格式
        content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        
        # 估算 token
        prompt_tokens = self.count_tokens(json.dumps(messages))
        completion_tokens = self.count_tokens(content)
        
        return ChatCompletionResponse(
            id=f"chatcmpl-{secrets.token_hex(12)}",
            model=model,
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            },
            created=int(time.time())
        )
    
    async def chat_completion_stream(
        self,
        model: str,
        messages: List[Message],
        **kwargs
    ) -> AsyncIterator[str]:
        """发送流式聊天补全请求（Gemini 不支持流式，此处返回普通响应）"""
        response = await self.chat_completion(model, messages, **kwargs)
        yield json.dumps({
            "id": response.id,
            "model": response.model,
            "choices": response.choices,
            "usage": response.usage
        })
    
    def count_tokens(self, text: str, model: str = None) -> int:
        """计算 token 数量（Gemini 使用不同估算）"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        # Gemini 估算更保守
        return int(chinese_chars / 1.5 + other_chars / 3)
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            url = f"/models?key={self.api_key}"
            response = await self.client.get(url)
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self):
        """关闭连接"""
        await self.client.aclose()


# 全局实例
gemini_provider = GeminiProvider()
