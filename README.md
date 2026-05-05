# AI API Gateway - 智能路由聚合网关

> 通过智能模型路由 + 垂直能力封装，打造高利润 AI API 服务

## 🚀 项目概述

这是一个**可赚钱的 AI API 聚合网关系统**，核心商业模式包括：

1. **API 聚合中转**（过路费模式）- 统一接入多模型，按 Token 计费抽成
2. **垂直能力封装**（高毛利 SaaS）- 按结果收费，毛利率 85-97%

### 参考案例
- **OpenRouter**: 仅靠 5% 抽成年赚 500 万美元
- **国内头部中转站**: 日交易额过百万
- **垂直 AI SaaS**: 毛利率可达 85-96%

## 💰 定价策略

### 订阅套餐

| 层级 | 价格 | 包含内容 |
|------|------|----------|
| **免费层** | ¥0 | 100次/天，仅 GPT-4o-mini |
| **基础层** | ¥99/月 | 1000次/天，GPT-4o + Claude Sonnet |
| **专业层** | ¥299/月 | 5000次/天，全部模型 + 垂直API |
| **企业层** | ¥999/月 | 无限制 + 专属模型 + SLA + 优先支持 |

### 按量计费（Token 模式）

| 模型 | 输入价格 | 输出价格 | 推荐用途 |
|------|----------|----------|----------|
| GPT-4o-mini | $0.15/1M | $0.60/1M | 简单任务、对话 |
| GPT-4o | $2.5/1M | $10/1M | 复杂任务 |
| Claude-3.5-Sonnet | $3/1M | $15/1M | 编程、分析 |
| DeepSeek-V3 | $0.14/1M | $0.28/1M | 性价比首选 |
| Gemini-1.5-Pro | $1.25/1M | $5/1M | 长上下文 |

### 垂直 API（按结果收费）

| API 端点 | 计费方式 | 建议售价 | 成本估算 | 毛利率 |
|----------|----------|----------|----------|--------|
| `/v1/content/write` | 按篇 | ¥5-20/篇 | ¥0.5-2 | 85-96% |
| `/v1/code/review` | 按次 | ¥3-15/次 | ¥0.3-1 | 87-97% |
| `/v1/data/analyze` | 按报告 | ¥50-200/报告 | ¥5-20 | 85-95% |
| `/v1/chat/smart` | 按轮次 | ¥0.5-2/轮 | ¥0.05-0.2 | 87-97% |

## 📊 利润测算

```
用户月费 ¥299
├── 平均 Token 成本: ¥5-15
├── API 调用成本: ¥3-10
└── 净利润: ¥270-285 (90-95%)

100 个付费用户 = 月收入 ¥29,700-31,350
1000 个付费用户 = 月收入 ¥297,000-313,500
```

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      客户端                              │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                   API Gateway (FastAPI)                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │ /chat   │ │/content │ │ /code   │ │ /data   │       │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                   智能路由层                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Model Router (自动选模型)            │   │
│  │  简单任务 → 便宜模型    复杂任务 → 强模型         │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                   模型供应商层                            │
│  ┌──────┐ ┌─────────┐ ┌────────┐ ┌────────┐            │
│  │OpenAI│ │Anthropic│ │DeepSeek│ │ Gemini │            │
│  └──────┘ └─────────┘ └────────┘ └────────┘            │
└─────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
AI-API-Gateway/
├── README.md              # 本文件
├── requirements.txt       # Python 依赖
├── .env.example           # 环境变量模板
├── main.py                # FastAPI 入口
├── config.py              # 配置管理
├── routers/
│   ├── chat.py            # 通用对话 API
│   ├── content.py         # 内容创作 API
│   ├── code.py            # 代码审查 API
│   ├── data.py            # 数据分析 API
│   ├── billing.py         # 计费与套餐 API
│   └── admin.py           # 管理后台 API
├── services/
│   ├── model_router.py    # 智能模型路由
│   ├── billing.py         # 计费逻辑
│   └── prompt_templates.py # 提示词模板
│   └── provider/
│       ├── base.py        # 供应商基类
│       ├── openai.py      # OpenAI 适配
│       ├── anthropic.py   # Anthropic 适配
│       ├── deepseek.py    # DeepSeek 适配
│       └── gemini.py      # Gemini 适配
├── models/
│   ├── user.py            # 用户模型
│   └── usage.py           # 用量模型
└── utils/
    ├── auth.py            # API Key 认证
    └── logger.py          # 日志工具
```

## 🚀 快速部署

### 1. 安装依赖

```bash
cd AI-API-Gateway
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Keys
```

### 3. 启动服务

```bash
# 开发模式
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. API 文档

启动后访问: http://localhost:8000/docs

## 🔑 API 使用示例

### 1. 注册并获取 API Key

```bash
curl -X POST "http://localhost:8000/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

### 2. 通用对话

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### 3. 内容创作

```bash
curl -X POST "http://localhost:8000/v1/content/write" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "article",
    "topic": "AI技术发展趋势",
    "length": "medium",
    "style": "professional"
  }'
```

### 4. 代码审查

```bash
curl -X POST "http://localhost:8000/v1/code/review" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def hello(): print(\"world\")",
    "language": "python",
    "focus_areas": ["security", "performance"]
  }'
```

### 5. 数据分析

```bash
curl -X POST "http://localhost:8000/v1/data/analyze" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "data": "日期,销售额\n2024-01,10000\n2024-02,15000\n2024-03,12000",
    "analysis_type": "trend",
    "report_format": "detailed"
  }'
```

### 6. 余额查询

```bash
curl -X GET "http://localhost:8000/v1/billing/balance" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## 🔧 配置说明

### .env 配置项

```env
# 服务配置
HOST=0.0.0.0
PORT=8000
DEBUG=true

# OpenAI
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx

# DeepSeek
DEEPSEEK_API_KEY=sk-xxx

# Google Gemini
GEMINI_API_KEY=xxx

# 计费配置
TOKEN_RATE_USD=7.2      # USD to CNY rate
MARKUP_RATIO=1.5         # 加价倍率
FREE_TIER_DAILY=100      # 免费层每日限制

# 管理配置
ADMIN_API_KEY=admin_secret_key
```

## 📈 商业化建议

### 1. 初期策略
- 先聚焦 1-2 个垂直场景（如代码审查）
- 积累种子用户，听取反馈
- 快速迭代产品

### 2. 增长策略
- 提供免费额度吸引用户
- 口碑传播 + 技术社区推广
- 差异化定价（企业 vs 个人）

### 3. 成本控制
- 智能路由降低模型成本 40-60%
- 按结果收费规避 Token 波动风险
- 缓存热门结果减少重复调用

### 4. 扩展方向
- 添加更多 AI 供应商
- 开发更多垂直 API
- 支持私有化部署
- 企业定制服务

## ⚠️ 注意事项

1. **API Key 安全**: 生产环境务必使用 HTTPS
2. **限流保护**: 建议接入 Redis 实现分布式限流
3. **数据存储**: 当前使用 JSON 文件，生产环境建议迁移到数据库
4. **成本监控**: 建议接入监控告警，防止滥用

## 📄 License

MIT License
