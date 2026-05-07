"""
AI API Gateway - 主入口文件 (BYOK + x402 版本)
智能路由聚合网关系统 - 支持 Bring Your Own Key 模式 + x402 按请求付费
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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
## 智能路由聚合网关 - BYOK + x402 模式

通过 Bring Your Own Key (BYOK) 模式，让用户使用自己的 API Key，平台赚取工具层费用。
支持 x402 协议，实现按请求用 USDC 实时结算。

### 核心功能

1. **BYOK 模式** - 用户自带 API Key，零中间差价
2. **平台 Key 兜底** - 无 Key 用户使用平台 Key，按量加价 30%
3. **x402 按次付费** - 用 USDC 稳定币在 Base 链上按请求实时结算
4. **免费体验** - 每日 5 次 DeepSeek 免费体验
5. **智能路由** - Pro 用户享有多模型智能路由

### 认证优先级

1. 有 API Key → 走 BYOK
2. 无 API Key + x402 启用 → 返回 HTTP 402
3. 有 PAYMENT-SIGNATURE → 走 x402 验证 → 返回数据

### 商业模式

- **BYOK 模式**：用户用自己的 Key，平台不赚差价
- **平台 Key**：无 BYOK 时使用平台 Key，加价 30%
- **x402 按次付费**：无需注册，用 USDC 按请求实时结算
- **Pro 订阅**：¥49/月，智能路由 + 用量分析
    """,
    version="2.1.0",
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
    expose_headers=["PAYMENT-REQUIRED", "PAYMENT-RESPONSE"],
)


# ==================== x402 中间件 ====================

@app.middleware("http")
async def x402_middleware(request: Request, call_next):
    """
    x402 支付协议中间件
    
    认证优先级：
    1. 有 Authorization header → 走 BYOK（放行，由路由层验证）
    2. 非 API 端点（/docs, /health 等）→ 直接放行
    3. x402 未启用 → 直接放行（走原有逻辑）
    4. 有 PAYMENT-SIGNATURE header → 验证支付
    5. 无任何认证 → 返回 HTTP 402 + PAYMENT-REQUIRED
    """
    from services.x402 import x402_service
    
    # 非 API 路径直接放行
    path = request.url.path
    non_api_paths = ["/", "/health", "/docs", "/redoc", "/openapi.json", "/landing"]
    if path in non_api_paths or path.startswith("/v1/auth"):
        return await call_next(request)
    
    # 有 Authorization header → 走 BYOK，放行
    auth_header = request.headers.get("Authorization")
    if auth_header:
        return await call_next(request)
    
    # x402 未启用 → 放行（走原有逻辑，会返回 401）
    if not x402_service.is_enabled():
        return await call_next(request)
    
    # 检查 PAYMENT-SIGNATURE
    payment_signature = request.headers.get("PAYMENT-SIGNATURE")
    
    if not payment_signature:
        # 无支付签名 → 返回 402 + PAYMENT-REQUIRED
        # 尝试从请求中获取 model（仅用于定价）
        model = request.headers.get("X-Model", "gpt-4o-mini")
        response_body, headers = x402_service.build_payment_required_response(
            resource=path,
            model=model
        )
        return JSONResponse(
            status_code=402,
            content=response_body,
            headers=headers
        )
    
    # 有支付签名 → 验证
    model = request.headers.get("X-Model", "gpt-4o-mini")
    is_valid, verification = await x402_service.verify_payment(
        payment_signature=payment_signature,
        resource=path,
        model=model
    )
    
    if is_valid:
        # 验证通过 → 放行，附加 x402 用户信息到 request state
        request.state.x402_user = {
            "user_id": f"x402_anonymous",
            "plan": "x402",
            "auth_method": "x402",
            "verification": verification
        }
        # 添加 PAYMENT-RESPONSE header
        response = await call_next(request)
        payment_response = x402_service.build_payment_response_header(verification)
        response.headers["PAYMENT-RESPONSE"] = payment_response
        return response
    else:
        # 验证失败 → 返回 402
        response_body, headers = x402_service.build_payment_required_response(
            resource=path,
            model=model
        )
        return JSONResponse(
            status_code=402,
            content=response_body,
            headers=headers
        )


# ==================== 辅助函数 ====================

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    )
) -> dict:
    """从 Header 获取当前用户（可选，用于管理自己的 BYOK Keys）"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请提供有效的认证信息"
        )
    from utils.auth import get_current_user
    return await get_current_user(credentials)


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
    from services.x402 import x402_service
    
    return HealthResponse(
        status="healthy",
        version="2.1.0",
        timestamp=datetime.now().isoformat()
    )


@app.get("/", tags=["系统"])
async def root():
    """根路径"""
    from services.x402 import x402_service
    
    return {
        "name": "AI API Gateway",
        "version": "2.1.0",
        "mode": "BYOK + x402",
        "docs": "/docs",
        "x402_enabled": x402_service.is_enabled(),
        "description": "智能路由聚合网关 - 支持自带 API Key 和 x402 按次付费"
    }


# ==================== Landing Page ====================

@app.get("/landing", tags=["系统"], response_class=HTMLResponse)
async def landing_page():
    """Landing Page"""
    landing_path = Path(__file__).parent / "landing-page" / "index.html"
    if landing_path.exists():
        return FileResponse(landing_path, media_type="text/html")
    return HTMLResponse("<h1>Landing page not found</h1>", status_code=404)


# ==================== x402 端点定价查询 ====================

@app.get("/v1/x402/pricing", tags=["x402"])
async def get_x402_pricing():
    """获取 x402 按请求付费定价表"""
    from services.x402 import x402_service
    from config import model_config
    
    if not x402_service.is_enabled():
        return {
            "enabled": False,
            "message": "x402 支付协议未启用。设置 X402_ENABLED=true 开启。"
        }
    
    return {
        "enabled": True,
        "network": x402_service.network,
        "asset": x402_service.usdc_contract,
        "payTo": x402_service.wallet_address,
        "pricing": model_config.X402_PRICING
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
    from services.x402 import x402_service
    
    logger.info("=" * 50)
    logger.info("AI API Gateway (BYOK + x402 Mode) 启动中...")
    logger.info(f"调试模式: {settings.debug}")
    logger.info(f"数据目录: {settings.data_dir}")
    logger.info(f"x402 支付协议: {'启用' if x402_service.is_enabled() else '禁用'}")
    if x402_service.is_enabled():
        logger.info(f"x402 收款钱包: {x402_service.wallet_address}")
        logger.info(f"x402 网络: {x402_service.network}")
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
