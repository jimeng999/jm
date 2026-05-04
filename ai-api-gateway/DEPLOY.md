# 🚀 AI API Gateway 部署指南

本文档详细说明如何将 AI API Gateway 部署到 Render 免费层。

## 目录

- [快速部署](#快速部署)
- [详细步骤](#详细步骤)
- [环境变量配置](#环境变量配置)
- [注意事项](#注意事项)
- [验证部署](#验证部署)

---

## 快速部署

### 一键部署按钮

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/new?repo=https://github.com/jimeng999/jm)

点击上方按钮，跳转到 Render 并自动配置（需要手动设置 Root Directory）。

---

## 详细步骤

### 第一步：准备 GitHub 仓库

代码已推送到: https://github.com/jimeng999/jm/tree/main/ai-api-gateway

### 第二步：登录 Render

1. 访问 [render.com](https://render.com)
2. 点击 "Sign In" 使用 GitHub 账号登录
3. 授权 Render 访问你的 GitHub 仓库

### 第三步：创建 Web Service

1. 点击 Dashboard 的 **"New +"** 按钮
2. 选择 **"Web Service"**
3. 在 "Connect a repository" 页面:
   - 选择 GitHub 账号
   - 搜索并选择 `jimeng999/jm` 仓库
   - 点击 **"Connect"**

### 第四步：配置服务

在 Web Service 配置页面填写以下内容：

| 配置项 | 值 |
|--------|-----|
| **Name** | `ai-api-gateway` |
| **Language** | `Python 3` |
| **Root Directory** | `ai-api-gateway` |
| **Region** | Singapore (或离你最近的) |
| **Branch** | `main` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | `Free` |

### 第五步：设置环境变量

点击 "Environment" 部分，添加以下环境变量：

#### 必需的环境变量

| 变量名 | 示例值 | 说明 |
|--------|--------|------|
| `OPENAI_API_KEY` | `sk-xxx...` | OpenAI API Key |
| `ANTHROPIC_API_KEY` | `sk-ant-xxx...` | Anthropic API Key |
| `DEEPSEEK_API_KEY` | `sk-xxx...` | DeepSeek API Key |
| `GEMINI_API_KEY` | `xxx...` | Google Gemini API Key |
| `JWT_SECRET_KEY` | `your-secret-key-here` | JWT 密钥（生成随机字符串） |
| `ENVIRONMENT` | `production` | 运行环境 |

#### 可选的环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `RATE_LIMIT_PER_MINUTE` | `60` | 每分钟请求限制 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `CORS_ORIGINS` | `*` | 允许的 CORS 源 |

### 第六步：创建服务

1. 点击 **"Create Web Service"** 按钮
2. 等待构建完成（约 2-5 分钟）
3. 服务创建成功后，你会获得一个 URL: `https://ai-api-gateway.onrender.com`

---

## 环境变量配置

### 生成 JWT Secret

```bash
# 方式1: 使用 Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 方式2: 使用 openssl
openssl rand -base64 32
```

### API Keys 获取

| 服务 | 获取地址 |
|------|----------|
| OpenAI | https://platform.openai.com/api-keys |
| Anthropic | https://console.anthropic.com/settings/keys |
| DeepSeek | https://platform.deepseek.com/api_keys |
| Gemini | https://aistudio.google.com/app/apikey |

---

## 注意事项

### Render 免费层限制

⚠️ **重要限制**:

1. **休眠机制**: 免费实例在 15 分钟无活动后会自动休眠
2. **冷启动**: 休眠后首次请求需要等待 30 秒 - 1 分钟启动
3. **睡眠时间**: 每月有 750 小时的免费时间（约 31 天）
4. **带宽限制**: 每月 100GB 传出带宽
5. **无持久化**: 无法使用文件系统存储数据

### 适合场景

- ✅ 开发测试
- ✅ 小规模演示
- ✅ 个人项目
- ✅ 初期验证 MVP

### 不适合场景

- ❌ 需要 24/7 在线服务
- ❌ 高并发访问
- ❌ 需要数据库持久化
- ❌ 生产环境关键业务

---

## 验证部署

### 方法 1: 检查健康状态

```bash
curl https://ai-api-gateway.onrender.com/health
```

预期响应:
```json
{"status":"healthy","timestamp":"2024-01-01T00:00:00Z"}
```

### 方法 2: 访问 API 文档

打开浏览器访问: https://ai-api-gateway.onrender.com/docs

你应该能看到 Swagger UI 文档页面。

### 方法 3: 测试 Chat API

```bash
curl -X POST https://ai-api-gateway.onrender.com/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## 故障排查

### 构建失败

1. 检查 `requirements.txt` 是否包含所有依赖
2. 确保 Python 版本兼容（推荐 3.9+）
3. 查看 Render 构建日志定位问题

### 启动失败

1. 检查环境变量是否正确配置
2. 确认 Start Command 正确
3. 查看 Render 运行时日志

### API 调用超时

1. 免费实例冷启动较慢，这是正常的
2. 可以使用 Keep-alive 请求保持实例活跃
3. 考虑升级到付费实例

---

## 下一步

部署成功后，你可以:

1. 📖 阅读 [API 文档](https://ai-api-gateway.onrender.com/docs)
2. 🔑 创建 API Keys 给用户使用
3. 💰 配置计费和订阅
4. 📊 监控使用量和费用

---

## 相关链接

- 🌐 [Render Dashboard](https://dashboard.render.com)
- 📦 [GitHub 仓库](https://github.com/jimeng999/jm)
- 📚 [FastAPI 文档](https://fastapi.tiangolo.com)
- 💬 [问题反馈](https://github.com/jimeng999/jm/issues)

---

*最后更新: 2024*
