"""
认证与授权工具模块
支持 BYOK + x402 支付协议
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import HTTPException, Request, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from config import settings


# HTTP Bearer 安全方案
security = HTTPBearer()


def generate_api_key() -> str:
    """生成 API Key"""
    random_bytes = secrets.token_bytes(32)
    return f"sk-{random_bytes.hex()}"


def generate_user_id() -> str:
    """生成用户 ID"""
    return f"user_{secrets.token_hex(16)}"


def hash_password(password: str) -> str:
    """哈希密码"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}${pwd_hash.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    try:
        salt, pwd_hash = hashed.split('$')
        new_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return new_hash.hex() == pwd_hash
    except Exception:
        return False


def create_access_token(user_id: str, plan: str = "free") -> str:
    """创建访问令牌"""
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    
    to_encode = {
        "sub": user_id,
        "plan": plan,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """解码访问令牌"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_api_key(api_key: str) -> Optional[dict]:
    """
    验证 API Key
    实际从数据库/文件读取用户信息验证
    返回 dict 格式
    """
    from models.user import UserManager
    
    # 格式检查
    if not api_key or not api_key.startswith("sk-"):
        return None
    
    # 查询用户
    user_manager = UserManager()
    user_obj = user_manager.get_user_by_api_key(api_key)
    
    if not user_obj:
        return None
    
    # 统一转 dict（兼容 Pydantic Model 和 dict）
    if hasattr(user_obj, "to_dict"):
        return user_obj.to_dict()
    elif hasattr(user_obj, "model_dump"):
        return user_obj.model_dump()
    return dict(user_obj)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    获取当前用户依赖
    用于 FastAPI 路由保护
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        
        # 优先验证 JWT token
        if token.startswith("eyJ"):  # JWT token 特征
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if user_id is None:
                raise credentials_exception
        else:
            # 验证 API Key
            user_data = verify_api_key(token)
            if user_data is None:
                raise credentials_exception
            user_id = user_data.get("user_id")
            return user_data
            
    except (JWTError, Exception) as e:
        raise credentials_exception
    
    # 获取完整用户数据
    from models.user import UserManager
    user_manager = UserManager()
    user_data = user_manager.get_user(user_id)
    
    if user_data is None:
        raise credentials_exception
    
    return user_data


async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(
    HTTPBearer(auto_error=False)
)) -> Optional[dict]:
    """
    可选的获取当前用户
    不强制要求认证
    """
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        if token.startswith("eyJ"):
            payload = decode_access_token(token)
            user_id = payload.get("sub")
        else:
            user_data = verify_api_key(token)
            return user_data
            
        from models.user import UserManager
        user_manager = UserManager()
        return user_manager.get_user(user_id)
    except Exception:
        return None


def verify_admin(api_key: str) -> bool:
    """验证管理员权限"""
    return api_key == settings.admin_api_key


async def get_x402_user(request: Request) -> Optional[dict]:
    """
    从 x402 支付签名中获取用户身份
    
    认证优先级：
    1. 有 API Key → 走 BYOK
    2. 无 API Key + x402 启用 → 检查 PAYMENT-SIGNATURE header
    3. 有 PAYMENT-SIGNATURE → 走 x402 验证
    4. 无 PAYMENT-SIGNATURE → 返回 None（由路由层返回 402）
    
    返回: 验证通过返回 x402 用户 dict，否则返回 None
    """
    from services.x402 import x402_service
    
    if not x402_service.is_enabled():
        return None
    
    payment_signature = request.headers.get("PAYMENT-SIGNATURE")
    if not payment_signature:
        return None
    
    # 确定请求的资源路径和模型
    resource = request.url.path
    
    # 尝试从请求体获取模型名称（用于定价）
    model = "gpt-4o-mini"  # 默认模型
    try:
        # 读取 body（需要特殊处理，因为 request body 只能读一次）
        # 这里用 query param 或 header 传递 model
        model = request.headers.get("X-Model", "gpt-4o-mini")
    except Exception:
        pass
    
    # 验证支付
    is_valid, verification = await x402_service.verify_payment(
        payment_signature=payment_signature,
        resource=resource,
        model=model
    )
    
    if is_valid:
        return {
            "user_id": f"x402_{verification.get('payer', 'anonymous')}",
            "plan": "x402",
            "auth_method": "x402",
            "model": model,
            "verification": verification
        }
    
    return None
