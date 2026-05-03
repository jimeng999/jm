#!/bin/bash
# ============================================
# AI API Gateway 一键部署脚本
# 支持三种部署方式：Railway / Fly.io / Docker
# ============================================

set -e

echo "🚀 AI API Gateway 部署脚本"
echo "============================"
echo ""
echo "请选择部署方式："
echo "  1) Railway (推荐，免费起步，自动CI/CD)"
echo "  2) Fly.io (全球边缘部署，按用量计费)"
echo "  3) Docker (自有服务器/VPS)"
echo "  4) 本地测试运行"
echo ""
read -p "输入选择 [1-4]: " choice

case $choice in
  1)
    echo ""
    echo "📦 部署到 Railway..."
    echo ""
    echo "前置条件："
    echo "  - 安装 Railway CLI: npm install -g @railway/cli"
    echo "  - 注册 Railway 账号: https://railway.app"
    echo ""
    
    # 检查 Railway CLI
    if ! command -v railway &> /dev/null; then
      echo "❌ 未安装 Railway CLI，正在安装..."
      npm install -g @railway/cli
    fi
    
    # 登录
    echo "🔐 登录 Railway..."
    railway login
    
    # 初始化项目
    echo "📋 初始化项目..."
    railway init
    
    # 设置环境变量
    echo "⚙️  配置环境变量..."
    read -p "输入 OpenAI API Key: " OPENAI_KEY
    read -p "输入 Anthropic API Key (可选): " ANTHROPIC_KEY
    read -p "输入 DeepSeek API Key (可选): " DEEPSEEK_KEY
    read -p "输入 Gemini API Key (可选): " GEMINI_KEY
    
    railway variables set OPENAI_API_KEY="$OPENAI_KEY"
    [ -n "$ANTHROPIC_KEY" ] && railway variables set ANTHROPIC_API_KEY="$ANTHROPIC_KEY"
    [ -n "$DEEPSEEK_KEY" ] && railway variables set DEEPSEEK_API_KEY="$DEEPSEEK_KEY"
    [ -n "$GEMINI_KEY" ] && railway variables set GEMINI_API_KEY="$GEMINI_KEY"
    railway variables set JWT_SECRET="$(openssl rand -hex 32)"
    
    # 部署
    echo "🚀 开始部署..."
    railway up
    
    echo ""
    echo "✅ 部署完成！"
    railway domain
    echo ""
    echo "访问以上域名即可使用 API"
    ;;

  2)
    echo ""
    echo "📦 部署到 Fly.io..."
    echo ""
    echo "前置条件："
    echo "  - 安装 Fly CLI: curl -L https://fly.io/install.sh | sh"
    echo "  - 注册 Fly.io 账号: https://fly.io"
    echo ""
    
    if ! command -v fly &> /dev/null; then
      echo "❌ 未安装 Fly CLI"
      echo "请先安装: curl -L https://fly.io/install.sh | sh"
      exit 1
    fi
    
    echo "🔐 登录 Fly.io..."
    fly auth login
    
    echo "📋 创建应用..."
    fly apps create ai-api-gateway
    
    echo "⚙️  配置环境变量..."
    read -p "输入 OpenAI API Key: " OPENAI_KEY
    fly secrets set OPENAI_API_KEY="$OPENAI_KEY"
    
    read -p "输入 Anthropic API Key (可选，回车跳过): " ANTHROPIC_KEY
    [ -n "$ANTHROPIC_KEY" ] && fly secrets set ANTHROPIC_API_KEY="$ANTHROPIC_KEY"
    
    fly secrets set JWT_SECRET="$(openssl rand -hex 32)"
    
    echo "🚀 开始部署..."
    fly deploy
    
    echo ""
    echo "✅ 部署完成！"
    echo "API 地址: https://ai-api-gateway.fly.dev"
    ;;

  3)
    echo ""
    echo "📦 Docker 部署（自有服务器）..."
    echo ""
    
    # 检查 .env 文件
    if [ ! -f .env ]; then
      echo "⚙️  创建 .env 配置文件..."
      cp .env.example .env
      
      read -p "输入 OpenAI API Key: " OPENAI_KEY
      sed -i "s/your-openai-api-key/$OPENAI_KEY/" .env
      
      read -p "输入 Anthropic API Key (可选): " ANTHROPIC_KEY
      [ -n "$ANTHROPIC_KEY" ] && sed -i "s/your-anthropic-api-key/$ANTHROPIC_KEY/" .env
      
      read -p "输入 DeepSeek API Key (可选): " DEEPSEEK_KEY
      [ -n "$DEEPSEEK_KEY" ] && sed -i "s/your-deepseek-api-key/$DEEPSEEK_KEY/" .env
      
      read -p "输入 Gemini API Key (可选): " GEMINI_KEY
      [ -n "$GEMINI_KEY" ] && sed -i "s/your-gemini-api-key/$GEMINI_KEY/" .env
      
      # 生成随机 JWT Secret
      JWT_SECRET=$(openssl rand -hex 32)
      sed -i "s/change-me-in-production/$JWT_SECRET/" .env
    fi
    
    echo "🔨 构建 Docker 镜像..."
    docker compose build
    
    echo "🚀 启动服务..."
    docker compose up -d
    
    echo ""
    echo "✅ 部署完成！"
    echo "API 地址: http://localhost:8000"
    echo "API 文档: http://localhost:8000/docs"
    echo ""
    echo "查看日志: docker compose logs -f"
    echo "停止服务: docker compose down"
    ;;

  4)
    echo ""
    echo "📦 本地测试运行..."
    echo ""
    
    # 检查 .env
    if [ ! -f .env ]; then
      echo "⚠️  未找到 .env 文件，使用默认配置"
      cp .env.example .env
    fi
    
    echo "🚀 启动开发服务器..."
    echo "API 地址: http://localhost:8000"
    echo "API 文档: http://localhost:8000/docs"
    echo ""
    echo "按 Ctrl+C 停止"
    echo ""
    
    uvicorn main:app --reload --port 8000
    ;;

  *)
    echo "无效选择"
    exit 1
    ;;
esac
