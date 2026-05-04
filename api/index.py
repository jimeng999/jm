"""
Vercel Serverless Function 入口
AI API Gateway - 智能路由聚合网关
"""
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# 添加app目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import app
from app.utils.auth import verify_api_key, decode_access_token

# Vercel Python runtime 需要这个 handler
def handler(request, context=None):
    """
    Vercel Serverless Function handler
    
    Args:
        request: Vercel 请求对象
        context: Vercel 上下文（可选）
    
    Returns:
        Response对象
    """
    return app(request, context)


# 为了兼容不同的调用方式，也导出 ASGI 应用
app_handler = app
