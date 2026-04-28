# OMKA Next Phase Productization Plan

> 文件用途：交给 opencode 执行。  
> 当前阶段目标：在已经完成 GitHub MVP 的基础上，把 OMKA 做成一个用户可直接通过 Web UI 使用、能接入飞书机器人推送、视觉上接近成熟产品的个人知识助手雏形。  
> 设计方向：Warm Linear Knowledge Workspace，即参考 Linear 的秩序感、留白、卡片层级和精致边框，但结合个人知识助手场景，采用更温和的暖色知识工作台风格。

---

## 0. 执行前必须阅读

在开始编码前，必须先检查当前项目，不允许盲目重构。

必须先确认：

```text
1. 当前后端框架、入口文件、启动方式
2. 当前 GitHub MVP Pipeline 的入口和数据流
3. 当前数据库模型和迁移方式
4. 当前是否已有前端
5. 当前是否已有 API 层
6. 当前配置文件和 .env 读取方式
7. 当前 digest / candidate / knowledge 的存储方式
8. 当前已有的测试、lint、typecheck、build 命令
```

执行原则：

```text
1. 保留现有已经跑通的 GitHub MVP 主流程
2. 只做产品化增量开发
3. 只做必要的接口和 UI
4. 不重写无关模块
5. 不引入重型依赖
6. 不为了视觉效果破坏功能、数据流、路由、存储逻辑
```

---

## 1. 当前项目背景

当前 OMKA 已经完成 GitHub MVP，已有或应已有以下能力：

```text
GitHub 信息源配置
→ GitHub 抓取
→ RawItem / NormalizedItem 结构化
→ 去重
→ 个性化排序
→ LLM 摘要
→ 每日 Digest
→ Candidate 候选池
→ Knowledge 收藏入库
```

下一阶段不是继续扩大抓取范围，也不是做知识图谱或多 Agent。

下一阶段核心是：

```text
让用户不用看命令行、不用改代码、不用理解内部 Pipeline，
就能通过 Web UI 配置、运行、查看、反馈、收藏，并通过飞书机器人收到每日简报。
```

---

## 2. 本阶段最终用户体验目标

完成后，用户应该可以：

```text
1. 打开 Web UI
2. 通过 Onboarding 配置 GitHub Token、兴趣、项目、GitHub repo、GitHub search query
3. 可选配置飞书 Webhook
4. 点击 Run Now
5. 看到一份美观、可读、有推荐理由的每日 GitHub 知识简报
6. 对推荐内容执行：收藏 / 忽略 / 不感兴趣 / 稍后阅读
7. 收藏内容进入 Knowledge 页面
8. Dashboard 显示今天任务是否成功、抓取多少、推荐多少、飞书是否推送成功
9. 每天自动收到飞书群机器人推送的压缩版简报
```

---

## 3. 本阶段开发边界

### 3.1 必须做

```text
P0 必做：
1. Web UI 基础框架
2. Warm Linear Knowledge Workspace 视觉设计
3. 主题 token / CSS variables，当前只实现一个暖色主题，但预留后续主题扩展
4. Settings 页面，用户可配置关键环境变量
5. Onboarding 初始化向导
6. Sources 页面，管理 GitHub repo 和 GitHub search query
7. Digest 页面，展示推荐卡片
8. Candidate 操作：收藏 / 忽略 / 不感兴趣 / 稍后阅读
9. Knowledge 页面，展示收藏内容
10. Run Now 手动运行按钮
11. 飞书自定义机器人 Webhook 推送
12. Dashboard 运行状态概览
13. Job Logs / Notification Runs 基础日志
14. 所有 token、URL、模型名、端口、路径、定时任务时间、Top N 等常量统一放入 .env 或 DB app_settings，不在代码中硬编码
15. 保留后续多信息源、多通知通道、多知识库后端的接口
```

### 3.2 严禁现阶段做

```text
严禁：
1. 不要接入 RSS、网页、Arxiv、Telegram、邮箱等新信息源
2. 不要扩展 GitHub 抓取到 commit、完整代码、全量 issue、全量 PR、discussion
3. 不要做知识图谱、Neo4j
4. 不要引入向量数据库重构当前流程
5. 不要做多 Agent
6. 不要做复杂聊天问答
7. 不要做飞书开放平台应用机器人
8. 不要做飞书事件订阅
9. 不要做飞书卡片按钮交互
10. 不要做飞书内收藏、忽略、稍后阅读
11. 不要做多用户账号系统
12. 不要做复杂权限系统
13. 不要把 token、webhook、secret、模型名、端口、路径硬编码到代码里
14. 不要为了 UI 大规模重写后端
15. 不要直接复制 Linear 的品牌、Logo、文案、插画或专有视觉资产
16. 不要做大量炫光渐变、玻璃拟态、AI 感发光卡片、无意义动画
17. 不要增加过多新文件和过度抽象
```

本阶段只做：

```text
产品可用性 + 前端视觉产品化 + 用户反馈闭环 + 飞书 Webhook 推送
```

---

## 4. 前端技术选型

### 4.1 推荐栈

如当前项目没有前端，新增：

```text
Vite + React + TypeScript + Tailwind CSS + shadcn/ui + lucide-react
```

理由：

```text
1. 适合本地 Web UI
2. 开发速度快
3. shadcn/ui 适合做克制、干净、可维护的知识工作台
4. Tailwind 便于统一 spacing、radius、颜色 token
5. React + TypeScript 对后续组件扩展友好
```

### 4.2 不推荐现阶段使用

```text
1. Next.js：当前不是内容站或 SSR 应用，复杂度不必要
2. Electron：当前先用 Web UI，不做桌面打包
3. Redux / MobX：当前状态复杂度不高
4. 重型 UI 框架：避免破坏视觉控制和增加依赖
5. 动画库：非必要不要引入
```

### 4.3 前端目录建议

```text
frontend/
  package.json
  vite.config.ts
  tailwind.config.ts
  postcss.config.js
  index.html
  src/
    main.tsx
    App.tsx

    api/
      client.ts
      settings.ts
      sources.ts
      digests.ts
      candidates.ts
      knowledge.ts
      jobs.ts
      notifications.ts

    components/
      ui/                 # shadcn/ui 组件（自动安装）
      layout/
        app-sidebar.tsx
        app-shell.tsx
        page-header.tsx
      cards/
        digest-card.tsx
        knowledge-card.tsx
        source-card.tsx
        metric-card.tsx
      common/
        status-badge.tsx
        empty-state.tsx
        error-state.tsx
        loading-state.tsx

    pages/
      DashboardPage.tsx
      OnboardingPage.tsx
      SourcesPage.tsx
      DigestPage.tsx
      KnowledgePage.tsx
      ReadLaterPage.tsx
      SettingsPage.tsx
      JobLogsPage.tsx

    hooks/
      use-settings.ts
      use-sources.ts
      use-digests.ts
      use-candidates.ts
      use-knowledge.ts
      use-jobs.ts

    styles/
      globals.css
      theme.css

    types/
      settings.ts
      source.ts
      digest.ts
      candidate.ts
      knowledge.ts
      job.ts
      notification.ts

    lib/
      cn.ts
      date.ts
      format.ts
```

---

## 5. UI 视觉设计规范

### 5.1 设计定位

本阶段 UI 风格定位为：

```text
Warm Linear Knowledge Workspace
```

含义：

```text
1. 借鉴 Linear 的布局纪律、留白、卡片层级、精致边框、清晰导航
2. 不复制 Linear 的品牌和冷色企业 SaaS 气质
3. 结合个人知识助手场景，使用更温和、可读、低噪声的暖色背景
4. 让用户感觉这是一个“每天愿意打开的个人知识工作台”
```

### 5.2 参考 Linear 时要学习什么

学习：

```text
1. 左侧导航 + 主工作区的清晰结构
2. 强层级的信息组织
3. 克制的边框和阴影
4. 高质量 spacing
5. 稳定、安静、专业的组件状态
6. 列表和卡片的可读性
7. 不喧宾夺主的 accent color
```

不要复制：

```text
1. Linear Logo
2. Linear 文案
3. Linear 品牌图形
4. Linear 专有插画
5. 过于冷的黑灰背景
6. 过于产品研发/工单系统的语义
```

### 5.3 颜色方向

当前版本只做一个主题：

```text
default warm theme
```

视觉目标：

```text
1. app background：warm ivory / warm sand
2. surface/card：soft white
3. border：warm gray
4. primary accent：muted amber / warm brown
5. text：neutral dark
6. muted text：warm gray
7. success：low-saturation green
8. danger：low-saturation red
```

不要：

```text
1. 大面积高饱和橙色
2. 大面积紫蓝渐变
3. 发光卡片
4. 玻璃拟态
5. 背景装饰 blob
6. 花哨 hero section
```

### 5.4 主题 token 规范

必须使用 CSS variables / Tailwind theme tokens。

严禁在组件中到处硬编码颜色，例如：

```text
bg-[#f7efe2]
text-[#2b1f18]
```

应该使用：

```text
bg-background
text-foreground
bg-card
border-border
text-muted-foreground
bg-primary
```

建议 `frontend/src/styles/theme.css`：

```css
:root {
  --background: 42 38% 96%;
  --foreground: 24 20% 12%;

  --card: 40 40% 99%;
  --card-foreground: 24 20% 12%;

  --popover: 40 40% 99%;
  --popover-foreground: 24 20% 12%;

  --primary: 32 72% 48%;
  --primary-foreground: 0 0% 100%;

  --secondary: 36 32% 91%;
  --secondary-foreground: 24 18% 18%;

  --muted: 35 24% 92%;
  --muted-foreground: 25 10% 42%;

  --accent: 34 44% 88%;
  --accent-foreground: 24 18% 18%;

  --destructive: 4 60% 46%;
  --destructive-foreground: 0 0% 100%;

  --success: 145 34% 36%;
  --success-foreground: 0 0% 100%;

  --border: 32 18% 86%;
  --input: 32 18% 86%;
  --ring: 32 72% 48%;

  --radius: 0.875rem;
}
```

后续主题扩展预留：

```text
[data-theme="warm"] 当前默认
[data-theme="neutral"] 后续
[data-theme="dark"] 后续
[data-theme="paper"] 后续
[data-theme="linear"] 后续
```

当前只实现 warm，不做主题切换 UI，但代码结构必须允许后续扩展。

### 5.5 Layout 规范

整体：

```text
1. 左侧固定 sidebar
2. 右侧主内容区域
3. 主内容 max-width 建议 1120px ~ 1280px
4. 页面顶部有 PageHeader
5. 重要操作放在 PageHeader 右侧
6. 页面内容使用 cards / sections 分组
```

桌面布局：

```text
sidebar width: 240px ~ 264px
main padding: 24px ~ 32px
section gap: 20px ~ 28px
card padding: 18px ~ 24px
```

移动端：

```text
1. sidebar 折叠
2. 主内容单列
3. 卡片按钮换行
4. 不要求复杂移动端体验，但不能明显错位
```

### 5.6 字体和排版

建议：

```text
font-family:
- 优先使用系统字体
- 不引入外部字体依赖

title:
- text-2xl / font-semibold / tracking-tight

section title:
- text-base or text-lg / font-semibold

body:
- text-sm / leading-6

muted:
- text-sm / text-muted-foreground

label:
- text-xs or text-sm / font-medium
```

不要使用：

```text
1. 过大的 marketing hero 标题
2. 过浅的灰色正文
3. 不一致的字号
4. 大量 emoji 作为主要信息结构
```

### 5.7 组件风格

卡片：

```text
1. bg-card
2. border border-border
3. rounded-2xl
4. shadow-sm 或无 shadow
5. hover 时轻微 border / background 变化
```

按钮：

```text
1. primary 用暖色 accent
2. secondary / ghost 要克制
3. destructive 只用于删除等危险操作
4. 所有按钮必须有 disabled / loading 状态
```

Badge：

```text
1. 用于 item_type、tag、status
2. 低饱和背景
3. 不要高亮过度
```

表单：

```text
1. label 清晰
2. help text 清楚
3. secret 字段默认 masked
4. 错误提示必须人类可读
```

空状态：

```text
1. 告诉用户为什么为空
2. 提供下一步按钮
3. 不显示“暂无数据”就结束
```

---

## 6. 后端技术和架构规范

### 6.1 后端保留现有技术

优先沿用当前项目已有技术。

如果当前已是 Python 后端，推荐：

```text
FastAPI
SQLModel / SQLAlchemy
SQLite
APScheduler
Pydantic
python-dotenv
httpx
```

要求：

```text
1. 不要切换数据库
2. 不要引入消息队列
3. 不要拆微服务
4. 不要重写 GitHub Pipeline
5. 只新增 UI 所需 API、飞书通知模块、状态日志模块
```

### 6.2 后端新增模块建议

```text
app/
  api/
    routes_settings.py
    routes_onboarding.py
    routes_sources.py
    routes_digests.py
    routes_candidates.py
    routes_knowledge.py
    routes_jobs.py
    routes_notifications.py

  core/
    settings.py
    env_writer.py
    errors.py

  notifications/
    base.py
    service.py
    channels/
      feishu_webhook.py

  feedback/
    service.py

  knowledge/
    service.py
    markdown_exporter.py

  jobs/
    service.py
```

如当前项目已有不同结构，按现有风格增量添加，不强制搬迁全部文件。

---

## 7. 环境变量与配置规范

### 7.1 总原则

配置采用**双层架构**：

```text
Layer 1: .env 文件 —— 启动时的兜底配置（只读）
Layer 2: DB app_settings 表 —— 运行时动态配置（UI 可读写）
```

读取优先级：`DB Settings` > `.env 默认值`

**为什么不用 .env 做运行时热重载？**
- 当前后端使用 Pydantic BaseSettings + `@lru_cache` 单例，启动后配置不可变
- .env 文件写入非原子操作，并发修改可能损坏
- DB 配置支持变更审计、即时生效、多进程同步

所有可变常量必须从 `.env` 或 DB 读取：

```text
1. GitHub Token
2. GitHub API Base URL
3. GitHub request timeout
4. GitHub search limit
5. LLM provider / base url / api key / model
6. 后端 host / port
7. 前端 port
8. public base url
9. data dir / db url / digest dir / knowledge dir
10. 每日任务开关和时间
11. timezone
12. digest top n
13. 飞书 webhook enabled / url / secret
14. 飞书推送 top n / timeout / retries
```

严禁：

```text
1. 在代码里硬编码 token
2. 在代码里硬编码 webhook
3. 在代码里硬编码模型名
4. 在代码里硬编码端口
5. 在代码里硬编码 data 目录
6. 在日志里输出完整 secret
```

### 7.2 推荐 .env.example

在现有 `.env.example` 基础上**增量添加**飞书相关配置，保持现有变量命名风格：

```env
# 在现有配置末尾追加：

# =========================
# Feishu Webhook
# =========================
FEISHU_WEBHOOK_ENABLED=false
FEISHU_WEBHOOK_URL=
FEISHU_WEBHOOK_SECRET=
FEISHU_PUSH_DIGEST_TOP_N=6
FEISHU_REQUEST_TIMEOUT_SECONDS=10
FEISHU_MAX_RETRIES=3
```

**注意：** 保持现有环境变量命名不变（如 `APP_NAME`, `API_HOST`, `DATABASE_URL` 等），不强制加 `OMKA_` 前缀。新增配置项也遵循当前风格。

### 7.3 Settings UI 更新配置

必须实现 `SettingsService`：

```text
1. 启动时从 .env 加载默认值
2. 运行时从 DB app_settings 表读取，覆盖 .env 值
3. UI 修改时写入 DB app_settings 表
4. 读取时优先使用 DB 值，DB 无值时回退到 .env
5. 缓存 60 秒，支持手动刷新
6. 不把 secret 打印到日志
7. UI/API 返回时 secret 字段只返回 masked 状态
```

DB `app_settings` 表建议字段：

```text
key (PRIMARY KEY)
value
is_secret (boolean)
category (string)
updated_at
```

敏感字段：

```text
GITHUB_TOKEN
LLM_API_KEY
FEISHU_WEBHOOK_URL
FEISHU_WEBHOOK_SECRET
```

UI 显示：

```text
已配置 / 未配置
最后 4 位可选显示
不明文展示完整值
```

---

## 8. API 规划

保持现有 API 前缀（无统一 `/api` 前缀），与当前后端保持一致。前端直接请求现有路径。

如需统一前缀，可在反向代理层面做路径映射，不修改后端路由。

### 8.1 Settings

```text
GET  /settings
PUT  /settings
POST /settings/test-github
POST /settings/test-llm
POST /settings/test-feishu
```

要求：

```text
1. GET 不返回完整 secret
2. PUT 支持更新 env
3. test-github 校验 GitHub Token 是否能访问 API
4. test-llm 校验 LLM 配置是否可用
5. test-feishu 发送一条测试消息
```

### 8.2 Onboarding

```text
GET  /onboarding/status
POST /onboarding/complete
```

`status` 返回：

```json
{
  "has_github_token": true,
  "has_interests": true,
  "has_projects": true,
  "has_sources": true,
  "has_latest_digest": false,
  "completed": false
}
```

### 8.3 Sources

```text
GET    /sources
POST   /sources/github/repo
POST   /sources/github/search
PUT    /sources/{id}
DELETE /sources/{id}
```

当前只允许：

```text
GitHub repo
GitHub search query
```

其他来源只在 UI 中显示 Coming soon，不实现 API。

### 8.4 Digest

```text
GET  /digests
GET  /digests/latest
GET  /digests/{date}
POST /digests/run-now
```

`run-now` 应触发：

```text
GitHub fetch
→ normalize
→ dedup
→ rank
→ summarize
→ digest generation
→ optional feishu push
```

### 8.5 Candidates

```text
GET  /candidates
POST /candidates/{id}/save
POST /candidates/{id}/ignore
POST /candidates/{id}/dislike
POST /candidates/{id}/read-later
```

行为：

```text
save:
  candidate status = confirmed
  create knowledge item
  create user_feedback action=save

ignore:
  candidate status = ignored
  create user_feedback action=ignore

dislike:
  candidate status = disliked
  create user_feedback action=dislike

read-later:
  candidate status = read_later
  create user_feedback action=read_later
```

### 8.6 Knowledge

```text
GET    /knowledge
GET    /knowledge/{id}
DELETE /knowledge/{id}
POST   /knowledge/{id}/export
```

查询参数建议：

```text
q
tag
project
source_type
item_type
limit
offset
```

### 8.7 Notifications

```text
POST /notifications/feishu/test
POST /notifications/feishu/send-latest-digest
GET  /notifications/runs
```

### 8.8 Jobs

```text
GET  /jobs/latest
GET  /jobs/runs
POST /jobs/run-now
```

---

## 9. 数据模型和数据库调整

如当前项目已有表，优先复用并增量字段，不要重复造表。

### 9.1 candidate_items

必须支持状态：

```text
pending
confirmed
ignored
disliked
read_later
```

建议字段：

```text
id
normalized_item_id
title
url
item_type
summary
recommendation_reason
score
score_detail_json
matched_interests_json
matched_projects_json
status
created_at
updated_at
```

### 9.2 user_feedback

新增或完善：

```text
id
candidate_item_id
normalized_item_id
action
reason
created_at
```

action：

```text
save
ignore
dislike
read_later
```

### 9.3 knowledge_items

建议字段：

```text
id
title
url
source_type
item_type
summary
content
recommendation_reason
tags_json
related_projects_json
created_at
updated_at
```

### 9.4 job_runs（复用现有 fetch_runs 表）

**不复用新建，直接扩展现有 `fetch_runs` 表：**

现有字段基础上扩展：

```text
id
job_type          -- 扩展：支持 github_daily_job / manual_run / digest_generation / feishu_push
status            -- 已有：running / success / partial_success / failed
started_at        -- 已有
finished_at       -- 已有
fetched_count     -- 已有（保留兼容）
fetched_repo_count      -- 新增
fetched_release_count   -- 新增
fetched_search_result_count -- 新增
normalized_count  -- 已有（保留兼容）
candidate_count   -- 已有（保留兼容）
digest_item_count -- 新增
error_count       -- 已有（保留兼容）
error_message     -- 已有
metadata_json     -- 新增（通用 JSON 字段）
```

新增字段均为可空，不影响现有数据。

**新增 `notification_runs` 表：**

```text
id
channel_type      -- feishu_webhook / email / telegram
digest_id
status            -- success / failed / skipped
sent_at
error_message
response_json
created_at
```

### 9.5 notification_runs

新增：

```text
id
channel_type
digest_id
status
sent_at
error_message
response_json
created_at
```

status：

```text
success
failed
skipped
```

---

## 10. 页面规划

### 10.1 App Shell

必须实现：

```text
1. 左侧 Sidebar
2. 顶部当前状态栏或 PageHeader
3. 主内容区域
4. 全局 Toast
5. Loading / Error / Empty states
```

导航项：

```text
Dashboard
Onboarding
Sources
Digest
Knowledge
Read Later
Settings
Job Logs
```

### 10.2 Dashboard Page

优先级：P1

展示：

```text
1. 今日是否已运行
2. 最近一次运行状态
3. 最近一次运行时间
4. GitHub 抓取数量
5. 候选内容数量
6. 推荐内容数量
7. 知识库总数
8. 飞书推送状态
9. 常见错误提示
```

按钮：

```text
Run Now
Send Test Feishu Message
Open Latest Digest
```

### 10.3 Onboarding Page

优先级：P0

步骤：

```text
Step 1：配置 GitHub Token
Step 2：选择兴趣方向
Step 3：配置当前项目
Step 4：添加关注仓库
Step 5：添加搜索关键词
Step 6：配置飞书 Webhook，可跳过
Step 7：立即运行一次
```

默认兴趣模板：

```text
AI Agent
Browser Agent
RAG
LLM Tools
Python Backend
Personal Knowledge Assistant
Open Source Tools
```

验收：

```text
1. 用户可以通过 UI 配置 GitHub Token
2. 用户可以通过 UI 添加 repo 和 search query
3. 用户可以点击 Run Now
4. 成功后跳转 Digest 页面
```

### 10.4 Sources Page

优先级：P0 / P1

功能：

```text
1. 查看当前 GitHub repos
2. 添加 GitHub repo
3. 删除 GitHub repo
4. 启用 / 禁用 repo
5. 添加 search query
6. 删除 search query
7. 设置来源权重
```

页面中可以显示但不得实现：

```text
RSS Coming soon
Webpage Coming soon
Arxiv Coming soon
Email Coming soon
Telegram Coming soon
```

### 10.5 Digest Page

优先级：P0

最重要页面。

每张推荐卡片包含：

```text
标题
GitHub 链接
类型：repo / release / repo_search_result
一句话摘要
推荐理由
相关兴趣标签
相关项目
分数
建议动作
```

按钮：

```text
收藏
忽略
不感兴趣
稍后阅读
```

设计重点：

```text
1. 推荐理由要醒目
2. 相关项目和标签要清晰
3. GitHub 原始字段不要堆满页面
4. 卡片之间有足够留白
5. 操作按钮位置固定且明显
```

### 10.6 Knowledge Page

优先级：P0 / P1

功能：

```text
1. 查看已收藏知识
2. 搜索标题 / 摘要 / 标签
3. 按标签筛选
4. 按项目筛选
5. 查看来源链接
6. 删除知识
7. 导出 Markdown
```

卡片字段：

```text
标题
来源
摘要
为什么收藏 / 推荐理由
相关标签
相关项目
创建时间
```

### 10.7 Read Later Page

优先级：P1

功能：

```text
1. 查看稍后阅读内容
2. 收藏
3. 忽略
4. 标记已读
```

如时间不够，可以先作为 Digest Page 的 tab。

### 10.8 Settings Page

优先级：P0

设置项：

```text
GitHub Token
LLM Provider
LLM API Key
LLM Base URL
LLM Model
每日运行时间
Digest Top N
Feishu Webhook 开关
Feishu Webhook URL
Feishu Secret
Feishu Top N
```

必须支持：

```text
1. 保存配置到 .env
2. 测试 GitHub Token
3. 测试 LLM 连接
4. 测试飞书 Webhook
5. secret 字段 masked
```

### 10.9 Job Logs Page

优先级：P1

展示：

```text
任务类型
状态
开始时间
结束时间
抓取数量
推荐数量
错误信息
```

---

## 11. 飞书 Webhook 接入规划

### 11.1 只做 Webhook

本阶段只实现：

```text
飞书自定义群机器人 Webhook
```

不实现：

```text
飞书开放平台应用机器人
事件订阅
消息回调
飞书卡片按钮
飞书内收藏 / 忽略 / 稍后阅读
```

### 11.2 后端模块

```text
app/notifications/
  base.py
  service.py
  channels/
    feishu_webhook.py
```

接口：

```python
class NotificationChannel:
    channel_type: str

    async def send_digest(self, digest) -> SendResult:
        raise NotImplementedError
```

本阶段实现：

```text
FeishuWebhookChannel
```

预留但不实现：

```text
EmailChannel
TelegramChannel
QQBotChannel
FeishuAppBotChannel
```

### 11.3 推送流程

```text
每日任务完成
→ Digest 生成成功
→ NotificationService 判断 FEISHU_WEBHOOK_ENABLED
→ FeishuWebhookChannel 发送压缩版简报
→ 写 notification_runs
```

飞书推送失败：

```text
1. 不影响 GitHub 抓取
2. 不影响 Digest 生成
3. 不影响 Candidate 入库
4. Dashboard 显示 Feishu push failed
5. Job Logs / Notification Runs 记录错误
```

### 11.4 飞书消息内容

第一版不要太长。

消息结构：

```text
📌 OMKA 今日 GitHub 知识简报

今日概览：
- 抓取仓库：x
- Release：x
- 搜索结果：x
- 推荐内容：x

🔥 最值得关注

1. {title}
摘要：{summary}
推荐理由：{recommendation_reason}
建议动作：{suggested_action}

2. {title}
摘要：{summary}
推荐理由：{recommendation_reason}
建议动作：{suggested_action}

查看完整简报：
{OMKA_PUBLIC_BASE_URL}/digests/{date}
```

只推：

```text
FEISHU_PUSH_DIGEST_TOP_N
```

### 11.5 飞书稳定性要求

必须：

```text
1. 请求超时
2. 最多重试
3. 发送结果落库
4. webhook 为空时跳过
5. 失败不影响主任务
6. 不在日志中打印完整 webhook URL
7. 不在日志中打印 secret
8. 测试推送支持 UI 按钮触发
```

---

## 12. 用户反馈影响推荐

优先级：P1

本阶段不做复杂 ML，只做规则反馈。

### 12.1 save

```text
1. user_feedback action=save
2. candidate status=confirmed
3. create knowledge item
4. 相关 tag 权重小幅提高
5. 相关 project 权重小幅提高
```

### 12.2 dislike

```text
1. user_feedback action=dislike
2. candidate status=disliked
3. URL 不再推荐
4. 相关 tag 权重小幅降低
```

### 12.3 ignore

```text
1. user_feedback action=ignore
2. candidate status=ignored
3. 当前 URL 不再推荐
```

### 12.4 read_later

```text
1. user_feedback action=read_later
2. candidate status=read_later
3. 进入 Read Later 页面
```

### 12.5 权重存储

如果当前已有兴趣配置文件，优先增量写入：

```text
data/profiles/user_feedback_weights.yaml
```

示例：

```yaml
positive_tags:
  browser-agent: 1.2
  langgraph: 1.1

negative_tags:
  toy-project: 0.7
  frontend-only: 0.8
```

不要把这个做复杂，第一版只要能影响下一次排序即可。

---

## 13. 后续扩展接口预留

### 13.1 SourceConnector

保留或新增：

```python
class SourceConnector:
    source_type: str

    async def fetch(self, source_config):
        raise NotImplementedError

    def normalize(self, raw_item):
        raise NotImplementedError
```

当前只实现：

```text
GitHubConnector
```

预留但不实现：

```text
RSSConnector
WebpageConnector
ArxivConnector
EmailConnector
TelegramConnector
```

### 13.2 NotificationChannel

```python
class NotificationChannel:
    channel_type: str

    async def send_digest(self, digest):
        raise NotImplementedError
```

当前只实现：

```text
FeishuWebhookChannel
```

预留但不实现：

```text
EmailChannel
TelegramChannel
QQBotChannel
FeishuAppBotChannel
```

### 13.3 KnowledgeStore

```python
class KnowledgeStore:
    async def save(self, item):
        raise NotImplementedError

    async def search(self, query):
        raise NotImplementedError

    async def delete(self, item_id):
        raise NotImplementedError
```

当前只实现：

```text
SQLite + Markdown
```

预留但不实现：

```text
VectorKnowledgeStore
GraphKnowledgeStore
```

---

## 14. 开发任务优先级

### P0：必须完成

```text
1. 代码结构检查，不破坏现有 GitHub MVP
2. .env.example 与配置读取标准化
3. Settings API + Settings 页面
4. 前端基础框架：Vite + React + TypeScript + Tailwind + shadcn/ui
5. Warm Linear 主题 token
6. App Shell：Sidebar + PageHeader + 主内容区
7. Onboarding 页面
8. Sources 页面支持 GitHub repo/search
9. Digest 页面推荐卡片
10. Candidate 操作 API：save / ignore / dislike / read-later
11. Knowledge 页面
12. Run Now 手动运行
13. FeishuWebhookChannel
14. 飞书测试推送
15. Digest 生成后可自动推送飞书
```

P0 完成后，用户应该能完整体验：

```text
配置 → 运行 → 查看推荐 → 收藏/反馈 → 知识库 → 飞书推送
```

### P1：提高可用性

```text
1. Dashboard
2. Job Logs
3. Notification Runs 展示
4. 反馈影响排序
5. Read Later 页面
6. Markdown 导出
7. GitHub Token 测试
8. LLM 连接测试
9. 细化错误提示
10. UI loading / empty / error states 完整打磨
```

### P2：后续增强，本阶段严禁实现

```text
1. 飞书富文本卡片
2. 飞书卡片按钮
3. 飞书应用机器人
4. 更多信息源
5. 向量检索
6. 知识图谱
7. 多 Agent
8. 聊天问答
9. 多用户系统
```

---

## 15. 建议执行顺序

### Step 1：后端基础调整（1 天）

在现有代码基础上增量调整，不破坏已有流程：

```text
1. 确认数据库模型调整（Candidate 状态扩展、fetch_runs 字段扩展）
2. 新增 app_settings DB 表（支持运行时配置读写）
3. 新增 Feishu 配置项到 config.py 和 .env.example（增量追加）
4. 确认现有 API 可用性
```

验收：

```text
- python -m omka.app.main 启动成功
- 数据库无报错
- 现有 GitHub MVP Pipeline 仍可正常运行
```

### Step 2：前端基础工程 + App Shell（2 天）

```text
1. 初始化 Vite + React + TypeScript + Tailwind + shadcn/ui
2. 实现 theme.css（Warm Linear CSS variables）
3. 实现 AppShell + Sidebar + PageHeader
4. 实现 React Router 页面切换
5. 实现 API client（对接现有后端路径，无 /api 前缀）
6. 基础页面空壳（Dashboard, Settings, Sources, Digest, Knowledge, JobLogs）
```

验收：

```text
1. npm run dev 启动成功
2. 页面可切换
3. Warm Linear theme 生效
4. npm run build 通过
```

### Step 3：Settings API + Settings 页面（2 天）

```text
1. 实现 SettingsService（DB 读写 + .env 兜底）
2. 实现 Settings API（GET /settings, PUT /settings, test 端点）
3. 实现 Settings 前端页面
4. secret masking
5. 不在日志输出 secret
```

验收：

```text
1. 可通过 UI 保存配置到 DB，刷新后配置不丢失
2. 可测试 GitHub / LLM / Feishu 连接
3. secret 不明文泄露
4. 修改配置后不需要重启服务
```

### Step 4：Onboarding + Sources 页面（2 天）

```text
1. 实现 Onboarding Stepper UI
2. 兴趣模板选择
3. 当前项目配置
4. GitHub repo / search query 添加
5. 可选飞书配置
6. 对接现有 Sources API
```

验收：

```text
新用户可以 5 分钟内完成配置并运行出第一份 digest。
```

### Step 5：Digest + Candidate 操作（2 天）

```text
1. 后端：新增 /candidates/{id}/dislike 和 /candidates/{id}/read-later 端点
2. 后端：扩展 CandidateItem.status 支持 disliked / read_later
3. 前端：Digest 推荐卡片（标题、摘要、推荐理由、标签、分数）
4. 前端：save / ignore / dislike / read-later 按钮
5. 前端：Toast 提示
```

验收：

```text
1. 用户能对推荐内容执行操作
2. 刷新后状态不丢失
3. disliked / read_later 的内容不再出现在 Digest
```

### Step 6：Knowledge + Read Later 页面（1 天）

```text
1. 前端：Knowledge 页面（收藏内容展示、搜索、标签筛选）
2. 前端：Read Later 页面（或作为 Digest 的 tab）
3. 前端：Markdown 导出按钮
4. 对接现有 Knowledge API
```

验收：

```text
1. 保存后的 candidate 可以在 Knowledge 页面看到
2. Read Later 内容可在对应页面查看
```

### Step 7：飞书 Webhook（2 天）

```text
1. 实现 NotificationChannel 基类
2. 实现 FeishuWebhookChannel（含签名验证、重试、超时）
3. 实现 NotificationService
4. 新增 notification_runs DB 表
5. 集成到 daily_job.py（Digest 生成后自动推送）
6. 实现测试推送 API
```

验收：

```text
1. UI 可配置飞书 webhook
2. 测试推送成功
3. 每日 digest 可自动推送到飞书
4. 推送失败不影响主任务
5. 不在日志输出完整 webhook URL 和 secret
```

### Step 8：Dashboard + Job Logs（1-2 天）

```text
1. 后端：Dashboard 聚合 API（今日状态、抓取数量、推荐数量、推送状态）
2. 后端：Job Logs API（查询 fetch_runs + notification_runs）
3. 前端：Dashboard 页面（Metrics Cards、运行状态、快捷按钮）
4. 前端：Job Logs 页面
```

验收：

```text
1. Dashboard 显示今天系统是否正常工作
2. 失败时显示友好错误提示（如 "GitHub Token 无效"）
3. Job Logs 可查看历史运行记录
```

### Step 9：打磨与验证（1-2 天）

```text
1. Loading / Empty / Error states 完整打磨
2. 移动端适配（sidebar 折叠、卡片换行）
3. 端到端验证：配置 → 运行 → 查看 → 收藏 → 飞书推送
4. 前端 build / lint / typecheck 配置
5. 补充关键测试
```

验收：

```text
1. npm run build / lint / typecheck 通过
2. 后端启动成功
3. Settings 页面可访问
4. Run Now 能触发
5. Digest 页面有数据
6. Candidate 操作生效
7. Knowledge 页面能看到收藏内容
8. Feishu 测试推送成功或给出明确失败原因
```

---

## 16. 错误处理要求

所有用户可见错误必须人类可读。

示例：

```text
GitHub Token 未配置
GitHub Token 无效
GitHub API 限流
没有配置任何关注仓库
没有配置搜索关键词
LLM API Key 未配置
LLM 摘要失败
Feishu Webhook 未配置
Feishu 推送失败
今日没有匹配到高价值内容
```

不要直接显示：

```text
500 Internal Server Error
KeyError
NoneType
Traceback
```

后端日志可以记录详细异常，但 UI 展示必须转换为友好文案。

---

## 17. 验证要求

每个阶段后都要运行可用的验证命令。

后端验证：

```text
python -m omka.app.main    # 启动检查
pytest tests/              # 运行测试（需补充）
```

前端验证（需配置）：

```text
cd frontend && npm run build      # 构建检查
cd frontend && npm run lint       # ESLint
cd frontend && npm run typecheck  # TypeScript
```

端到端验证：

```text
1. 后端启动成功（python -m omka.app.main）
2. 前端启动成功（npm run dev）
3. Settings 页面可访问且可保存配置
4. Run Now 能触发并生成 Digest
5. Digest 页面展示推荐卡片
6. Candidate save/ignore/dislike/read-later 操作生效
7. Knowledge 页面能看到收藏内容
8. Feishu 测试推送成功或给出明确失败原因
```

---

## 18. 最终验收标准

完成后必须满足：

```text
1. 用户可以通过 Web UI 完成首次配置
2. 用户可以通过 UI 手动运行一次 GitHub 抓取
3. 用户可以看到每日推荐卡片
4. 每条推荐都有摘要和推荐理由
5. 用户可以收藏内容
6. 收藏内容可以在 Knowledge 页面看到
7. 用户可以忽略、不感兴趣、稍后阅读
8. 用户可以配置飞书 Webhook
9. 用户可以收到飞书测试消息
10. 每日简报可以推送到飞书
11. Dashboard 可以看到运行状态
12. Job Logs 可以看到失败原因
13. 所有敏感配置都来自 .env 或 DB app_settings，不在代码中硬编码
14. 通过 UI 修改配置后不需要重启服务即可生效
15. 当前只实现 GitHub 信息源，不实现其他来源
16. 当前只实现飞书 Webhook，不实现飞书开放平台应用机器人
17. 现有 GitHub MVP 主流程仍然可用
18. 前端视觉符合 Warm Linear Knowledge Workspace，不是默认模板感
```

---

## 19. 给 opencode 的执行提示

执行时请遵循：

```text
1. 先检查项目结构，再制定最小修改计划
2. 不要大规模重构
3. 先完成 P0，再做 P1
4. 任何新增配置必须进 .env.example
5. 任何 secret 不得输出到日志
6. UI 必须让用户不用看命令行也能完成核心操作
7. 前端视觉参考 Linear 的结构和克制感，但使用暖色个人知识工作台风格
8. 所有颜色走 CSS variables / Tailwind tokens
9. 先做一个 default warm theme，预留后续主题扩展
10. 完成后运行 build / lint / typecheck / 可用测试
```

---

## 20. 最终交付目标

交付后，OMKA 应从：

```text
一个能跑通 GitHub MVP 的本地项目
```

升级为：

```text
一个用户可以通过 Web UI 配置、运行、查看、反馈、收藏，并能通过飞书每天收到个性化 GitHub 技术简报的个人知识助手产品雏形。
```
