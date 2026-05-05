# 技术社区发帖模板

## V2EX 发帖模板

---

**标题选项**（选一个）：

```
做了一个 AI API Gateway，聚合 GPT-4/Claude/DeepSeek，比官方便宜 30%
开源 + 自部署 | 一个 Key 调用所有主流 LLM，统一计费管理
帮大家省点 API 钱，我们做了个 AI 网关，支持 OpenAI 兼容格式
```

---

**正文**：

```
大家好，

最近被各个 AI 厂商的 API Key 管理折腾得够呛，索性自己写了个网关。

## 解决的问题

1. **多 Key 管理混乱** - 一个平台搞定所有模型
2. **成本不透明** - 统一计费明细，清楚知道每分钱花在哪
3. **想换模型要改代码** - OpenAI 兼容格式，切换模型只需要改个参数

## 核心功能

- 支持：OpenAI GPT-4/4o、Claude 3.5、DeepSeek V3、通义千问、GLM-4...
- 统一 OpenAI SDK 格式，代码零改动迁移
- 按量计费，比原厂便宜 20-30%
- 支持 Token 计费池，多模型共享额度
- 开源可自部署（Docker 一键部署）

## 价格

| 套餐 | 价格 | 说明 |
|------|------|------|
| 免费版 | 0 | 100次/天 |
| 开发者版 | $29/月 | 无限调用，20%官方价格折扣 |
| 团队版 | $99/月 | 5人协作，API Key 管理 |

## 演示

Dashboard：[截图]

API 示例：
```python
# 原来用 OpenAI
from openai import OpenAI
client = OpenAI(api_key="sk-xxx")

# 现在只需要换 base_url 和 api_key
client = OpenAI(
    api_key="your-gateway-key",  # 我们平台的 Key
    base_url="https://api.xxx.com/v1"  # 接入点
)
# 模型随便换，代码一行不用改
```

## 开源地址

GitHub: https://github.com/xxx/ai-api-gateway

## 问

大家有什么想了解的，可以在评论区聊。

目前在内测阶段，欢迎来玩~
```

---

## 掘金发帖模板

**标题**：
```
【开源】做了一个聚合所有主流LLM的API网关，成本直降30%
```

**正文**：

```
# 背景

最近在做 AI 应用开发，深感多平台 API 管理之苦：
- OpenAI 的 Key、Anthropic 的 Key、DeepSeek 的 Key...
- 每个平台计费方式不一样，月底对账头疼
- 想切换模型？代码改一堆

于是花了周末两天，写了个 AI Gateway。

# 功能

## 支持的模型
- OpenAI: GPT-4, GPT-4o, GPT-3.5
- Anthropic: Claude 3.5 Sonnet, Claude 3 Opus
- DeepSeek: DeepSeek V3, DeepSeek Coder
- 阿里: 通义千问 Qwen
- 智谱: GLM-4

## 统一接口

```python
from openai import OpenAI

client = OpenAI(
    api_key="gateway-api-key",  # 一个 Key
    base_url="https://api.yours.com/v1"
)

# 换模型只需要改模型名
response = client.chat.completions.create(
    model="gpt-4",  # 或 claude-3-5-sonnet，或 deepseek-v3
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## 成本对比

| 模型 | 官方价格 | 我们的价格 | 节省 |
|------|----------|------------|------|
| GPT-4 | $0.03/1K | $0.024/1K | 20% |
| Claude 3.5 | $0.003/1K | $0.0024/1K | 20% |
| DeepSeek V3 | $0.001/1K | $0.0008/1K | 20% |

# 自部署

```bash
docker run -d -p 8080:8080 \
  -e OPENAI_API_KEY=sk-xxx \
  -e ANTHROPIC_API_KEY=sk-ant-xxx \
  your-gateway:latest
```

# 后续计划

- [ ] 多租户隔离
- [ ] Token 计费池
- [ ] WebSocket 流式输出
- [ ] 企业版私有化部署

---

欢迎 Star，欢迎来玩，有问题评论区见。
```

---

## 发帖注意事项

### V2EX
- 不要太营销化，用"帮大家"语气
- 贴代码演示，体现技术含量
- 评论区要积极回复

### 掘金
- 文章要有干货（技术实现细节）
- 可以贴架构图增加说服力
- 标签选：AI、Python、OpenAI、API

### 通用
- 避免"颠覆"、"革命性"等词汇
- 客观描述功能和价格
- 欢迎提出问题，展现团队响应力
