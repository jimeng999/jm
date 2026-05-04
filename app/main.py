"""
AI API Gateway - Vercel Serverless 版本
核心应用模块
"""
import os
import json
import time
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from urllib.parse import parse_qs, urlparse

# ==================== 配置 ====================

class Config:
    """Vercel 环境配置"""
    # API Keys
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    
    # JWT配置
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "vercel-secret-key-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    
    # 计费配置
    TOKEN_RATE_USD: float = 7.2
    MARKUP_RATIO: float = 1.5
    FREE_TIER_DAILY: int = 100
    
    # 管理配置
    ADMIN_API_KEY: str = os.environ.get("ADMIN_API_KEY", "admin_secret_key")

config = Config()


# ==================== 数据存储（简化版，Vercel Serverless 内存模式） ====================

class SimpleStore:
    """简单的内存数据存储（适合Serverless）"""
    
    def __init__(self):
        self._users: Dict[str, Dict] = {}
        self._api_keys: Dict[str, str] = {}  # api_key -> user_id
        self._tokens: Dict[str, Dict] = {}  # token -> user_id
        self._usage: Dict[str, List] = {}  # user_id -> usage_records
    
    def create_user(self, email: str, password: str, plan: str = "free") -> Optional[Dict]:
        """创建用户"""
        # 检查邮箱是否存在
        for user in self._users.values():
            if user.get("email") == email:
                return None
        
        user_id = f"user_{secrets.token_hex(16)}"
        api_key = f"sk-{secrets.token_hex(32)}"
        password_hash = self._hash_password(password)
        now = datetime.now().isoformat()
        
        user = {
            "user_id": user_id,
            "email": email,
            "password_hash": password_hash,
            "plan": plan,
            "api_key": api_key,
            "balance": 0.0,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
            "daily_requests": 0,
            "last_request_date": now[:10],
            "total_requests": 0
        }
        
        self._users[user_id] = user
        self._api_keys[api_key] = user_id
        
        return user
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """获取用户"""
        user = self._users.get(user_id)
        if user:
            return self._check_daily_reset(user)
        return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """通过邮箱获取用户"""
        for user in self._users.values():
            if user.get("email") == email:
                return self._check_daily_reset(user)
        return None
    
    def get_user_by_api_key(self, api_key: str) -> Optional[Dict]:
        """通过API Key获取用户"""
        user_id = self._api_keys.get(api_key)
        if user_id:
            user = self._users.get(user_id)
            if user:
                return self._check_daily_reset(user)
        return None
    
    def authenticate(self, email: str, password: str) -> Optional[Dict]:
        """验证用户登录"""
        user = self.get_user_by_email(email)
        if user and user.get("is_active"):
            if self._verify_password(password, user.get("password_hash", "")):
                return user
        return None
    
    def increment_request_count(self, user_id: str):
        """增加请求计数"""
        if user_id in self._users:
            today = datetime.now().strftime("%Y-%m-%d")
            user = self._users[user_id]
            if user.get("last_request_date") != today:
                user["daily_requests"] = 0
                user["last_request_date"] = today
            user["daily_requests"] += 1
            user["total_requests"] += 1
    
    def _check_daily_reset(self, user: Dict) -> Dict:
        """检查并重置每日计数"""
        today = datetime.now().strftime("%Y-%m-%d")
        if user.get("last_request_date") != today:
            user["daily_requests"] = 0
            user["last_request_date"] = today
        return user
    
    def _hash_password(self, password: str) -> str:
        """哈希密码"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000
        )
        return f"{salt}${pwd_hash.hex()}"
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        try:
            salt, pwd_hash = hashed.split('$')
            new_hash = hashlib.pbkdf2_hmac(
                'sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000
            )
            return new_hash.hex() == pwd_hash
        except Exception:
            return False


# 全局存储实例
store = SimpleStore()


# ==================== JWT 工具 ====================

def create_access_token(user_id: str, plan: str = "free") -> str:
    """创建JWT Token"""
    try:
        from jose import jwt
        expire = datetime.utcnow() + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
        to_encode = {
            "sub": user_id,
            "plan": plan,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        return jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    except ImportError:
        # 如果没有jose库，使用简单的base64编码
        import base64
        import json
        expire = int(time.time()) + config.JWT_EXPIRE_MINUTES * 60
        payload = {
            "sub": user_id,
            "plan": plan,
            "exp": expire
        }
        return base64.b64encode(json.dumps(payload).encode()).decode()


def decode_access_token(token: str) -> Optional[Dict]:
    """解码JWT Token"""
    try:
        from jose import jwt, JWTError
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        return payload
    except Exception:
        return None


# ==================== 认证函数 ====================

def verify_api_key(api_key: str) -> Optional[Dict]:
    """验证API Key"""
    return store.get_user_by_api_key(api_key)


def get_current_user(request) -> Optional[Dict]:
    """从请求中获取当前用户"""
    auth_header = request.headers.get("Authorization", "")
    
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_access_token(token)
        if payload:
            return store.get_user(payload.get("sub"))
    
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return store.get_user_by_api_key(api_key)
    
    return None


# ==================== 模型配置 ====================

MODEL_CONFIG = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "models": {
            "gpt-4o-mini": {"input_cost": 0.15, "output_cost": 0.60, "tier": "fast"},
            "gpt-4o": {"input_cost": 2.5, "output_cost": 10.0, "tier": "powerful"},
        }
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "models": {
            "claude-3-5-sonnet-20241022": {"input_cost": 3.0, "output_cost": 15.0, "tier": "powerful"},
            "claude-3-haiku-20240307": {"input_cost": 0.25, "output_cost": 1.25, "tier": "fast"},
        }
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "models": {
            "deepseek-chat": {"input_cost": 0.14, "output_cost": 0.28, "tier": "fast"},
        }
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key_env": "GEMINI_API_KEY",
        "models": {
            "gemini-1.5-flash": {"input_cost": 0.075, "output_cost": 0.30, "tier": "fast"},
        }
    }
}

PLAN_CONFIG = {
    "free": {"name": "免费层", "requests_limit": 100, "models": ["gpt-4o-mini"]},
    "basic": {"name": "基础层", "requests_limit": 1000, "models": ["gpt-4o", "gpt-4o-mini", "claude-3-haiku-20240307"]},
    "pro": {"name": "专业层", "requests_limit": 5000, "models": ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet-20241022", "deepseek-chat"]},
}


def find_model_provider(model: str) -> Optional[str]:
    """查找模型所属供应商"""
    for provider, info in MODEL_CONFIG.items():
        if model in info.get("models", {}):
            return provider
    return "openai"


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Dict:
    """估算成本"""
    provider = find_model_provider(model)
    if provider:
        model_info = MODEL_CONFIG[provider]["models"].get(model, {})
        input_cost = model_info.get("input_cost", 0.15) / 1_000_000 * input_tokens
        output_cost = model_info.get("output_cost", 0.60) / 1_000_000 * output_tokens
        cost_usd = input_cost + output_cost
        return {
            "cost_usd": cost_usd,
            "cost_cny": cost_usd * config.TOKEN_RATE_USD,
            "price_cny": cost_usd * config.TOKEN_RATE_USD * config.MARKUP_RATIO
        }
    return {"cost_usd": 0, "cost_cny": 0, "price_cny": 0}


# ==================== AI 供应商调用 ====================

async def call_openai(model: str, messages: List[Dict], **kwargs) -> Dict:
    """调用OpenAI API"""
    import httpx
    
    api_key = config.OPENAI_API_KEY
    if not api_key:
        raise Exception("OpenAI API Key not configured")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": messages,
                **kwargs
            }
        )
        response.raise_for_status()
        return response.json()


async def call_anthropic(model: str, messages: List[Dict], **kwargs) -> Dict:
    """调用Anthropic API"""
    import httpx
    
    api_key = config.ANTHROPIC_API_KEY
    if not api_key:
        raise Exception("Anthropic API Key not configured")
    
    # 转换消息格式
    anthropic_messages = []
    for msg in messages:
        if msg["role"] == "system":
            continue
        anthropic_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": anthropic_messages,
                **kwargs
            }
        )
        response.raise_for_status()
        data = response.json()
        
        # 转换为OpenAI格式
        return {
            "id": data.get("id", f"chatcmpl-{secrets.token_hex(12)}"),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": data["content"][0]["text"]},
                "finish_reason": data.get("stop_reason", "stop")
            }],
            "usage": {
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                "total_tokens": sum(data.get("usage", {}).values())
            },
            "created": int(time.time())
        }


async def call_deepseek(model: str, messages: List[Dict], **kwargs) -> Dict:
    """调用DeepSeek API"""
    import httpx
    
    api_key = config.DEEPSEEK_API_KEY
    if not api_key:
        raise Exception("DeepSeek API Key not configured")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": messages,
                **kwargs
            }
        )
        response.raise_for_status()
        return response.json()


async def call_gemini(model: str, messages: List[Dict], **kwargs) -> Dict:
    """调用Google Gemini API"""
    import httpx
    
    api_key = config.GEMINI_API_KEY
    if not api_key:
        raise Exception("Gemini API Key not configured")
    
    # 转换消息格式
    contents = []
    for msg in messages:
        if msg["role"] == "system":
            continue
        contents.append({
            "role": msg["role"],
            "parts": [{"text": msg["content"]}]
        })
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={
                "Content-Type": "application/json"
            },
            params={"key": api_key},
            json={
                "contents": contents,
                **kwargs
            }
        )
        response.raise_for_status()
        data = response.json()
        
        # 转换为OpenAI格式
        content = data["candidates"][0]["content"]["parts"][0]["text"]
        return {
            "id": f"gemini-{secrets.token_hex(12)}",
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": data.get("usageMetadata", {}).get("promptTokenCount", 0),
                "completion_tokens": data.get("usageMetadata", {}).get("candidatesTokenCount", 0),
                "total_tokens": data.get("usageMetadata", {}).get("totalTokenCount", 0)
            },
            "created": int(time.time())
        }


async def call_ai_provider(provider: str, model: str, messages: List[Dict], **kwargs) -> Dict:
    """调用AI供应商"""
    if provider == "openai":
        return await call_openai(model, messages, **kwargs)
    elif provider == "anthropic":
        return await call_anthropic(model, messages, **kwargs)
    elif provider == "deepseek":
        return await call_deepseek(model, messages, **kwargs)
    elif provider == "gemini":
        return await call_gemini(model, messages, **kwargs)
    else:
        return await call_openai(model, messages, **kwargs)


# ==================== 请求路由处理 ====================

def parse_request_body(request) -> Dict:
    """解析请求体"""
    try:
        if hasattr(request, 'json'):
            return request.json
        elif hasattr(request, 'body'):
            body = request.body
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            return json.loads(body) if body else {}
        return {}
    except Exception:
        return {}


async def handle_chat_completions(request, user: Dict) -> Dict:
    """处理聊天补全请求"""
    body = parse_request_body(request)
    
    model = body.get("model", "auto")
    messages = body.get("messages", [])
    temperature = body.get("temperature", 0.7)
    max_tokens = body.get("max_tokens", 4096)
    
    # 检查每日限制
    plan_info = PLAN_CONFIG.get(user.get("plan", "free"), PLAN_CONFIG["free"])
    limit = plan_info.get("requests_limit", 100)
    daily = user.get("daily_requests", 0)
    
    if daily >= limit:
        return {
            "error": {
                "message": f"每日请求次数已达上限 (今日剩余 {max(0, limit - daily)} 次)",
                "type": "rate_limit",
                "code": "daily_limit_exceeded"
            }
        }
    
    # 增加请求计数
    store.increment_request_count(user["user_id"])
    
    # 自动模型选择
    if model == "auto":
        # 简单路由策略
        content = " ".join(m.get("content", "").lower() for m in messages if isinstance(m, dict))
        
        if any(kw in content for kw in ["code", "python", "function", "bug", "debug", "api", "编程", "代码"]):
            task = "coding"
        elif any(kw in content for kw in ["analyze", "analysis", "data", "report", "分析", "报告"]):
            task = "analysis"
        else:
            task = "simple"
        
        # 根据任务类型选择模型
        if task == "coding":
            selected_model = "claude-3-5-sonnet-20241022"
            provider = "anthropic"
        elif task == "analysis":
            selected_model = "gpt-4o"
            provider = "openai"
        else:
            selected_model = "gpt-4o-mini"
            provider = "openai"
        
        model = selected_model
    else:
        provider = find_model_provider(model)
    
    # 调用AI供应商
    try:
        start_time = time.time()
        response = await call_ai_provider(provider, model, messages, 
                                          temperature=temperature, 
                                          max_tokens=max_tokens)
        
        # 计算成本
        usage = response.get("usage", {})
        costs = estimate_cost(
            model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0)
        )
        
        elapsed = time.time() - start_time
        
        return {
            "id": response.get("id", f"chatcmpl-{secrets.token_hex(12)}"),
            "object": "chat.completion",
            "created": response.get("created", int(time.time())),
            "model": model,
            "choices": response.get("choices", []),
            "usage": usage,
            "_internal": {
                "provider": provider,
                "cost_cny": costs["cost_cny"],
                "price_cny": costs["price_cny"],
                "elapsed": elapsed
            }
        }
    except Exception as e:
        return {
            "error": {
                "message": f"AI请求失败: {str(e)}",
                "type": "api_error"
            }
        }


# ==================== 主应用入口 ====================

async def app(request, context=None):
    """
    Vercel Serverless Function 主入口
    
    处理所有HTTP请求并返回响应
    """
    path = request.path if hasattr(request, 'path') else urlparse(request.url).path
    method = request.method if hasattr(request, 'method') else 'GET'
    
    # CORS 头
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key"
    }
    
    # 处理 OPTIONS 预检请求
    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": ""
        }
    
    # 健康检查
    if path == "/health" or path == "/":
        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps({
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
                "service": "AI API Gateway (Vercel)"
            })
        }
    
    # 注册
    if path == "/v1/auth/register" and method == "POST":
        body = parse_request_body(request)
        email = body.get("email", "")
        password = body.get("password", "")
        
        if not email or "@" not in email:
            return {
                "statusCode": 400,
                "headers": {**cors_headers, "Content-Type": "application/json"},
                "body": json.dumps({"error": "邮箱格式不正确"})
            }
        
        if not password or len(password) < 6:
            return {
                "statusCode": 400,
                "headers": {**cors_headers, "Content-Type": "application/json"},
                "body": json.dumps({"error": "密码至少6位"})
            }
        
        user = store.create_user(email, password)
        if not user:
            return {
                "statusCode": 400,
                "headers": {**cors_headers, "Content-Type": "application/json"},
                "body": json.dumps({"error": "邮箱已被注册"})
            }
        
        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps({
                "user_id": user["user_id"],
                "email": user["email"],
                "api_key": user["api_key"],
                "plan": user["plan"],
                "message": "注册成功！您的免费套餐已激活。"
            })
        }
    
    # 登录
    if path == "/v1/auth/login" and method == "POST":
        body = parse_request_body(request)
        email = body.get("email", "")
        password = body.get("password", "")
        
        user = store.authenticate(email, password)
        if not user:
            return {
                "statusCode": 401,
                "headers": {**cors_headers, "Content-Type": "application/json"},
                "body": json.dumps({"error": "邮箱或密码错误"})
            }
        
        token = create_access_token(user["user_id"], user["plan"])
        
        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps({
                "access_token": token,
                "token_type": "bearer",
                "user_id": user["user_id"],
                "email": user["email"],
                "plan": user["plan"]
            })
        }
    
    # 聊天补全
    if path == "/v1/chat/completions" and method == "POST":
        user = get_current_user(request)
        if not user:
            return {
                "statusCode": 401,
                "headers": {**cors_headers, "Content-Type": "application/json"},
                "body": json.dumps({"error": "未授权，请提供有效的API Key或Token"})
            }
        
        result = await handle_chat_completions(request, user)
        
        if "error" in result:
            return {
                "statusCode": result["error"].get("code") == "daily_limit_exceeded" and 429 or 500,
                "headers": {**cors_headers, "Content-Type": "application/json"},
                "body": json.dumps(result)
            }
        
        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps(result)
        }
    
    # 模型列表
    if path == "/v1/models" and method == "GET":
        user = get_current_user(request)
        plan_models = PLAN_CONFIG.get(user.get("plan", "free") if user else "free", PLAN_CONFIG["free"])["models"]
        
        all_models = []
        for provider, info in MODEL_CONFIG.items():
            for model_name, model_info in info["models"].items():
                all_models.append({
                    "id": model_name,
                    "object": "model",
                    "provider": provider,
                    "provider_name": info["name"],
                    **model_info
                })
        
        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps({
                "object": "list",
                "data": all_models
            })
        }
    
    # 计费信息
    if path == "/v1/billing/usage" and method == "GET":
        user = get_current_user(request)
        if not user:
            return {
                "statusCode": 401,
                "headers": {**cors_headers, "Content-Type": "application/json"},
                "body": json.dumps({"error": "未授权"})
            }
        
        plan_info = PLAN_CONFIG.get(user.get("plan", "free"), PLAN_CONFIG["free"])
        
        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps({
                "user_id": user["user_id"],
                "plan": user["plan"],
                "plan_name": plan_info["name"],
                "daily_requests": user.get("daily_requests", 0),
                "daily_limit": plan_info["requests_limit"],
                "total_requests": user.get("total_requests", 0),
                "balance": user.get("balance", 0)
            })
        }
    
    # 404 处理
    return {
        "statusCode": 404,
        "headers": {**cors_headers, "Content-Type": "application/json"},
        "body": json.dumps({
            "error": {
                "message": f"API endpoint not found: {method} {path}",
                "type": "invalid_request"
            }
        })
    }
