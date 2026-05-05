"""
AI API Gateway - 主入口文件 (BYOK 版本)
智能路由聚合网关系统 - 支持 Bring Your Own Key 模式
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from config import settings
from utils.logger import logger
from utils.auth import create_access_token, hash_password, verify_password
from utils.encryption import key_encryptor, mask_api_key
from utils.simple_store import set_user_byok_key, get_user_byok_key, delete_user_byok_key, get_user_all_byok_keys, get_free_trial_count, increment_free_trial

# 导入所有路由
from routers import chat, content, code, data, billing, admin


# ==================== FastAPI 应用初始化 ====================

app = FastAPI(
    title="AI API Gateway",
    description="""
## 智能路由聚合网关 - BYOK 模式

通过 Bring Your Own Key (BYOK) 模式，让用户使用自己的 API Key，平台赚取工具层费用。

### 核心功能

1. **BYOK 模式** - 用户自带 API Key，零中间差价
2. **平台 Key 兜底** - 无 Key 用户使用平台 Key，按量加价 30%
3. **免费体验** - 每日 5 次 DeepSeek 免费体验
4. **智能路由** - Pro 用户享有多模型智能路由

### 商业模式

- **BYOK 模式**：用户用自己的 Key，平台不赚差价
- **平台 Key**：无 BYOK 时使用平台 Key，加价 30%
- **Pro 订阅**：¥49/月，智能路由 + 用量分析
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 请求/响应模型 ====================

class RegisterRequest(BaseModel):
    """注册请求"""
    email: str = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, description="密码（至少6位）")


class RegisterResponse(BaseModel):
    """注册响应"""
    user_id: str
    email: str
    api_key: str
    plan: str
    message: str


class LoginRequest(BaseModel):
    """登录请求"""
    email: str = Field(..., description="邮箱地址")
    password: str = Field(..., description="密码")


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    plan: str


class SetApiKeyRequest(BaseModel):
    """设置 BYOK API Key 请求"""
    provider: str = Field(..., description="Provider: openai, anthropic, deepseek, gemini")
    api_key: str = Field(..., description="API Key")


class ApiKeyResponse(BaseModel):
    """API Key 响应（脱敏）"""
    provider: str
    masked_key: str
    is_set: bool = True


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    timestamp: str


class FreeTrialResponse(BaseModel):
    """免费体验响应"""
    daily_limit: int = 5
    used: int
    remaining: int


# ==================== 路由注册 ====================

@app.post("/v1/auth/register", response_model=RegisterResponse, tags=["认证"])
async def register(request: RegisterRequest):
    """
    用户注册
    
    注册后自动获得：
    - API Key
    - 免费套餐（BYOK 无限调用 + 每日 5 次平台 Key 体验）
    """
    from models.user import user_manager
    
    # 检查邮箱格式
    if "@" not in request.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱格式不正确"
        )
    
    # 创建用户
    user = user_manager.create_user(request.email, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    logger.info(f"New user registered: {request.email}")
    
    return RegisterResponse(
        user_id=user.user_id,
        email=user.email,
        api_key=user.api_key,
        plan=user.plan,
        message="注册成功！您可以使用自己的 API Key（BYOK 模式），或每日体验 5 次免费 DeepSeek。"
    )


@app.post("/v1/auth/login", response_model=LoginResponse, tags=["认证"])
async def login(request: LoginRequest):
    """
    用户登录
    
    登录成功后返回 JWT Token，可用于 API 认证。
    """
    from models.user import user_manager
    
    user = user_manager.authenticate(request.email, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )
    
    # 生成 JWT Token
    token = create_access_token(user.user_id, user.plan)
    
    return LoginResponse(
        access_token=token,
        user_id=user.user_id,
        email=user.email,
        plan=user.plan
    )


# ==================== BYOK API Key 管理 ====================

@app.post("/v1/user/api-keys", response_model=ApiKeyResponse, tags=["BYOK"])
async def set_user_api_key(
    request: SetApiKeyRequest,
    user: dict = Depends(get_current_user_optional)
):
    """
    设置用户的 BYOK API Key
    
    支持的 Provider:
    - openai: OpenAI API
    - anthropic: Anthropic API (Claude)
    - deepseek: DeepSeek API
    - gemini: Google Gemini API
    
    您的 Key 将被加密存储，我们无法访问您的明文 Key。
    """
    valid_providers = ["openai", "anthropic", "deepseek", "gemini"]
    if request.provider.lower() not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的 Provider: {request.provider}。支持: {', '.join(valid_providers)}"
        )
    
    if not request.api_key or len(request.api_key) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API Key 格式不正确"
        )
    
    # 加密存储
    encrypted_key = key_encryptor.encrypt(request.api_key)
    set_user_byok_key(user["user_id"], request.provider.lower(), encrypted_key)
    
    logger.info(f"User {user['user_id']} set BYOK key for {request.provider}")
    
    return ApiKeyResponse(
        provider=request.provider.lower(),
        masked_key=mask_api_key(request.api_key),
        is_set=True
    )


@app.get("/v1/user/api-keys", response_model=List[ApiKeyResponse], tags=["BYOK"])
async def list_user_api_keys(user: dict = Depends(get_current_user_optional)):
    """
    获取用户已设置的 BYOK API Keys（脱敏显示）
    """
    all_keys = get_user_all_byok_keys(user["user_id"])
    
    return [
        ApiKeyResponse(
            provider=provider,
            masked_key=mask_api_key(key_encryptor.decrypt(encrypted_key)),
            is_set=True
        )
        for provider, encrypted_key in all_keys.items()
    ]


@app.delete("/v1/user/api-keys/{provider}", tags=["BYOK"])
async def delete_user_api_key(
    provider: str,
    user: dict = Depends(get_current_user_optional)
):
    """
    删除用户的 BYOK API Key
    """
    valid_providers = ["openai", "anthropic", "deepseek", "gemini"]
    if provider.lower() not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的 Provider: {provider}"
        )
    
    deleted = delete_user_byok_key(user["user_id"], provider.lower())
    
    if deleted:
        logger.info(f"User {user['user_id']} deleted BYOK key for {provider}")
        return {"message": f"已删除 {provider} 的 API Key"}
    else:
        return {"message": f"{provider} 没有设置 API Key"}


@app.get("/v1/user/free-trial", response_model=FreeTrialResponse, tags=["BYOK"])
async def get_free_trial_status(user: dict = Depends(get_current_user_optional)):
    """
    获取免费体验状态
    
    每日 5 次 DeepSeek 免费体验（使用平台 Key）
    """
    used = get_free_trial_count(user["user_id"])
    return FreeTrialResponse(
        daily_limit=5,
        used=used,
        remaining=max(0, 5 - used)
    )


# ==================== 辅助函数 ====================

def get_current_user_optional(user_id: str = None) -> dict:
    """从 Header 获取当前用户（可选，用于管理自己的 BYOK Keys）"""
    from utils.auth import get_current_user
    try:
        return get_current_user(user_id)
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请提供有效的认证信息"
        )


# ==================== 注册业务路由 ====================

app.include_router(chat.router)
app.include_router(content.router)
app.include_router(code.router)
app.include_router(data.router)
app.include_router(billing.router)
app.include_router(admin.router)


# ==================== 健康检查 ====================

@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """系统健康检查"""
    from datetime import datetime
    
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        timestamp=datetime.now().isoformat()
    )


@app.get("/", tags=["系统"])
async def root():
    """根路径"""
    return {
        "name": "AI API Gateway",
        "version": "2.0.0",
        "mode": "BYOK",
        "docs": "/docs",
        "description": "智能路由聚合网关 - 支持自带 API Key"
    }


# ==================== 错误处理 ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "type": "http_exception"
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """通用异常处理"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": 500,
                "message": "服务器内部错误",
                "type": "internal_error"
            }
        }
    )


# ==================== 启动事件 ====================

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("=" * 50)
    logger.info("AI API Gateway (BYOK Mode) 启动中...")
    logger.info(f"调试模式: {settings.debug}")
    logger.info(f"数据目录: {settings.data_dir}")
    logger.info("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("AI API Gateway 关闭中...")


# ==================== 主程序入口 ====================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
