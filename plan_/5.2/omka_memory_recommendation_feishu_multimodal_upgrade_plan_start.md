# OMKA 记忆、推荐、飞书与多模态升级计划 — 可行性分析与启动文档

> 分析日期：2026-05-02
> 基于：omka_memory_recommendation_feishu_multimodal_upgrade_plan.md
> 分析方式：代码审查 + 架构评估 + 依赖分析

---

## 1. 执行摘要

### 1.1 总体结论

**该升级计划技术可行，但工作量显著。** 当前项目具备良好的基础架构（FastAPI + SQLModel + 飞书 Bot + React），但距离计划目标存在明显差距。预计完整实施需要 **25-40 人天**，建议分阶段交付，优先构建"记忆 + 推荐解释"核心能力。

### 1.2 关键发现

| 维度 | 当前状态 | 与目标的差距 |
|---|---|---|
| 数据库模型 | 13 个表，结构清晰 | 需新增 9 个表（+69%） |
| API 层 | 9 个路由文件，基础 CRUD 完整 | 大量接口需新增，部分现有接口需重构 |
| 飞书命令 | 6 个基础命令 | 计划需 40+ 命令，差距巨大 |
| Agent 能力 | 简单问答，无执行能力 | 需新增 ActionService、权限模型、审计 |
| 推荐系统 | 4 维度加权，无解释 | 需新增解释生成、反馈学习、记忆关联 |
| 前端页面 | 8 个页面 | 需新增 4-5 个管理页面 |
| 多模态 | 完全缺失 | 需新增资产表、存储、解析链路 |

### 1.3 可行性评级

| Phase | 可行度 | 工作量 | 风险等级 | 建议优先级 |
|---|---|---|---|---|
| Phase 0: 基础治理 | ⭐⭐⭐⭐⭐ 高 | 1-2 天 | 🟢 低 | P0（可合并） |
| Phase 1: 统一记忆内核 | ⭐⭐⭐⭐ 中高 | 4-6 天 | 🟡 中 | P0 |
| Phase 2: 推荐解释与反馈 | ⭐⭐⭐⭐ 中高 | 4-5 天 | 🟡 中 | P0 |
| Phase 3: 飞书 Agent 执行通道 | ⭐⭐⭐ 中 | 5-8 天 | 🟠 中高 | P0 |
| Phase 4: 主动推送策略 | ⭐⭐⭐⭐ 中高 | 3-5 天 | 🟡 中 | P1 |
| Phase 5: 多模态资产 P0 | ⭐⭐⭐ 中 | 5-8 天 | 🟠 中高 | P1 |
| Phase 6: Web 管理页面 | ⭐⭐⭐⭐⭐ 高 | 4-7 天 | 🟢 低 | P2 |

---

## 2. 当前项目基线详细评估

### 2.1 数据库层

当前已有 **16 个表**（db.py），设计质量良好：

```
SourceConfig          - 数据源配置
FetchRun              - 抓取运行记录
RequestCache          - HTTP 请求缓存
RawItem               - 原始抓取数据
NormalizedItem        - 规范化数据
CandidateItem         - 候选推荐条目
KnowledgeItem         - 知识库条目
UserFeedback          - 用户反馈
AppSetting            - 应用配置
NotificationRun       - 通知推送记录
FeishuTokenCache      - 飞书 Token 缓存
FeishuMessageRun      - 飞书消息发送记录
FeishuEventLog        - 飞书事件日志
FeishuDirectConversation - 飞书单聊绑定
ConversationMessage   - 对话消息历史
AgentRun              - Agent 调用记录
```

**评估**：现有模型遵循统一模式（`BaseSchema` + `SQLModel` + `JSON` 字段），新增 9 个表的实现成本可控。但需注意：
- SQLite 作为单文件数据库，表数量膨胀后查询性能可能下降
- 建议后续评估迁移到 PostgreSQL 的必要性

### 2.2 API 层

已审查 9 个路由文件，关键问题：

| 文件 | 当前问题 | 影响 |
|---|---|---|
| `routes_sources.py:61` | `update_source` 使用 `dict[str, Any]` | 类型不安全，与计划要求的 Pydantic 模型冲突 |
| `routes_feedback.py:115` | `feedback_candidate` 使用 `dict[str, Any]` | 同上 |
| `routes_knowledge.py:49` | `create_knowledge` 使用 `dict[str, Any]` | 同上 |
| `routes_digest.py:10-13` | 直接调用 `rank_candidates()` | 违反分层原则，需下沉到 Service 层 |
| `routes_settings.py` | 多处使用 `dict[str, Any]` | 同上 |

**评估**：API 层的基础模式清晰（`APIRouter` + `get_session()`），但存在计划中明确指出的"已知违规"。Phase 0 需要修复这些问题，否则新增 API 会建立在不稳定基础上。

### 2.3 飞书集成层

当前飞书命令仅支持 6 个：

```python
handlers = {
    "help":    self._handle_help,
    "bind":    self._handle_bind,
    "status":  self._handle_status,
    "latest":  self._handle_latest,
    "run":     self._handle_run,      # 仅管理员
    "chat":    self._handle_chat,     # 转发到 Agent
}
```

Agent 对话通过 `SimpleKnowledgeAgentGateway` 实现，核心逻辑：
- `ContextBuilder` 构建上下文（最近 6 条消息 + Digest + Knowledge + Candidate + Profile）
- `SimpleKnowledgeAgent` 调用 LLM 生成回答
- 没有长期记忆、没有执行能力、没有权限控制

**评估**：飞书集成的基础架构完整（事件处理、Token 管理、消息发送、单聊绑定），但命令体系过于单薄。扩展到 40+ 命令需要重构 `CommandRouter`，建议采用"自然语言优先 + 斜杠命令兜底"的混合模式（计划中已提出）。

### 2.4 推荐系统

当前 `ranker.py` 实现：

```python
final_score =
    interest_score   * 0.40 +
    project_score    * 0.30 +
    freshness_score  * 0.15 +
    popularity_score * 0.15
```

- 基于关键词匹配（非语义）
- 无记忆关联
- 无推荐解释（`recommendation_reason` 由 LLM 生成，但无结构化解释）
- 无反馈学习闭环（confirm/dislike/ignore 只改状态）

**评估**：当前推荐系统简单但可用。升级到计划中的"可解释推荐"需要：
1. 重构 `ranker.py` 为 `RecommendationService`
2. 新增 `RecommendationRun` + `RecommendationDecision` 表
3. 推荐解释需要额外的 LLM 调用（成本增加）
4. 反馈闭环需要修改 `routes_feedback.py` 的业务逻辑

### 2.5 前端层

当前 8 个页面：

```
/           - Dashboard（仪表盘）
/onboarding - 引导页
/sources    - 信息源管理
/digest     - 每日简报
/knowledge  - 知识库
/read-later - 稍后阅读
/settings   - 设置
/job-logs   - 任务日志
```

技术栈：React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui

**评估**：前端架构现代化，组件化程度高。新增 4-5 个管理页面的工作量可控，但需要：
- 新增 API client 模块（memory, recommendation, push, assets）
- 新增 hooks 和 pages
- 修复 API client 硬编码地址问题（`http://127.0.0.1:8000`）

### 2.6 依赖与外部能力

当前 `requirements.txt` 共 12 个核心依赖：

```
fastapi, uvicorn, sqlalchemy, sqlmodel, httpx, apscheduler,
pydantic, pydantic-settings, pyyaml, python-dotenv, lark-oapi, pytest
```

**缺失的关键依赖**（多模态需要）：

| 能力 | 需要依赖 | 当前状态 |
|---|---|---|
| OCR（图片文字识别） | `pytesseract` / `easyocr` | ❌ 缺失 |
| PDF 文本提取 | `PyPDF2` / `pdfplumber` | ❌ 缺失 |
| 图像处理 | `Pillow` | ❌ 缺失 |
| 视觉模型调用 | 依赖 LLM 提供商 | ⚠️ 部分支持 |

**评估**：多模态资产的 P0 实现需要新增 3-4 个依赖，增加部署复杂度。建议 Phase 5 开始时再引入。

---

## 3. 各模块可行性详细分析

### 3.1 Phase 0: 基础治理与编码清理

**可行性：⭐⭐⭐⭐⭐（极高）**

| 任务 | 工作量 | 风险 | 说明 |
|---|---|---|---|
| 修复中文乱码 | 0.5 天 | 🟢 无 | 全局搜索替换，低风险 |
| 补 Pydantic 请求模型 | 0.5 天 | 🟢 无 | 4 个接口需补模型 |
| 修复 cleaner 全量读取 | 0.5 天 | 🟡 低 | SQL 层加 `.where()` 过滤 |
| routes_digest 下沉 | 0.5 天 | 🟢 无 | 提取到 Service 层 |
| SQLite 迁移策略 | 0.5 天 | 🟡 低 | 新增表需手动迁移或保留自动建表 |

**关键发现**：
- `py_compile` 和 `tsc -b` 检查简单，但计划中提到的"前端页面乱码"需要具体定位
- `cleaner.py:15` 的全量读取问题需要确认当前实现是否已存在性能问题（当前数据量 59 条 RawItem，暂无性能问题）

**建议**：Phase 0 不要单独作为一个阶段，而是作为每个 Phase 的前置任务。例如 Phase 1 开始前先修复编码和模型问题。

### 3.2 Phase 1: 统一记忆内核

**可行性：⭐⭐⭐⭐（高）**

**核心交付物**：
- `MemoryItem` 表（9 个字段 + JSON 扩展）
- `MemoryEvent` 表（审计日志）
- `MemoryService`（CRUD + 查询 + 导入）
- `MemoryExtractor`（从对话抽取候选记忆）
- 飞书命令：`memory list/add/confirm/reject/delete`
- API：`/memories/*`

**工作量分解**：

| 任务 | 工作量 | 风险 | 依赖 |
|---|---|---|---|
| MemoryItem + MemoryEvent 模型 | 0.5 天 | 🟢 低 | 无 |
| MemoryService 实现 | 1 天 | 🟡 中 | 模型 |
| Profile 导入（YAML → Memory） | 0.5 天 | 🟡 中 | Service |
| ContextBuilder 接入 memory | 1 天 | 🟡 中 | Service |
| MemoryExtractor（对话抽取） | 1-2 天 | 🟠 中高 | LLM 能力 |
| 飞书 memory 命令 | 1 天 | 🟡 中 | Service |
| Memory API | 0.5 天 | 🟢 低 | Service |

**关键风险点**：

1. **MemoryExtractor 的准确性**：从对话中自动抽取记忆需要 LLM 配合。如果抽取质量差，会产生大量垃圾记忆，反而增加用户负担。
   - **缓解**：先实现保守策略（只抽取高置信度、用户明确表达偏好的内容），默认进入 `candidate` 状态，需用户确认。

2. **ContextBuilder 重构**：当前 ContextBuilder 已取最近消息、Digest、Knowledge、Candidate，接入 Memory 后上下文可能过长。
   - **缓解**：只接入 `active` 状态的高重要性记忆，限制数量（如 Top 10）。

3. **identity.md 解析**：当前 identity.md 是纯文本，没有结构化格式。
   - **缓解**：先按段落或关键词简单解析，后续再考虑结构化模板。

### 3.3 Phase 2: 推荐解释与反馈学习

**可行性：⭐⭐⭐⭐（高）**

**核心交付物**：
- `RecommendationRun` + `RecommendationDecision` 表
- `RecommendationService`（替代直接 `rank_candidates()`）
- 结构化推荐解释（`explanation_json`）
- 反馈闭环（confirm → 提升权重，dislike → 降低权重）
- 飞书命令：`why/more-like/dislike/later`

**工作量分解**：

| 任务 | 工作量 | 风险 | 依赖 |
|---|---|---|---|
| RecommendationRun + Decision 模型 | 0.5 天 | 🟢 低 | 无 |
| RecommendationService 重构 | 1-2 天 | 🟡 中 | 模型 |
| 推荐解释生成（LLM） | 1-2 天 | 🟠 中高 | LLM 成本 |
| 反馈闭环实现 | 1 天 | 🟡 中 | MemoryService |
| Digest + 飞书统一解释 | 0.5 天 | 🟡 中 | 解释生成 |
| 飞书推荐命令 | 0.5 天 | 🟡 中 | Service |

**关键风险点**：

1. **LLM 调用成本增加**：每条候选生成结构化解释需要额外 LLM 调用。假设每日 20 条候选，每次调用 500 tokens，按 OpenAI GPT-4o-mini 价格（$0.15/M input, $0.60/M output），每日成本约 $0.015，可接受。
   - **缓解**：解释生成可异步进行，失败时降级为简单模板解释。

2. **反馈学习的有效性**：简单的权重调整可能无法产生明显效果，需要足够多的反馈数据。
   - **缓解**：先记录反馈事件到 Memory，不急于实时调整权重，等数据积累后再启用动态调整。

3. **ranker.py 重构影响**：当前 `rank_candidates()` 被 `routes_digest.py` 和 `daily_job.py` 直接调用。
   - **缓解**：先包装一层 `RecommendationService`，保留原有接口兼容性，逐步迁移。

### 3.4 Phase 3: 飞书 Agent 任务执行通道

**可行性：⭐⭐⭐（中）**

**这是整个计划中工作量最大、风险最高的模块。**

**核心交付物**：
- `SystemAction` 审计表
- `ActionService`（封装所有系统操作）
- 权限模型（viewer/operator/admin）
- 高危操作二次确认机制
- 自然语言意图解析（NL → Action Draft）
- 扩展命令：source/candidate/knowledge/memory/config/push/job/asset

**工作量分解**：

| 任务 | 工作量 | 风险 | 依赖 |
|---|---|---|---|
| SystemAction 模型 | 0.5 天 | 🟢 低 | 无 |
| ActionService 框架 | 1-2 天 | 🟡 中 | 权限模型 |
| 权限模型实现 | 0.5 天 | 🟡 中 | 无 |
| 高危操作确认机制 | 1 天 | 🟠 中高 | ActionService |
| CommandRouter 扩展 | 2-3 天 | 🟠 中高 | ActionService |
| 自然语言意图解析 | 1-2 天 | 🟠 中高 | LLM + ActionService |

**关键风险点**：

1. **自然语言意图解析的稳定性**：用户自然语言表述多样，解析为结构化 action 的准确率难以保证。
   - **缓解**：明确"命令优先，自然语言兜底"策略。对于模糊意图，Agent 应询问澄清而不是猜测执行。

2. **ActionService 的复杂度**：需要封装 source、candidate、knowledge、memory、config、push、job 等所有操作，代码量会很大。
   - **缓解**：ActionService 可以分阶段实现，先支持查询操作（viewer 权限），再支持修改操作（operator/admin）。

3. **高危操作确认的状态管理**：需要维护 pending → needs_confirm → confirmed → executed 的状态流转，且有过期机制。
   - **缓解**：使用 `SystemAction` 表存储状态，过期时间可配置（如 5 分钟），通过 APScheduler 定期清理过期记录。

4. **权限模型与现有 admin 检查的兼容**：当前 `run` 命令通过 `feishu_admin_open_ids` 配置检查，需要迁移到新权限模型。
   - **缓解**：新权限模型兼容现有配置，`admin` 权限默认包含 `feishu_admin_open_ids` 中的用户。

### 3.5 Phase 4: 主动推送策略

**可行性：⭐⭐⭐⭐（高）**

**核心交付物**：
- `PushPolicy` + `PushEvent` 表
- `PushService`（策略检查 + 去重 + 发送）
- 4 类推送策略：daily_digest, high_score, read_later_reminder, system_alert
- 飞书命令：`push status/pause/resume/set/test`

**工作量分解**：

| 任务 | 工作量 | 风险 | 依赖 |
|---|---|---|---|
| PushPolicy + PushEvent 模型 | 0.5 天 | 🟢 低 | 无 |
| PushService 实现 | 1-2 天 | 🟡 中 | 模型 |
| 推送策略配置 | 0.5 天 | 🟡 中 | Service |
| 去重/安静时间/上限逻辑 | 0.5 天 | 🟡 中 | Service |
| 飞书 push 命令 | 0.5 天 | 🟡 中 | Service |

**关键风险点**：

1. **high_score 推送的阈值调优**：阈值过高导致推送太少，过低导致打扰用户。
   - **缓解**：阈值可配置，默认保守值，根据用户反馈调整。

2. **read_later 提醒的时效性**：需要定期检查 read_later 条目，但不宜过于频繁。
   - **缓解**：作为 APScheduler 的独立 job，每日检查一次即可。

### 3.6 Phase 5: 多模态知识资产 P0

**可行性：⭐⭐⭐（中）**

**核心交付物**：
- `KnowledgeAsset` + `AssetProcessingRun` 表
- `AssetService`（上传 + 处理 + 查询）
- 图片：保存 + 缩略图 + OCR/视觉摘要
- PDF：文本提取 + 摘要
- 飞书命令：`assets/status/summarize/save/delete`

**工作量分解**：

| 任务 | 工作量 | 风险 | 依赖 |
|---|---|---|---|
| KnowledgeAsset + ProcessingRun 模型 | 0.5 天 | 🟢 低 | 无 |
| AssetService 框架 | 1 天 | 🟡 中 | 模型 |
| 文件上传 API | 0.5 天 | 🟡 中 | 无 |
| 图片处理（Pillow + OCR） | 1-2 天 | 🟠 中高 | 新依赖 |
| PDF 文本提取 | 1-2 天 | 🟠 中高 | 新依赖 |
| 资产生成 CandidateItem | 0.5 天 | 🟡 中 | Pipeline |
| 飞书 asset 命令 | 0.5 天 | 🟡 中 | Service |

**关键风险点**：

1. **OCR 质量**：开源 OCR（如 Tesseract）对中文支持一般，可能需要额外训练数据。
   - **缓解**：P0 阶段可以先使用 LLM 视觉能力（如 GPT-4o）做图片描述，OCR 作为备选。

2. **PDF 解析的复杂性**：PDF 格式多样，纯文本提取可能丢失格式信息。
   - **缓解**：P0 只做纯文本提取，P1 再考虑版面理解。

3. **文件存储管理**：需要管理 `data/assets/` 目录，考虑磁盘空间、文件清理。
   - **缓解**：限制单个文件大小（如 10MB），定期清理 `failed` 状态的资产。

4. **新增依赖的部署复杂度**：
   - `Pillow` - 轻量，通常无问题
   - `pytesseract` - 需要安装 Tesseract OCR 引擎（系统级依赖）
   - `pdfplumber` / `PyPDF2` - Python 纯库，无问题
   - **缓解**：文档中明确说明系统级依赖安装步骤。

### 3.7 Phase 6: Web 管理页面补齐

**可行性：⭐⭐⭐⭐⭐（极高）**

**核心交付物**：
- Memory 管理页面
- Recommendation explanation 页面
- Push policy 页面
- Assets 页面
- 修复前端乱码和 API 硬编码

**工作量分解**：

| 任务 | 工作量 | 风险 | 依赖 |
|---|---|---|---|
| Memory 页面 | 1-2 天 | 🟢 低 | 后端 API |
| Recommendation 页面 | 1 天 | 🟢 低 | 后端 API |
| Push 页面 | 0.5-1 天 | 🟢 低 | 后端 API |
| Assets 页面 | 1 天 | 🟢 低 | 后端 API |
| 前端修复（乱码 + API 地址） | 0.5 天 | 🟢 低 | 无 |

**关键风险点**：

1. **前端 API client 硬编码**：`frontend/src/api/client.ts` 硬编码 `http://127.0.0.1:8000`，计划要求改为 Vite proxy 或环境变量。
   - **缓解**：修改为读取 `import.meta.env.VITE_API_BASE_URL`，开发环境走 proxy，生产环境走配置。

---

## 4. 依赖关系与实施顺序

### 4.1 模块依赖图

```
Phase 0 (基础治理)
    │
    ▼
Phase 1 (记忆内核) ─────┐
    │                   │
    ▼                   │
Phase 2 (推荐解释) ◄────┘
    │
    ▼
Phase 3 (飞书 Agent)
    │
    ├───► Phase 4 (主动推送) ── 依赖推荐解释
    │
    └───► Phase 5 (多模态) ──── 弱依赖，可与 Phase 4 并行
              │
              ▼
        Phase 6 (Web 页面) ──── 依赖所有后端模块
```

### 4.2 关键路径

**最长路径**：Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 6，约 18-26 天

**可并行路径**：
- Phase 4 可与 Phase 3 后半段并行（PushService 开发）
- Phase 5 可与 Phase 3/4 并行（AssetService 开发）

### 4.3 推荐的实施顺序

**第一迭代（核心能力，约 12-16 天）**：
1. Phase 0 + Phase 1：记忆内核（含编码治理）
2. Phase 2：推荐解释与反馈

交付物：Agent 能使用记忆、推荐有解释、反馈能记录

**第二迭代（交互闭环，约 10-15 天）**：
3. Phase 3：飞书 Agent 任务执行
4. Phase 4：主动推送

交付物：飞书可管理全系统、推送智能化

**第三迭代（能力扩展，约 10-15 天）**：
5. Phase 5：多模态资产
6. Phase 6：Web 管理页面

交付物：支持图片/PDF、Web 可管理所有功能

---

## 5. 风险识别与缓解策略

### 5.1 高风险项

| 风险 | 可能性 | 影响 | 缓解策略 |
|---|---|---|---|
| **Agent 自然语言理解不准确** | 高 | 高 | 1. 命令优先策略<br>2. 模糊意图要求澄清<br>3. 高危操作必须二次确认 |
| **记忆抽取产生垃圾数据** | 中 | 中 | 1. 默认 candidate 状态<br>2. 高置信度阈值<br>3. 用户可一键清理 |
| **LLM 成本超预算** | 中 | 中 | 1. 解释生成可降级为模板<br>2. 视觉摘要可选<br>3. 记录并监控 token 用量 |
| **Phase 3 工作量爆炸** | 中 | 高 | 1. 分阶段实现（先查询后操作）<br>2. 先命令后自然语言<br>3. 推迟非核心命令 |
| **多模态依赖部署失败** | 中 | 中 | 1. 提供详细安装文档<br>2. Docker 化可选<br>3. 纯 Python 库优先 |

### 5.2 技术债务风险

| 债务项 | 当前状态 | 升级后风险 |
|---|---|---|
| SQLite 单文件 | 13 个表 → 22 个表 | 表膨胀、并发性能下降 |
| 无数据库迁移工具 | 自动建表 + 手动 ALTER | 新表字段变更容易出错 |
| API 中 raw dict | 4 个接口 | 类型不安全，维护困难 |
| 前端无测试 | 无测试框架 | 回归风险 |

**建议**：
- 在 Phase 0 引入 Alembic 或类似迁移工具
- 评估 SQLite → PostgreSQL 的迁移成本（可选，非必须）
- Phase 0 必须修复所有 raw dict 接口

---

## 6. 最小可交付版本（MVP）建议

### 6.1 MVP 定义

如果目标是快速验证价值，MVP 应包含：

```
✅ MemoryItem + MemoryService（用户记忆 CRUD）
✅ RecommendationService + explanation_json（结构化解释）
✅ ActionService 基础版（查询 + 简单操作）
✅ 飞书扩展命令（source/candidate/knowledge/memory 查询）
```

**排除项**（MVP 不做）：
- ❌ 自然语言意图解析（先用命令）
- ❌ 高危操作二次确认（MVP 只支持查询）
- ❌ 主动推送策略（保留现有 digest 推送）
- ❌ 多模态资产
- ❌ Web 管理页面（先用飞书）

### 6.2 MVP 工作量

约 **8-12 天**：
- Phase 0：1 天
- Phase 1（简化版）：3-4 天（不做 MemoryExtractor，只做 CRUD）
- Phase 2（简化版）：2-3 天（不做反馈闭环，只做解释生成）
- Phase 3（简化版）：2-4 天（只做查询命令，不做自然语言和确认）

### 6.3 MVP 用户故事

```
用户在飞书说："/omka memory add 我最近重点关注多模态知识资产"
系统保存为用户记忆。

每日 GitHub 抓取后，推荐服务发现相关内容。
系统推送到飞书，并解释：匹配用户当前重点。

用户在飞书说："/omka save candidate:xxx"
系统保存为 KnowledgeItem。

用户说："/omka memory list"
系统返回所有用户记忆。
```

做到这个闭环，即可验证"记忆驱动推荐"的核心价值。

---

## 7. 资源需求评估

### 7.1 开发资源

| Phase | 后端工作量 | 前端工作量 | 总计 |
|---|---|---|---|
| Phase 0 | 1-2 天 | 0 天 | 1-2 天 |
| Phase 1 | 4-5 天 | 0 天 | 4-5 天 |
| Phase 2 | 3-4 天 | 0.5 天 | 3-4.5 天 |
| Phase 3 | 5-7 天 | 0 天 | 5-7 天 |
| Phase 4 | 2-3 天 | 0.5 天 | 2-3.5 天 |
| Phase 5 | 4-6 天 | 1 天 | 5-7 天 |
| Phase 6 | 0 天 | 4-6 天 | 4-6 天 |
| **总计** | **19-27 天** | **6-8 天** | **25-35 天** |

### 7.2 运行资源

| 资源 | 当前 | 升级后 | 变化 |
|---|---|---|---|
| LLM API 调用 | 每日 1 次（摘要） | 每日 20+ 次（解释 + 摘要 + Agent） | 成本增加 10-20 倍 |
| 数据库大小 | ~1MB | ~5-10MB | 记忆 + 审计日志 |
| 磁盘（资产） | 0 | 取决于上传量 | 需监控 |
| 内存 | ~50MB | ~100MB | Agent 上下文增长 |

### 7.3 LLM 成本估算

假设每日 20 条候选：

| 场景 | 调用次数 | Tokens/次 | 月度成本（GPT-4o-mini） |
|---|---|---|---|
| 当前（仅摘要） | 1 | 2000 | ~$0.5 |
| 升级后（摘要+解释+Agent） | 25 | 3000 | ~$15-20 |
| 多模态（图片摘要） | 10 | 5000 | ~$20-30 |

**结论**：LLM 成本可控（月度 <$50），但需监控。

---

## 8. 推荐实施路径

### 8.1 方案 A：完整实施（约 30-40 天）

按原计划顺序执行，适合有充足时间的场景。

### 8.2 方案 B：MVP 优先（约 10-15 天）

先做 MVP 验证核心价值，再逐步扩展。推荐此方案。

```
Week 1: Phase 0 + Phase 1（记忆内核）
Week 2: Phase 2（推荐解释）+ Phase 3 简化版（飞书查询命令）
Week 3-4: Phase 3 完整版 + Phase 4
Week 5-6: Phase 5 + Phase 6
```

### 8.3 方案 C：按需实施

根据实际使用反馈，动态调整优先级。例如：
- 如果用户主要用飞书 → 优先 Phase 3
- 如果推荐质量是痛点 → 优先 Phase 2
- 如果知识资产类型单一 → 推迟 Phase 5

---

## 9. 关键决策点

在启动实施前，需要确认以下决策：

### 9.1 必须决策

| # | 决策项 | 选项 | 建议 |
|---|---|---|---|
| 1 | 实施策略 | A: 完整 / B: MVP / C: 按需 | **B: MVP 优先** |
| 2 | 数据库迁移工具 | 引入 Alembic / 保持手动 | **引入 Alembic** |
| 3 | 多模态 OCR | Tesseract / EasyOCR / LLM Vision | **LLM Vision + Tesseract 备选** |
| 4 | 权限模型存储 | 配置文件 / 数据库表 | **AppSetting 扩展** |
| 5 | 自然语言解析 | LLM 结构化输出 / 规则匹配 | **先规则，后 LLM** |

### 9.2 可选决策

| # | 决策项 | 说明 |
|---|---|---|
| 6 | PostgreSQL 迁移 | 如果 SQLite 性能成为瓶颈，可考虑迁移 |
| 7 | 向量数据库 | 如果推荐需要语义匹配，可引入 Chroma/Milvus |
| 8 | 消息队列 | 如果异步任务增多，可引入 Celery/RQ |
| 9 | Docker 化 | 简化部署，尤其是多模态依赖 |

---

## 10. 启动检查清单

在正式开始编码前，请确认：

- [ ] 已选定实施策略（MVP / 完整 / 按需）
- [ ] 已确认 LLM 提供商和预算
- [ ] 已安装多模态所需的系统依赖（Tesseract 等，如果做 Phase 5）
- [ ] 已备份现有数据库
- [ ] 已确定前端开发资源（如果需要 Phase 6）
- [ ] 已评估飞书 Bot 的 API 调用限额

---

## 11. 附录：当前代码关键发现

### 11.1 已知违规（AGENTS.md 记录）

| 文件 | 问题 | 修复优先级 |
|---|---|---|
| `routes_digest.py:10-13` | 直接调用 `rank_candidates()` | P0 |
| `routes_sources.py:61` | `dict[str, Any]` 请求 | P0 |
| `routes_feedback.py:115` | `dict[str, Any]` 请求 | P0 |
| `routes_knowledge.py:49,71` | `dict[str, Any]` 请求 | P0 |
| `routes_settings.py:31,50` | `dict[str, Any]` 请求 | P0 |
| `digest_builder.py:7` | 跨 pipeline 导入 | P1 |
| `cleaner.py:15` | 全量 RawItem 读取 | P1 |

### 11.2 缺失的 `__init__.py`

- `omka/app/notifications/__init__.py` ❌
- `omka/app/notifications/channels/__init__.py` ❌

### 11.3 前端空目录

- `frontend/src/components/cards/`
- `frontend/src/components/common/`
- `frontend/src/components/ui/`
- `frontend/src/types/`

---

## 12. 总结与下一步行动

### 12.1 总体评估

| 维度 | 评分 | 说明 |
|---|---|---|
| 技术可行性 | 8/10 | 所有模块都有明确实现路径 |
| 工作量合理性 | 6/10 | 计划偏乐观，实际可能超期 30-50% |
| 架构设计 | 8/10 | 新增 service 层和审计机制设计合理 |
| 风险可控性 | 7/10 | 最大风险在 Phase 3（自然语言 + 权限） |
| 价值产出 | 9/10 | 升级后产品能力有质的飞跃 |

### 12.2 下一步行动

如果选择 **MVP 优先策略**，建议立即启动：

1. **今天**：创建 feature 分支，启动 Phase 0（编码治理）
2. **第 1-3 天**：实现 MemoryItem + MemoryService + 飞书 memory 命令
3. **第 4-6 天**：实现 RecommendationService + explanation_json
4. **第 7-10 天**：扩展飞书命令（source/candidate/knowledge 查询）
5. **第 11-12 天**：集成测试和飞书端到端验证

**预计 2 周内可交付 MVP。**

---

> 本文档由 Sisyphus 基于代码审查生成。
> 如需调整实施策略或深入分析某个模块，请随时提出。
