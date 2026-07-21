# OMKA - Oh My Knowledge Assistant

> 可追踪、可学习、可主动执行的个人知识 Agent

## 为什么做这个项目

作为开发者，我们每天面对海量的 GitHub 更新——新仓库、新 Release、新趋势。问题是：

- **信息过载**：关注 100+ 仓库，每天手动刷太累
- **噪声太多**：大部分更新与你的兴趣无关
- **容易错过**：重要更新淹没在信息流中
- **难以沉淀**：看到的好东西没有系统化保存

**OMKA 的解决方案**：每天自动采集、筛选和沉淀你关心的知识，并通过统一 Agent Runtime 在 Web 与飞书中完成检索、解释、记忆、收藏和受控执行。

## 核心功能

```
GitHub 信息源 → 自动抓取 → 结构化 → 去重 → 个性化排序 → AI 摘要 → 每日简报 → 飞书推送
```

同时，交互链路由统一 Runtime 驱动：

```text
用户目标 → 上下文检索 → 规划 → 工具调用 → 权限/确认 → 观察 → 回答 → 记忆与评估
```

| 功能 | 状态 | 说明 |
|------|------|------|
| GitHub 仓库监控 | ✅ | 支持指定仓库 + 关键词搜索 |
| 数据结构化 | ✅ | Raw → Normalized → Candidate 三层模型 |
| 智能去重 | ✅ | URL + 内容哈希双重去重 |
| 个性化排序 | ✅ | 兴趣匹配 + 项目相关 + 新鲜度 + 热度 |
| AI 摘要生成 | ✅ | 支持 OpenAI / Qwen / Ollama |
| 每日 Markdown 简报 | ✅ | 自动生成 `data/digests/YYYY-MM-DD.md` |
| 飞书 Webhook 推送 | ✅ | 支持签名校验 |
| Web 管理界面 | ✅ | React + shadcn/ui |
| 候选池管理 | ✅ | 收藏 / 忽略 / 入库 |
| 知识库 | ✅ | 已确认的知识条目 |
| 定时任务 | ✅ | APScheduler Cron 表达式 |
| 统一 Agent Runtime | ✅ | Web / 飞书共享规划与工具循环 |
| 工具权限与持久确认 | ✅ | 读、写、破坏性操作分级；确认可跨进程恢复 |
| 用户域记忆 | ✅ | 用户/会话隔离、候选记忆确认、过期与使用追踪 |
| 推荐反馈闭环 | ✅ | 收藏、忽略与反馈进入用户画像并影响后续推荐 |
| Agent 可观测性 | ✅ | 步骤轨迹、回放、确定性质量评估 |
| 主动 Agent Goal | ✅ | 手动或 Cron 运行、限定工具与最大步数 |
| Apple 风格工作台 | ✅ | 响应式 Web UI、Agent 中心与生成式主视觉 |

## 技术栈

### 后端

| 组件 | 技术 | 说明 |
|------|------|------|
| Web 框架 | FastAPI | 轻量高效，自动 OpenAPI 文档 |
| 定时任务 | APScheduler | Cron 表达式调度 |
| ORM | SQLModel + SQLAlchemy | 类型安全的数据库操作 |
| 数据库 | SQLite | 零配置，单文件 |
| HTTP 客户端 | httpx | 异步请求 |
| 数据验证 | Pydantic | 类型安全 |
| 配置管理 | python-dotenv + PyYAML | .env + YAML 配置 |

### 前端

| 组件 | 技术 | 说明 |
|------|------|------|
| 框架 | React 19 | 函数式组件 + Hooks |
| 语言 | TypeScript | 类型安全 |
| 构建工具 | Vite 8 | 快速热更新 |
| 样式 | Tailwind CSS | 原子化 CSS |
| UI 组件 | shadcn/ui | 可复用组件库 |
| 路由 | React Router 7 | SPA 路由 |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- npm 或 yarn

### 1. 克隆项目

```bash
git clone https://github.com/your-username/oh-my-knowledge-assistant.git
cd oh-my-knowledge-assistant
```

### 2. 后端配置

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 复制配置模板
copy .env.example .env

# 编辑 .env，填入必要配置
```

#### 必填配置

```bash
# GitHub Token（必须）
# 获取地址：https://github.com/settings/tokens
# 权限：repo（读取仓库信息）
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# LLM 配置（至少选一种）
# 方式 1：OpenAI
LLM_PROVIDER=openai
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# 方式 2：通义千问（Qwen）
LLM_PROVIDER=qwen
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus

# 方式 3：本地 Ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

#### 可选配置

```bash
# 数据采集
FETCH_CONCURRENCY=3          # 并发数
FETCH_TIMEOUT=30             # 请求超时（秒）
FETCH_MAX_RETRIES=3          # 失败重试次数

# 排序权重
SCORE_WEIGHT_INTEREST=0.40   # 兴趣匹配权重
SCORE_WEIGHT_PROJECT=0.30    # 项目相关权重
SCORE_WEIGHT_FRESHNESS=0.15  # 新鲜度权重
SCORE_WEIGHT_POPULARITY=0.15 # GitHub 热度权重

# 每日简报
DIGEST_TOP_N=10              # 简报包含条目数

# 定时任务
SCHEDULER_DAILY_CRON=0 9 * * *  # 每天 9:00 执行
SCHEDULER_TIMEZONE=Asia/Shanghai
```

### 3. 配置数据源

编辑 `data/profiles/sources.yaml`：

```yaml
github:
  repos:
    - langchain-ai/langgraph      # 关注的仓库
    - microsoft/playwright
    - browser-use/browser-use

  searches:
    - name: Browser Agent          # 关键词搜索
      query: "browser agent"
      limit: 5

    - name: RAG Agent
      query: "rag agent"
      limit: 5

    - name: Personal Knowledge Assistant
      query: "personal knowledge assistant llm"
      limit: 5
```

### 4. 配置兴趣画像

编辑 `data/profiles/interests.yaml`：

```yaml
interests:
  - name: AI Agent
    keywords:
      - agent
      - langgraph
      - multi-agent
      - tool use
      - autonomous agent
    weight: 1.0

  - name: Browser Agent
    keywords:
      - playwright
      - browser automation
      - drissionpage
      - aria snapshot
      - browser-use
    weight: 1.2

  - name: RAG
    keywords:
      - rag
      - retrieval augmented generation
      - vector search
      - embedding
    weight: 0.9

  - name: Personal Knowledge Management
    keywords:
      - knowledge management
      - second brain
      - zettelkasten
      - note taking
    weight: 0.8
```

### 5. 配置项目关注（可选）

编辑 `data/profiles/projects.yaml`，定义你关注的项目类型：

```yaml
projects:
  - name: Personal Knowledge Assistant
    keywords:
      - personal ai
      - knowledge assistant
      - memory
      - recommendation
    weight: 1.3

  - name: Browser Automation Framework
    keywords:
      - browser automation
      - web scraping
      - playwright
      - headless browser
    weight: 1.1
```

项目配置用于排序算法中的"项目相关性"评分（占总分 30%）。如果不配置，该维度评分为 0。

### 6. 启动后端

```bash
python -m omka.app.main
```

后端将在 `http://localhost:8000` 启动，访问 `http://localhost:8000/docs` 查看 API 文档。

### 7. 前端配置与启动

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将在 `http://localhost:5173` 启动。

### 8. 生产构建

```bash
cd frontend
npm run build
```

构建产物在 `frontend/dist/` 目录。

## 飞书 Webhook 配置

### 1. 创建飞书机器人

1. 打开飞书，进入目标群组
2. 点击群组设置 → 群机器人 → 添加机器人
3. 选择 **自定义机器人**
4. 填写机器人名称（如：OMKA 知识助手）
5. 复制 **Webhook 地址**

### 2. 配置签名（可选但推荐）

1. 在机器人设置中开启 **签名校验**
2. 复制 **签名密钥**

### 3. 配置 OMKA

在 `.env` 中添加：

```bash
# 飞书配置
FEISHU_WEBHOOK_ENABLED=true
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
FEISHU_WEBHOOK_SECRET=your_secret_here

# 推送配置
FEISHU_PUSH_DIGEST_TOP_N=6       # 推送简报条目数
FEISHU_REQUEST_TIMEOUT_SECONDS=10 # 请求超时
FEISHU_MAX_RETRIES=3              # 失败重试
```

或者在 Web 界面的 **设置页面** 中配置。

### 4. 测试飞书连接

```bash
# 方式 1：通过 API
curl -X POST http://localhost:8000/settings/test-feishu

# 方式 2：通过 Web 界面
# 打开 http://localhost:5173/settings → 点击"测试飞书"
```

### 5. 手动触发推送

```bash
# 生成今日简报并推送
curl -X POST http://localhost:8000/digests/run-today
```

## 目录结构

```
.
├── omka/                    # Python 后端包
│   └── app/
│       ├── main.py          # FastAPI 入口
│       ├── api/             # API 路由
│       ├── agents/          # Runtime、工具、上下文、记忆提取与评估
│       ├── connectors/      # 数据源连接器（插件化）
│       │   └── github/      # GitHub 实现
│       ├── pipeline/        # 数据处理流水线
│       │   ├── fetcher.py   # 抓取
│       │   ├── cleaner.py   # 清洗
│       │   ├── deduper.py   # 去重
│       │   ├── ranker.py    # 排序
│       │   ├── summarizer.py # AI 摘要
│       │   └── digest_builder.py # 简报生成
│       ├── storage/         # 数据存储
│       ├── services/        # 业务逻辑
│       ├── profiles/        # 用户画像加载
│       ├── notifications/   # 通知推送
│       └── core/            # 核心配置
├── frontend/                # React 前端
│   └── src/
│       ├── api/             # API 客户端
│       ├── components/      # UI 组件
│       ├── hooks/           # 自定义 Hooks
│       ├── pages/           # 页面组件
│       └── lib/             # 工具函数
├── data/                    # 数据目录
│   ├── profiles/            # 用户配置
│   ├── db/                  # SQLite 数据库
│   ├── digests/             # 每日简报
│   ├── knowledge/           # 知识库
│   └── raw/                 # 原始数据
├── tests/                   # 测试
└── requirements.txt         # Python 依赖
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| **信息源** | | |
| GET | `/sources` | 获取所有信息源 |
| POST | `/sources` | 创建信息源 |
| PUT | `/sources/{id}` | 更新信息源 |
| DELETE | `/sources/{id}` | 删除信息源 |
| POST | `/sources/{id}/run` | 手动运行单个源 |
| **候选池** | | |
| GET | `/candidates` | 获取候选列表（支持 `?status=pending`） |
| POST | `/candidates/{id}/confirm` | 确认入库 |
| POST | `/candidates/{id}/ignore` | 忽略 |
| POST | `/candidates/{id}/dislike` | 不感兴趣 |
| POST | `/candidates/{id}/read-later` | 稍后阅读 |
| POST | `/candidates/{id}/feedback` | 提交反馈 |
| **每日简报** | | |
| GET | `/digests/ranked` | 获取已排序的候选列表 |
| POST | `/digests/run-ranking` | 手动运行排序 |
| POST | `/digests/run-today` | 手动生成今日简报 |
| **知识库** | | |
| GET | `/knowledge` | 获取知识库列表 |
| GET | `/knowledge/{id}` | 获取单条详情 |
| POST | `/knowledge` | 创建知识条目 |
| DELETE | `/knowledge/{id}` | 删除知识条目 |
| POST | `/knowledge/{id}/feedback` | 提交反馈 |
| **通知** | | |
| POST | `/notifications/feishu/test` | 测试飞书推送 |
| POST | `/notifications/feishu/send-latest-digest` | 发送最新简报到飞书 |
| GET | `/notifications/runs` | 通知推送记录 |
| **任务** | | |
| GET | `/jobs/latest` | 最近一次任务 |
| GET | `/jobs/runs` | 任务运行记录 |
| POST | `/jobs/run-now` | 手动运行任务 |
| GET | `/jobs/dashboard` | 仪表盘数据 |
| **设置** | | |
| GET | `/settings` | 获取所有配置 |
| PUT | `/settings` | 批量更新配置 |
| POST | `/settings/{key}` | 更新单个配置 |
| POST | `/settings/test-github` | 测试 GitHub Token |
| POST | `/settings/test-llm` | 测试 LLM 配置 |
| POST | `/settings/test-feishu` | 测试飞书 Webhook |
| **Agent** | | |
| POST | `/agent/test` | 在 Web 中执行一次 Agent 任务 |
| GET | `/agent/runs` | 查询 Agent 运行 |
| GET | `/agent/runs/{id}` | 查询步骤轨迹 |
| POST | `/agent/runs/{id}/replay` | 使用最新上下文回放 |
| GET | `/agent/runs/{id}/evaluation` | 运行质量评估 |
| GET | `/agent-goals` | 查询主动目标 |
| POST | `/agent-goals` | 创建手动或 Cron 目标 |
| POST | `/agent-goals/{id}/run` | 立即运行目标 |
| PUT | `/agent-goals/{id}/status` | 暂停或恢复目标 |
| DELETE | `/agent-goals/{id}` | 删除目标 |

完整 API 文档：`http://localhost:8000/docs`

## 前端页面

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | 仪表盘 | 概览统计 |
| `/onboarding` | 引导页 | 首次使用配置引导 |
| `/sources` | 信息源 | 管理 GitHub 仓库和搜索 |
| `/digest` | 每日简报 | 查看生成的简报 |
| `/knowledge` | 知识库 | 已收藏的知识条目 |
| `/read-later` | 稍后阅读 | 待处理的候选条目 |
| `/memory` | 记忆 | 管理用户记忆与候选记忆 |
| `/assets` | 知识资产 | 管理上传与沉淀的知识资产 |
| `/agent` | Agent 中心 | 执行任务、管理目标、查看轨迹与评估 |
| `/push` | 推送策略 | 管理推送策略与历史 |
| `/settings` | 设置 | 配置 GitHub / LLM / 飞书 |
| `/job-logs` | 任务日志 | 查看执行历史 |

## 常见问题

### GitHub Token 额度不足

GitHub REST API 对认证用户有 5000 次/小时的额度。如果不够：
- 减少 `FETCH_CONCURRENCY`
- 增加 `FETCH_TIMEOUT`
- 减少监控的仓库数量

### LLM 摘要生成失败

- 检查 API Key 是否正确
- 检查 Base URL 是否可访问
- 摘要失败不会阻断主流程，会使用简单截断作为降级方案

### 飞书推送失败

- 检查 Webhook URL 是否正确
- 如果配置了签名，检查 Secret 是否正确
- 通过 `/settings/test-feishu` 测试连接

### 数据库位置

默认：`data/db/app.sqlite`

可以用 SQLite 工具直接查看：
```bash
sqlite3 data/db/app.sqlite
```

## 开发

### 运行测试

```bash
# Agent Runtime 与核心纯单元测试
python -m pytest tests/test_agent_runtime.py tests/test_github_query_builder.py tests/test_github_quality_scoring.py tests/test_github_search_task.py -q

# API 集成测试（需要先启动后端）
python tests/test_api.py

# 前端质量检查
cd frontend
npm run lint
npm run build
```

Agent 架构、工具风险策略、数据隔离和扩展方式详见
[`docs/AGENT_RUNTIME.md`](docs/AGENT_RUNTIME.md)。

### 添加新的数据源

1. 在 `omka/app/connectors/` 创建新连接器
2. 继承 `SourceConnector`，实现 `fetch()` 和 `normalize()`
3. 在 `registry.py` 注册
4. 在 `data/profiles/sources.yaml` 添加配置

### 添加新的 Pipeline 阶段

1. 在 `omka/app/pipeline/` 创建新模块
2. 在 `services/daily_job.py` 调用

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件（如不存在，请创建）。

---

> **OMKA** - 让 GitHub 信息流为你所用，而不是被它淹没。
