# 部署到 Vercel

## 方法一：GitHub Actions 自动部署（推荐）

### 步骤 1: 获取 Vercel 凭证

1. 登录 [Vercel Dashboard](https://vercel.com/dashboard)
2. 进入 Settings → Tokens
3. 创建一个新的 Token，复制保存

### 步骤 2: 获取 Vercel 组织 ID 和项目 ID

```bash
# 安装 Vercel CLI
npm install -g vercel

# 登录
vercel login

# 在项目目录执行
cd vercel-ai-gateway
vercel link
vercel env pull
```

或者直接在 Vercel Dashboard:
- 组织 ID: Settings → General → Team ID
- 项目 ID: Settings → General → Project ID

### 步骤 3: 配置 GitHub Secrets

在 GitHub 仓库 Settings → Secrets 中添加:

| Secret Name | Value |
|-------------|-------|
| VERCEL_TOKEN | 你的 Vercel Token |
| VERCEL_ORG_ID | 你的 Team ID (格式: team_xxx) |
| VERCEL_PROJECT_ID | 你的 Project ID |
| GH_PAT | GitHub Personal Access Token (repo 权限) |

### 步骤 4: 触发部署

推送代码到 `ai-api-gateway` 分支即可自动部署:

```bash
git push origin master:ai-api-gateway
```

---

## 方法二：手动部署

### 步骤 1: 在 Vercel 导入项目

1. 访问 https://vercel.com/new
2. 选择 "Import Git Repository"
3. 选择 `jimeng999/jm` 仓库
4. 选择 `ai-api-gateway` 分支

### 步骤 2: 配置项目

- **Framework Preset**: Other
- **Root Directory**: ./ (或保持默认)
- **Build Command**: 无需（Python 无需构建）

### 步骤 3: 配置环境变量

在 Vercel Dashboard → Settings → Environment Variables 添加:

| Name | Value |
|------|-------|
| OPENAI_API_KEY | your-openai-key |
| ANTHROPIC_API_KEY | your-anthropic-key |
| DEEPSEEK_API_KEY | your-deepseek-key |
| GEMINI_API_KEY | your-gemini-key |
| JWT_SECRET_KEY | your-secret-key (随机字符串) |

### 步骤 4: 部署

点击 "Deploy" 按钮即可。

---

## 方法三：Vercel CLI 部署

```bash
# 安装
npm install -g vercel

# 登录
vercel login

# 进入目录
cd vercel-ai-gateway

# 部署预览
vercel

# 部署生产
vercel --prod
```

---

## 部署后配置

部署成功后，访问 `https://your-project.vercel.app/health` 确认服务正常。

### API 端点

- 注册: `POST /v1/auth/register`
- 登录: `POST /v1/auth/login`
- 聊天: `POST /v1/chat/completions`
- 模型列表: `GET /v1/models`
- 用量查询: `GET /v1/billing/usage`
