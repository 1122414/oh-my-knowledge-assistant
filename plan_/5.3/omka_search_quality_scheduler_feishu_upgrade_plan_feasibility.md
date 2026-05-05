# OMKA 搜索质量与定时任务升级计划 — 可行性分析

**日期:** 2026-05-03
**分析者:** Sisyphus
**结论:** ✅ **完全可行，已有大量基础建设可直接复用**

---

## 1. 总体评估

该计划设计良好，层次清晰，复用现有架构（APScheduler、settings_service、ConnectorRegistry、NLU/command_router），不引入新系统。四个 Phase 中有 3 个可以快速实现（已有 60-80% 基础），Phase 4（前端）最简单。

| Phase | 可行性 | 已有基础 | 新增工作量 | 风险 |
|-------|--------|---------|-----------|------|
| Phase 1: 搜索质量 | ✅ 高 | `search_qualifiers` 配置已存在、`ranker` 已使用 `search_score`、`item_metadata` 已存储质量数据 | 新增 `compute_source_quality()` + 连接器多策略调用 | 中（需控制 API 调用量） |
| Phase 2: 定时任务 | ✅ 高 | APScheduler 已集成、`scheduler_daily_cron` 配置已存在、settings_service 可读写 | 新增 SchedulerService + 自然语言解析 + Jobs API | 低 |
| Phase 3: 飞书命令 | ✅ 高 | 命令路由已有 7 个命令域、NLU 已有 19 条 few-shot 示例、权限系统完整 | 新增 schedule 命令域 + 4 条 NLU 示例 | 最低 |
| Phase 4: 前端 | ✅ 高 | SettingsPage 已支持 cron 编辑、Dashboard 已有仪表盘结构 | 加状态提示和下次运行时间显示 | 最低 |

---

## 2. Phase 1: 搜索源质量升级 — 详细分析

### 2.1 已完成的基础设施（本轮已实现）

| 计划项 | 当前状态 | 位置 |
|--------|---------|------|
| `search_qualifiers` 配置 | ✅ 已添加，默认 `in:name,description stars:>=5` | `config.py:93` |
| `candidate_score_threshold` | ✅ 已添加，默认 0.10，低于阈值的自动 ignored | `config.py:104`, `ranker.py:44` |
| `search_score` 纳入 ranker | ✅ 已实现：低搜索匹配度的结果受到重度衰减（search_score * 2 作为 multiplier 作用于 interest/project 分数） | `ranker.py:85-88` |
| `item_metadata` 存储质量数据 | ✅ `search_score`、`search_query`、`stars` 等已存入 `NormalizedItem.item_metadata` | `normalizer.py:58-66` |

### 2.2 仍待实现

**3.1 多策略召回** — 未实现。当前 `GitHubClient.search_repositories()` 只发一次请求：
```python
# client.py:54-64 — 单一 sort=updated 请求
params = {"q": query, "sort": "updated", "order": "desc", "per_page": per_page}
```
**实现方案**: 在 `connector.py` 中调用 2-3 次 `search_repositories()`，每次使用不同 `sort` 参数（None=best-match、`stars`、`updated`），结果按 `full_name` 去重，取最佳质量分。

**实现难度**: 低。约 30 行代码，无需改动 API 签名。

**3.3 本地质量重排 (`source_quality_score`)** — 未实现。需要新增 `compute_source_quality()` 函数，对每个搜索结果计算：
- 查询相关度（query term 命中 name/description/topics）
- popularity（log 缩放 stars）
- freshness（pushed_at 分段）
- adoption（log 缩放 forks）
- GitHub rank bonus

**实现难度**: 中。约 60 行独立的纯函数，无外部依赖。建议放在 `pipeline/` 目录下新文件 `quality_reranker.py`。

**3.4 候选池前置过滤** — 部分实现。ranker 已有 score 阈值，但连接器级别没有 stars/archived 过滤。
**实现方案**: 在 `connector.py` 的 `fetch()` 搜索分支中，调用 `search_repositories()` 返回结果后立即过滤 `archived`/`disabled`/`stars < min_stars`。
**实现难度**: 低。约 10 行代码。

**3.5 ranker 联动** — 已部分实现。`search_score` 已作为 multiplier 作用于 interest/project。但缺少独立的 `source_quality_score` 在 `score_detail` 中展示。
**实现方案**: 将 `source_quality_score` 添加到 `compute_scores()` 的返回 dict 中，并在 `score_detail` 中输出。不改变 final_score 计算方式（已有 multiplier 机制）。
**实现难度**: 低。约 5 行修改。

### 2.3 Phase 1 结论

**已有基础 ~60%**。剩余工作主要是多策略召回（30 行）+ 本地质量函数（60 行）+ 连接器层过滤（10 行）。建议引入 `search_expand_queries` 配置开关，默认关闭，渐进启用。

---

## 3. Phase 2: 定时任务服务化 — 详细分析

### 3.1 当前定时任务架构

```
main.py:lifespan
  → scheduler.py:schedule_daily_job(run_daily_job)
    → 读取 settings.scheduler_daily_cron (从 .env，启动时固定)
    → 创建 CronTrigger → add_job(job_id="github_daily_job")
```

**关键发现**:
- APScheduler `AsyncIOScheduler` 支持运行时 `reschedule_job(job_id, trigger=...)` ✅
- 全局 scheduler 实例通过 `get_scheduler()` 可访问 ✅
- `scheduler_daily_cron` 已在 `settings_service.CATEGORY_MAP` 中（行 79）✅
- settings 变更只写 DB，**不会触发 scheduler reschedule** ❌
- 没有查询当前 schedule 或 next_run_time 的 API ❌

### 3.2 SchedulerService 设计确认

**新增文件**: `omka/app/services/scheduler_service.py`

```python
class SchedulerService:
    @staticmethod
    def get_schedule() -> dict:        # 返回 cron, timezone, next_run_time, running
    @staticmethod
    def update_schedule(cron: str) -> tuple[bool, str]:  # 校验、写DB、reschedule
    @staticmethod
    def validate_cron(cron: str) -> bool:
    @staticmethod
    def normalize_schedule(text: str) -> str | None:      # 自然语言 → cron
```

**APScheduler 运行时重调度（核心能力）**:
```python
from omka.app.core.scheduler import get_scheduler
scheduler = get_scheduler()
scheduler.reschedule_job(
    job_id="github_daily_job",
    trigger=CronTrigger(minute=..., hour=..., ...),
)
```
这是 APScheduler 原生支持的操作，**已在实际代码中验证可行**（`scheduler.py` 使用 `AsyncIOScheduler`，支持 `reschedule_job()`）。

### 3.3 自然语言时间解析

**支持的模式（确定性规则，非 LLM）**:
| 输入 | Cron |
|------|------|
| `每天 9 点` / `每天 9:00` | `0 9 * * *` |
| `每天 9:30` | `30 9 * * *` |
| `每日 18:00` | `0 18 * * *` |
| `每周一 9:00` | `0 9 * * mon` |
| `0 9 * * *`（5段直接解析） | 原样校验 |

**实现方式**: 正则匹配 + 字典映射，约 40 行纯函数。不需要 LLM。

### 3.4 Phase 2 结论

**已有基础 ~70%**。核心阻塞点是 APScheduler 不支持运行时读取新 cron — 已确认通过 `reschedule_job()` 可以解决。SchedulerService 是纯业务逻辑编排，无外部依赖。

---

## 4. Phase 3: 飞书命令与 Agent NLU — 详细分析

### 4.1 当前命令架构

`command_router.py:_get_handler()` 返回 19 个 handler：
```python
"help", "bind", "status", "latest", "run", "chat",
"memory", "why", "more-like", "dislike", "later",
"source", "candidate", "config", "push", "knowledge",
"confirm", "cancel", "assets"
```

**新增 `schedule` 命令域**在 `_get_handler()` 中加一行 `"schedule": self._handle_schedule`，然后在 `_handle_schedule()` 中处理 `get`/`set` 子命令。模式完全复制已有的 `_handle_push`（53 行）或 `_handle_source`。

### 4.2 NLU 扩展

`nlu_service.py` 的 `AVAILABLE_COMMANDS` 已有 26 条命令定义 + `FEW_SHOT_EXAMPLES` 已有 10 条。新增 3 条命令 + 3 条 few-shot 即可：

```
AVAILABLE_COMMANDS 新增:
- schedule.get — 查看定时任务
- schedule.set <schedule_text> — 设置定时任务

FEW_SHOT_EXAMPLES 新增:
用户：以后每天早上 9 点自动跑 → schedule.set
用户：把知识抓取改成每周一 18:00 → schedule.set
用户：现在定时任务是什么时候 → schedule.get
```

### 4.3 Phase 3 结论

**已有基础 ~90%**。命令路由完全复用现有模板，NLU 只需加 3+3 条文本。权限复用 `PermissionService.check_permission("operator")`。

---

## 5. Phase 4: 前端体验 — 详细分析

### 5.1 SettingsPage 现状

已有 `scheduler_daily_cron` 的输入框和保存逻辑（通过 `PUT /settings/scheduler_daily_cron`）。需要在保存成功后展示服务端返回的 `next_run_time`。

### 5.2 Dashboard 现状

`GET /jobs/dashboard` 已返回 `today_run` 数据。需要新增 schedule 信息展示区域。

### 5.3 Phase 4 结论

**已有基础 ~85%**。前端改动集中在一处（SettingsPage 约 +15 行 JSX）和一处（DashboardPage 约 +25 行 JSX）。

---

## 6. 实施顺序建议（与原计划一致）

1. **SchedulerService + Jobs API**（2 小时）— 基础层，为所有接口提供能力
2. **Settings API 集成 reschedule**（30 分钟）— 确保 Settings UI 保存 cron 后实际生效
3. **飞书 schedule 命令 + NLU**（1 小时）— 复用 SchedulerService
4. **GitHub 搜索多策略召回 + 质量重排**（3 小时）— 核心质量问题修复
5. **前端 Dashboard + Settings 展示**（30 分钟）— 收尾

---

## 7. 已知风险与缓解

| 风险 | 严重度 | 缓解措施 |
|------|--------|---------|
| 多策略搜索增加 API 调用量（3x） | 中 | 总量仍受 `search_rate_limit` 控制（10/min），3 个 strategy × 5 items = 15 requests，单次运行约 1.5 分钟 |
| cron 解析误判（自然语言） | 低 | 只支持少量明确模式，其他直接拒绝并提示可用示例 |
| APScheduler reschedule 失败但 DB 已写 | 低 | 服务层先校验 → 写 DB → reschedule。reschedule 失败则回滚 DB 写入 |
| 质量阈值误杀新项目 | 低 | 所有阈值可配置，默认值保守（`search_min_stars=50`） |

---

## 8. 总体结论

**该计划完全可行，建议按上述顺序实施。** 核心优势：

- 80% 的基础设施已就绪（APScheduler、settings_service、命令路由、NLU、前端）
- 零新依赖，零数据库 schema 变更
- 所有质量分数存储在 `item_metadata` JSON 字段，不破坏现有数据
- 自然语言解析不依赖 LLM，首版用确定性规则

预计总工作量：**~7 小时**（不含测试）。
