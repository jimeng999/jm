"""
AI API Gateway - 主入口文件
智能路由聚合网关系统
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

from config import settings
from utils.logger import logger
from utils.auth import create_access_token, hash_password, verify_password

# 导入所有路由
from routers import chat, content, code, data, billing, admin


# ==================== FastAPI 应用初始化 ====================

app = FastAPI(
    title="AI API Gateway",
    description="""
## 智能路由聚合网关

通过智能模型路由 + 垂直能力封装，打造高利润 AI API 服务。

### 核心功能

1. **多模型聚合** - 统一接入 OpenAI、Anthropic、DeepSeek、Google Gemini
2. **智能路由** - 根据任务复杂度自动选择最优模型
3. **垂直 API** - 内容创作、代码审查、数据分析等高毛利 SaaS
4. **计费系统** - Token 计费 + 按结果计费双重模式

### 商业模式

- **API 聚合中转**（过路费模式）- 统一接入多模型，按 Token 计费抽成
- **垂直能力封装**（高毛利 SaaS）- 按结果收费，毛利率 85-97%
    """,
    version="1.0.0",
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


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    timestamp: str


# ==================== 路由注册 ====================

# 认证相关路由
@app.post("/v1/auth/register", response_model=RegisterResponse, tags=["认证"])
async def register(request: RegisterRequest):
    """
    用户注册
    
    注册后自动获得：
    - API Key
    - 免费套餐（100次/天，仅 GPT-4o-mini）
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
        message="注册成功！您的免费套餐已激活，每天100次请求额度。"
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


# 注册业务路由
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
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )


@app.get("/", tags=["系统"])
async def root():
    """根路径"""
    return {
        "name": "AI API Gateway",
        "version": "1.0.0",
        "docs": "/docs",
        "description": "智能路由聚合网关系统"
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
    logger.info("AI API Gateway 启动中...")
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
