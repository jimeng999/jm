"""
Vercel Serverless API Handler
AI API Gateway - BYOK 版本
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入 FastAPI 应用
from main import app

# Vercel Serverless Handler
handler = app
