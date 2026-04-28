# OMKA 产品化阶段可行性分析报告

> 基于当前 MVP 代码审查与 `omka_next_plan.md` 计划分析  
> 日期：2026-04-28  
> 审查范围：37 个 Python 文件、配置系统、数据库模型、API 路由、Pipeline 全流程

---

## 一、当前项目状态快照

### 1.1 技术栈现状

| 模块 | 现状 | 计划要求 | 差异 |
|---|---|---|---|
| 后端框架 | FastAPI ✅ | FastAPI | 一致 |
| ORM | SQLModel + SQLAlchemy ✅ | SQLModel | 一致 |
| 数据库 | SQLite ✅ | SQLite | 一致 |
| 定时任务 | APScheduler ✅ | APScheduler | 一致 |
| HTTP 客户端 | httpx ✅ | httpx | 一致 |
| 配置系统 | Pydantic BaseSettings + `@lru_cache` 单例 | 动态读写 `.env` | ⚠️ **架构差异** |
| 前端 | **不存在** | Vite + React + TS + Tailwind + shadcn/ui | ❌ 缺失 |
| 测试 | pytest + pytest-asyncio（仅 test_api.py） | 完整的 build/lint/typecheck | ⚠️ 不完备 |
| Lint/Formatter | 无配置 | ruff / mypy 等 | ❌ 缺失 |
| 前端构建 | 无 | npm run build / lint / typecheck | ❌ 缺失 |

### 1.2 数据库模型现状

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  SourceConfig   │────▶│    RawItem      │────▶│ NormalizedItem  │
│   (8 张表之一)   │     │   (原始数据)     │     │  (规范化数据)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                       │
                                                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   FetchRun      │     │  UserFeedback   │◀────│ CandidateItem   │
│ (任务运行记录)   │     │   (用户反馈)     │     │  (候选推荐)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │ KnowledgeItem   │
                                              │   (知识库)       │
                                              └─────────────────┘
                              ┌─────────────────┐
                              │  RequestCache   │
                              │  (HTTP 缓存)     │
                              └─────────────────┘
```

**已覆盖计划模型的对比：**

| 计划模型 | 现状模型 | 差异 |
|---|---|---|
| `candidate_items` (5 种状态) | `candidate_items` (3 种状态) | ⚠️ 缺少 `disliked` / `read_later` |
| `user_feedback` (`action` 字段) | `user_feedback` (`feedback_type` 字段) | ⚠️ 字段名不一致 |
| `job_runs` | `fetch_runs` | ⚠️ 表名/字段不完全匹配 |
| `notification_runs` | **不存在** | ❌ 缺失 |
| `knowledge_items` | `knowledge_items` | ✅ 基本一致 |

### 1.3 API 路由现状

| 计划 API | 现状 API | 差异 |
|---|---|---|
| `/api/settings` | **不存在** | ❌ 缺失 |
| `/api/onboarding/*` | **不存在** | ❌ 缺失 |
| `/api/sources` | `/sources` (无前缀) | ⚠️ 前缀不一致 |
| `/api/digests/*` | `/digests/*` | ⚠️ 前缀不一致 |
| `/api/candidates/*` | `/candidates/*` | ⚠️ 前缀不一致 |
| `/api/knowledge/*` | `/knowledge/*` | ⚠️ 前缀不一致 |
| `/api/notifications/*` | **不存在** | ❌ 缺失 |
| `/api/jobs/*` | **不存在** | ❌ 缺失 |

**当前已有端点：**
- `GET /sources`, `POST /sources`, `PUT /sources/{id}`, `DELETE /sources/{id}`, `POST /sources/{id}/run`
- `GET /candidates`, `POST /candidates/{id}/confirm`, `POST /candidates/{id}/ignore`, `POST /candidates/{id}/feedback`
- `POST /digests/run-ranking`, `GET /digests/ranked`, `POST /digests/run-today`
- `GET /knowledge`, `GET /knowledge/{id}`, `POST /knowledge`, `DELETE /knowledge/{id}`, `POST /knowledge/{id}/feedback`
- `GET /health`

### 1.4 Pipeline 全流程现状

```
SourceConfig → fetch_all_sources() → RawItem
                                    ↓
                              clean_and_normalize() → NormalizedItem
                                                      ↓
                                                dedup_and_create_candidates() → CandidateItem
                                                                                ↓
                                                                          rank_candidates() → 打分 + 排序
                                                                                                  ↓
                                                                                            generate_digest() → Markdown
```

**结论：** Pipeline 5 阶段全部已实现，代码质量良好，各阶段独立 try/catch，不互相阻断。这是产品化的坚实基础。

### 1.5 配置系统现状（关键风险点）

当前实现：
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    github_token: str = ""
    llm_api_key: str = ""
    # ... 其他字段

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings

settings = get_settings()  # 全局单例，启动时加载
```

**问题：**
- `@lru_cache` 意味着配置在进程生命周期内只加载一次
- Pydantic BaseSettings 设计为**启动时读取**，不支持运行时热重载
- 计划要求"通过 UI 更新 .env 后服务可读取新配置"，这与当前架构冲突

---

## 二、计划可行性总体评估

### 2.1 评估矩阵

| 计划模块 | 可行性 | 风险等级 | 工作量 | 说明 |
|---|---|---|---|---|
| Web UI 基础框架 (Vite+React+TS+Tailwind+shadcn/ui) | ✅ 高 | 🟡 中 | 中等 | 前端从零搭建，技术选型合理，shadcn/ui 组件丰富 |
| Warm Linear 主题 token | ✅ 高 | 🟢 低 | 小 | 设计规范已明确，只需实现 CSS 变量 |
| App Shell (Sidebar + PageHeader) | ✅ 高 | 🟢 低 | 小 | 标准布局模式，无技术难点 |
| Settings API + 页面 | ⚠️ 中 | 🔴 高 | 较大 | **.env 动态读写是架构挑战** |
| Onboarding 页面 | ✅ 高 | 🟢 低 | 中等 | 前端 Stepper + 表单，标准模式 |
| Sources 页面 | ✅ 高 | 🟢 低 | 小 | 已有后端 API，只需前端对接 |
| Digest 推荐卡片 | ✅ 高 | 🟢 低 | 中等 | 已有 `/digests/ranked` API |
| Candidate 操作 | ✅ 高 | 🟡 中 | 小 | 需新增 `dislike`/`read-later` 端点 + 改状态字段 |
| Knowledge 页面 | ✅ 高 | 🟢 低 | 小 | 已有后端 API，只需前端对接 |
| Run Now 按钮 | ✅ 高 | 🟢 低 | 极小 | 已有 `/digests/run-today` |
| Feishu Webhook 推送 | ✅ 高 | 🟡 中 | 中等 | HTTP POST 即可，需设计消息模板 |
| Dashboard 状态概览 | ✅ 高 | 🟡 中 | 中等 | 需新增聚合查询 API |
| Job Logs 页面 | ✅ 高 | 🟢 低 | 小 | 已有 `FetchRun` 表，需扩展字段 |
| .env 标准化 | ⚠️ 中 | 🔴 高 | 较大 | **变量命名冲突 + 动态读写** |
| 反馈影响排序 | ✅ 高 | 🟡 中 | 中等 | YAML 权重文件 + 排序时读取 |
| 主题预留扩展 | ✅ 高 | 🟢 低 | 极小 | CSS 结构预留即可 |

### 2.2 综合结论

| 维度 | 结论 |
|---|---|
| **技术可行性** | ✅ **高度可行**。技术选型合理，后端基础扎实，前端栈成熟 |
| **架构兼容性** | ⚠️ **需要适配**。配置系统、API 前缀、数据库字段需调整 |
| **工作量估算** | **12-18 天**（单人全职），其中前端占 40%，后端 API 占 35%，配置系统占 15%，测试打磨占 10% |
| **风险可控性** | ⚠️ **中等**。最大风险是 `.env 动态读写`，其次是前端工程搭建 |

---

## 三、关键风险识别与缓解

### 风险 1：.env 动态读写（🔴 高风险）

**问题描述：**
当前 `Pydantic BaseSettings + @lru_cache` 单例模式不支持运行时热重载。计划要求 UI 修改 .env 后服务立即生效，这会导致：
1. 写入 .env 后，运行中的进程仍使用旧值
2. 需要重启服务才能读取新配置
3. 如果改为动态读取，所有依赖 `settings` 单例的代码都需要改造

**建议方案（推荐）：**
```
┌─────────────────────────────────────────────────────────────┐
│                    配置分层架构（优化后）                      │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: .env 文件                                          │
│  - 作为启动时的**兜底配置**                                    │
│  - 不通过 UI 修改（避免进程间同步问题）                        │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: DB Settings 表（新增）                              │
│  - UI 修改时写入数据库                                        │
│  - 运行时从数据库读取                                         │
│  - 优先级高于 .env                                            │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: 内存缓存（EnvSettingsService）                      │
│  - 读取时先查缓存                                             │
│  - 缓存失效时间 60 秒                                         │
│  - 支持手动刷新                                               │
└─────────────────────────────────────────────────────────────┘
```

**具体实现：**
1. 新增 `app_settings` 数据库表，存储 key-value 配置
2. `SettingsService` 提供 `get(key)` / `set(key, value)` / `reload()`
3. 启动时：`.env` 加载默认值 → DB 覆盖 → 内存缓存
4. UI 修改时：写入 DB → 清除缓存 → 下次读取自动刷新
5. 敏感字段（token/webhook）在 DB 中加密存储或至少 masked

**为什么不直接改写 .env？**
- 文件写入不是原子操作，并发修改可能损坏
- 多进程部署时，.env 修改无法通知其他进程
- 没有变更审计（谁改了什么）
- 重启服务才能生效，用户体验差

### 风险 2：环境变量命名冲突（🟡 中风险）

**问题描述：**
计划建议的 `.env.example` 使用 `OMKA_` 前缀（如 `OMKA_APP_ENV`），但当前代码使用无前缀命名（如 `app_env`）。

**现状 .env 变量名：**
```
GITHUB_TOKEN, LLM_PROVIDER, APP_NAME, API_HOST, API_PORT, DATABASE_URL, ...
```

**计划 .env 变量名：**
```
OMKA_APP_ENV, OMKA_BACKEND_HOST, OMKA_BACKEND_PORT, GITHUB_TOKEN, ...
```

**影响：**
- 如果强制切换，现有用户的 `.env` 文件将失效
- Pydantic 字段名和 env 变量名需要重新映射

**建议：**
保持当前命名不变。理由：
1. 已有代码和文档都使用当前命名
2. 切换成本 > 收益（只是命名风格差异）
3. 计划的核心价值是功能实现，不是变量命名标准化
4. 如果坚持要统一，使用 `env_prefix="OMKA_"` + 兼容层

### 风险 3：API 前缀变更（🟡 中风险）

**问题描述：**
计划建议所有 API 加 `/api` 前缀，但当前无前缀。

**影响：**
- 变更前缀会导致现有前端/客户端/测试全部失效
- 新增前端完全可以适配现有前缀

**建议：**
保持现有 API 前缀不变。前端请求时直接请求 `/sources`, `/candidates` 等。理由：
1. 当前 API 已经可用，无需为了"美观"破坏兼容性
2. 如果需要，可以在 Nginx/反向代理层面做路径映射
3. 计划的核心目标是产品可用性，不是 API 路径标准化

### 风险 4：前端工程复杂度（🟡 中风险）

**问题描述：**
计划要求使用 shadcn/ui，这需要：
1. `npx shadcn@latest init` 初始化
2. 逐个安装组件（Button, Card, Input, Dialog, ...）
3. 维护 `components.json` 配置
4. Tailwind CSS 配置与 shadcn 预设兼容

**潜在问题：**
- shadcn/ui 在 Windows 上初始化有时会有路径问题
- 组件数量多时，依赖管理复杂
- 需要 `clsx` + `tailwind-merge` + `class-variance-authority`

**建议：**
1. 使用 `npx shadcn@latest init --yes --template vite --base-color stone` 快速初始化
2. 只安装核心组件（button, card, input, dialog, badge, select, tabs, toast）
3. 不安装不需要的（calendar, chart, carousel 等）
4. 保留一个 `components/ui/` 目录，不分散到各页面

### 风险 5：Candidate 状态扩展（🟢 低风险）

**问题描述：**
当前 `CandidateItem.status` 支持 `pending/ignored/confirmed`，计划需要 `pending/confirmed/ignored/disliked/read_later`。

**实施：**
1. 修改 `CandidateItem.status` 字段的 Literal 类型
2. 新增 `/candidates/{id}/dislike` 和 `/candidates/{id}/read-later` 端点
3. 更新前端操作按钮
4. **注意**：`disliked` 和 `read_later` 也是"不再展示在 digest"的状态，查询时需过滤

### 风险 6：Job Runs / Notification Runs（🟢 低风险）

**问题描述：**
计划有独立的 `job_runs` 和 `notification_runs` 表，但当前只有 `fetch_runs`。

**建议：**
复用并扩展 `fetch_runs` 表：
1. 将 `fetch_runs` 改名为 `job_runs`（可选，不改也行）
2. 新增字段：`job_type` 支持 `github_daily_job/manual_run/digest_generation/feishu_push`
3. 新增 `notification_runs` 表
4. 在 `daily_job.py` 中记录各阶段状态到 `job_runs`

### 风险 7：飞书 Webhook 安全性（🟢 低风险）

**问题描述：**
飞书 Webhook URL 包含敏感信息，计划要求：
- 不在日志中输出完整 URL
- 不在 API 中返回完整 URL
- 支持 secret 签名

**实施：**
1. URL 存储时 masked（只显示前 10 字符 + ...）
2. 日志中只输出 `Feishu webhook: https://open.feishu.cn/.../masked`
3. 支持飞书自定义机器人的 `timestamp + sign` 签名验证

---

## 四、计划与现状的具体差异清单

### 4.1 需要新增的后端模块

| 模块 | 文件 | 复杂度 |
|---|---|---|
| Settings Service | `app/core/env_writer.py` + `app_settings` DB 表 | 高 |
| Settings API | `app/api/routes_settings.py` | 中 |
| Onboarding API | `app/api/routes_onboarding.py` | 低 |
| Jobs API | `app/api/routes_jobs.py` | 低 |
| Notification Service | `app/notifications/base.py` + `service.py` + `channels/feishu_webhook.py` | 中 |
| Notification API | `app/api/routes_notifications.py` | 低 |
| Feedback Service | `app/feedback/service.py` | 低 |

### 4.2 需要修改的现有模块

| 模块 | 修改内容 | 复杂度 |
|---|---|---|
| `CandidateItem.status` | 增加 `disliked`, `read_later` | 低 |
| `routes_feedback.py` | 新增 `dislike`, `read-later` 端点 | 低 |
| `daily_job.py` | 集成 Feishu 推送 + job_runs 记录 | 中 |
| `config.py` | 新增 Feishu 相关配置项 | 低 |
| `.env.example` | 新增飞书配置项 | 低 |
| `main.py` | 注册新路由 | 低 |

### 4.3 需要新增的前端模块

| 模块 | 文件/目录 | 复杂度 |
|---|---|---|
| 前端工程 | `frontend/` 全部 | 中 |
| API Client | `frontend/src/api/*.ts` | 低 |
| 主题系统 | `frontend/src/styles/theme.css` + `globals.css` | 低 |
| App Shell | `frontend/src/components/app-shell.tsx` + `app-sidebar.tsx` | 中 |
| Dashboard | `frontend/src/pages/DashboardPage.tsx` | 中 |
| Onboarding | `frontend/src/pages/OnboardingPage.tsx` | 中 |
| Sources | `frontend/src/pages/SourcesPage.tsx` | 低 |
| Digest | `frontend/src/pages/DigestPage.tsx` | 中 |
| Knowledge | `frontend/src/pages/KnowledgePage.tsx` | 低 |
| Read Later | `frontend/src/pages/ReadLaterPage.tsx` | 低 |
| Settings | `frontend/src/pages/SettingsPage.tsx` | 中 |
| Job Logs | `frontend/src/pages/JobLogsPage.tsx` | 低 |

---

## 五、优化建议（对计划的直接优化）

### 5.1 配置系统优化（强烈建议）

**原方案：**
```text
所有配置通过 UI 写入 .env，服务热重载读取
```

**优化后方案：**
```text
1. .env 作为启动时的兜底配置（只读）
2. 新增 app_settings 数据库表（UI 可写）
3. 运行时优先读取 DB Settings，缺失时回退到 .env
4. 敏感字段在 DB 中 masked，API 返回时脱敏
5. 修改配置后不需要重启服务
```

**理由：**
- 避免 .env 文件并发写入损坏
- 支持多进程/容器部署
- 有变更审计（可记录 updated_at）
- 不破坏 Pydantic Settings 的单例设计

### 5.2 环境变量命名优化

**原方案：**
```text
统一加 OMKA_ 前缀
```

**优化后方案：**
```text
保持当前命名不变
新增配置项也保持当前风格（大写下划线，无统一前缀）
```

**理由：**
- 已有代码、文档、用户配置都使用当前命名
- 切换成本 > 收益
- 这是个人项目，不需要企业级命名规范

### 5.3 API 前缀优化

**原方案：**
```text
所有 API 加 /api 前缀
```

**优化后方案：**
```text
保持现有前缀不变（无 /api）
前端适配现有路径
```

**理由：**
- 当前 API 已经工作，无需破坏兼容性
- 可在反向代理层面做路径映射（如果需要）
- 减少不必要的后端修改

### 5.4 前端目录优化

**原方案：**
```text
frontend/src/
  api/
  components/
  pages/
  styles/
  types/
  lib/
```

**优化后方案：**
```text
frontend/src/
  api/              # API 客户端
  components/
    ui/             # shadcn/ui 组件（自动安装）
    layout/         # AppShell, Sidebar, PageHeader
    cards/          # DigestCard, KnowledgeCard, SourceCard
    common/         # StatusBadge, EmptyState, LoadingState
  pages/            # 页面组件
  hooks/            # 自定义 hooks（useSettings, useSources 等）
  types/            # TypeScript 类型
  lib/              # 工具函数（cn, date, format）
  styles/
    globals.css
    theme.css
```

**理由：**
- 增加 `hooks/` 目录，封装数据获取逻辑
- `components/ui/` 专用于 shadcn 组件，与业务组件分离
- 更符合 React 社区惯例

### 5.5 执行顺序优化

**原方案：**
```text
Step 1: 项目检查
Step 2: 配置系统标准化
Step 3: 前端基础工程
Step 4: Settings 页面
Step 5: Onboarding 页面
Step 6: Digest + Candidate 操作
Step 7: Knowledge 页面
Step 8: 飞书 Webhook
Step 9: Dashboard + Logs
```

**优化后方案：**
```text
Step 1: 项目检查 + 后端基础调整（1 天）
  - 确认数据库模型调整（Candidate 状态、job_runs 扩展）
  - 新增 app_settings 表
  - 新增 Feishu 配置项到 config.py 和 .env.example

Step 2: 前端基础工程 + App Shell（2 天）
  - 初始化 Vite + React + TS + Tailwind + shadcn/ui
  - 实现 theme.css
  - 实现 AppShell + Sidebar + 路由
  - 实现 API client

Step 3: Settings API + Settings 页面（2 天）
  - 实现 SettingsService（DB 层）
  - 实现 Settings API（GET/PUT + test 端点）
  - 实现 Settings 前端页面
  - 验收：可通过 UI 配置并持久化

Step 4: Sources + Onboarding 页面（2 天）
  - 实现 Onboarding 前端（Stepper UI）
  - 对接已有 Sources API
  - 验收：新用户 5 分钟完成配置

Step 5: Digest + Candidate 操作（2 天）
  - 新增 dislike / read-later 后端端点
  - 实现 Digest 卡片前端
  - 实现 save/ignore/dislike/read-later 按钮
  - 验收：操作后状态持久化

Step 6: Knowledge + Read Later 页面（1 天）
  - 对接已有 Knowledge API
  - 实现 Read Later 页面（或 Digest 的 tab）

Step 7: 飞书 Webhook（2 天）
  - 实现 NotificationChannel 基类
  - 实现 FeishuWebhookChannel
  - 集成到 daily_job.py
  - 实现测试推送 API
  - 验收：测试推送成功

Step 8: Dashboard + Job Logs（1-2 天）
  - 实现 Dashboard 聚合 API
  - 实现 Dashboard 前端
  - 实现 Job Logs 页面
  - 验收：能看到运行状态

Step 9: 打磨 + 测试（1-2 天）
  - Loading / Empty / Error states
  - 移动端适配
  - 端到端验证
```

**总计：12-14 天**

### 5.6 数据模型优化

**原方案（job_runs）：**
```text
新增 job_runs 表
```

**优化后方案：**
```text
复用现有 fetch_runs 表，改名为 job_runs（可选）
扩展字段：
  - job_type: github_daily_job / manual_run / digest_generation / feishu_push
  - fetched_repo_count
  - fetched_release_count
  - fetched_search_result_count
  - digest_item_count
  - metadata_json

新增 notification_runs 表
```

**理由：**
- 减少迁移复杂度
- 现有 FetchRun 的字段基本覆盖需求

### 5.7 错误处理优化

**原方案：**
```text
所有用户可见错误必须人类可读
```

**优化后建议（补充）：**
```text
1. 后端定义标准错误码枚举
2. 前端根据错误码显示对应文案（支持 i18n 预留）
3. 错误响应格式统一：{ "error_code": "GITHUB_TOKEN_INVALID", "message": "...", "detail": "..." }
4. 日志中记录完整 traceback，但 API 只返回 message
```

---

## 六、验证策略

### 6.1 每个 Step 的验收标准

| Step | 验收标准 |
|---|---|
| Step 1 | `python -m omka.app.main` 启动成功，数据库无报错 |
| Step 2 | `npm run dev` 启动成功，Warm Linear 主题生效，页面可切换 |
| Step 3 | Settings 页面可保存配置，刷新后配置不丢失，secret 被 masked |
| Step 4 | 新用户可通过 Onboarding 完成配置，Sources 页面可增删改 |
| Step 5 | Digest 页面展示推荐卡片，save/ignore/dislike/read-later 操作后状态持久化 |
| Step 6 | Knowledge 页面展示收藏内容，Read Later 页面展示稍后阅读内容 |
| Step 7 | 飞书测试推送成功，推送失败不影响主任务，Dashboard 显示推送状态 |
| Step 8 | Dashboard 显示今日运行状态，Job Logs 展示历史记录 |
| Step 9 | 端到端验证：配置 → 运行 → 查看 → 收藏 → 飞书推送 |

### 6.2 建议新增的自动化检查

```text
# 后端
python -m omka.app.main  # 启动检查
pytest tests/            # 运行测试（需补充）

# 前端
cd frontend && npm run build      # 构建检查
cd frontend && npm run lint       # ESLint 检查（需配置）
cd frontend && npm run typecheck  # TypeScript 检查（需配置）
```

---

## 七、最终结论

### 7.1 可行性判断

| 维度 | 评分 | 说明 |
|---|---|---|
| 技术可行性 | ⭐⭐⭐⭐⭐ | 技术栈成熟，后端基础扎实 |
| 架构兼容性 | ⭐⭐⭐⭐ | 需适配配置系统和 API 前缀，但改动可控 |
| 工作量合理性 | ⭐⭐⭐⭐ | 12-14 天单人全职合理，P0 部分约 8-10 天 |
| 风险控制 | ⭐⭐⭐⭐ | 最大风险（.env 读写）有明确缓解方案 |
| 后续扩展性 | ⭐⭐⭐⭐⭐ | Connector/Channel/Store 预留接口设计良好 |

**综合：✅ 高度可行，建议立即启动。**

### 7.2 启动前必须决策的 3 个问题

1. **配置系统方案**：是否接受"DB Settings + .env 兜底"方案？（强烈建议接受）
2. **API 前缀**：是否保持现有无 `/api` 前缀？（建议保持）
3. **环境变量命名**：是否保持当前命名风格？（建议保持）

### 7.3 关键成功因素

1. **严格执行 P0 边界**：不做 RSS、不做知识图谱、不做多 Agent
2. **配置系统优先**：Step 1 就确定配置方案，后续所有功能依赖它
3. **前端框架先行**：Step 2 完成前端工程，后续并行开发前后端
4. **每日验证**：每个 Step 完成后必须运行验证命令
5. **不炫技**：Warm Linear 风格的核心是克制和留白，不是动画和特效

---

*本报告基于对当前 MVP 代码的完整审查和 `omka_next_plan.md` 的深度分析生成，供产品化阶段执行参考。*
