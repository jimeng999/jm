# AI API Gateway - Vercel Serverless 版本

🚀 基于 Vercel Serverless Functions 的 AI API 聚合网关

## 一键部署

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/jimeng999/jm&redirect=ai-api-gateway&branch=ai-api-gateway)

## 功能特性

- **多模型聚合** - 统一接入 OpenAI、Anthropic、DeepSeek、Google Gemini
- **智能路由** - 根据任务类型自动选择最优模型
- **OpenAI 兼容** - 兼容 OpenAI API 格式
- **认证计费** - API Key 认证 + 用量统计
- **Serverless 架构** - 零服务器维护，按需付费

## 快速部署

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/jimeng999/ai-api-gateway)

### 或手动部署

1. Fork 本仓库
2. 在 Vercel Dashboard 导入项目
3. 配置环境变量：
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `DEEPSEEK_API_KEY`
   - `GEMINI_API_KEY`
   - `JWT_SECRET_KEY`
4. Deploy!

## API 端点

### 认证

| 端点 | 方法 | 描述 |
|------|------|------|
| `/v1/auth/register` | POST | 用户注册 |
| `/v1/auth/login` | POST | 用户登录 |

### 对话

| 端点 | 方法 | 描述 |
|------|------|------|
| `/v1/chat/completions` | POST | 聊天补全 |

### 其他

| 端点 | 方法 | 描述 |
|------|------|------|
| `/v1/models` | GET | 获取可用模型 |
| `/v1/billing/usage` | GET | 获取用量统计 |
| `/health` | GET | 健康检查 |

## 使用示例

### 注册

```bash
curl -X POST https://your-domain.vercel.app/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

### 聊天

```bash
curl -X POST https://your-domain.vercel.app/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Hello, world!"}]
  }'
```

## 技术栈

- **Runtime**: Vercel Python Runtime
- **HTTP Client**: httpx
- **认证**: JWT (python-jose)

## License

MIT
