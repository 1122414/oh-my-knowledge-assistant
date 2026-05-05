# OMKA 搜索质量与定时任务升级 — 实施启动文档

**计划文件:** `omka_search_quality_scheduler_feishu_upgrade_plan.md`
**可行性分析:** `omka_search_quality_scheduler_feishu_upgrade_plan_feasibility.md`
**实施者:** Sisyphus
**日期:** 2026-05-03

---

## 实施概览

5 个里程碑，按依赖链路顺序执行。每个里程碑独立可验证。

```
M1: SchedulerService       → M2: Settings reschedule hook
  ↓                            ↓
M3: Feishu /omka schedule  → M4: GitHub 搜索多策略 + 质量重排
                                ↓
                              M5: 前端 Dashboard + Settings
```

---

## M1: SchedulerService + Jobs API（基础层）

### 新建文件

**`omka/app/services/scheduler_service.py`**

```
核心方法:
├── get_schedule() → {cron, timezone, next_run_time, running}
├── update_schedule(schedule_text: str) → (ok, message)
├── validate_cron(cron_text: str) → bool
├── normalize_schedule(text: str) → str | None
└── _parse_natural_time(text: str) → str | None  (内部)
```

**自然语言解析规则（确定性，非 LLM）:**

| 模式 | 正则 | Cron |
|------|------|------|
| 每天 HH 点 | `每天\s*(\d{1,2})\s*点` | `0 H * * *` |
| 每天 HH:MM | `每天\s*(\d{1,2}):(\d{2})` | `M H * * *` |
| 每日 HH:MM | `每日\s*(\d{1,2}):(\d{2})` | `M H * * *` |
| 每周X HH:MM | `每周([一二三四五六日天])\s*(\d{1,2}):(\d{2})` | `M H * * W` |
| 5段 cron | `^[\d*,/]+\s+[\d*,/]+\s+[\d*,/]+\s+[\d*,/]+\s+[\d*,/]+$` | 原样 |

**APScheduler reschedule 关键代码:**
```python
from omka.app.core.scheduler import get_scheduler
from apscheduler.triggers.cron import CronTrigger
from omka.app.core.config import settings

scheduler = get_scheduler()
parts = new_cron.split()  # "0 9 * * *"
scheduler.reschedule_job(
    job_id="github_daily_job",
    trigger=CronTrigger(
        minute=parts[0], hour=parts[1], day=parts[2],
        month=parts[3], day_of_week=parts[4],
        timezone=settings.scheduler_timezone,
    )
)
```

### 修改文件

**`omka/app/api/routes_jobs.py`** — 新增 2 个端点:

```python
@router.get("/schedule")
async def get_schedule():
    result = SchedulerService.get_schedule()
    return result
    # → {cron, timezone, next_run_time, running}

@router.put("/schedule")
async def update_schedule(data: ScheduleUpdateRequest):
    ok, message = SchedulerService.update_schedule(data.schedule)
    if not ok:
        raise HTTPException(400, message)
    return SchedulerService.get_schedule()
```

### 验证方式
```bash
curl http://localhost:8000/jobs/schedule
# → {"cron": "0 9 * * *", "timezone": "Asia/Shanghai", "next_run_time": "2026-05-04T09:00:00", "running": true}

curl -X PUT http://localhost:8000/jobs/schedule -H "Content-Type: application/json" -d '{"schedule": "每天 14:30"}'
# → {"cron": "30 14 * * *", "next_run_time": "2026-05-03T14:30:00", ...}
```

**涉及文件数: 2（1 新建 + 1 修改）**

---

## M2: Settings API 接入运行时 reschedule

### 修改文件

**`omka/app/api/routes_settings.py`** — 在 `PUT /settings/{key}` 和批量 `PUT /settings` 中加入 hook:

```python
# 在 set_setting() 成功后：
if key == "scheduler_daily_cron":
    from omka.app.services.scheduler_service import SchedulerService
    ok, msg = SchedulerService.update_schedule(value)
    if not ok:
        logger.warning("设置 cron 已保存但 scheduler 更新失败 | error=%s", msg)
```

**`omka/app/services/scheduler_service.py`** — `update_schedule()` 已包含 DB 写入逻辑（通过 `settings_service.set_setting()`），所以 Settings API 调用后自动生效。

### 验证方式
1. 通过 Settings 页面修改 cron → 检查 `GET /jobs/schedule` 的 `next_run_time` 是否更新
2. 检查日志确认 APScheduler job 已 reschedule

**涉及文件数: 2（修改）**

---

## M3: 飞书 /omka schedule 命令 + NLU

### 修改文件

**`omka/app/integrations/feishu/command_router.py`**

1. `_get_handler()` 新增: `"schedule": self._handle_schedule`
2. 新增 `_handle_schedule()` 方法（约 55 行，参照 `_handle_push` 模板）:

```python
async def _handle_schedule(self, args: list[str]) -> FeishuCommandResult:
    from omka.app.services.scheduler_service import SchedulerService
    from omka.app.services.action_service import PermissionService

    if not args:
        info = SchedulerService.get_schedule()
        return FeishuCommandResult(success=True,
            message=f"📅 定时任务\n\nCron: {info['cron']}\n时区: {info['timezone']}\n下次运行: {info['next_run_time']}",
            command=FeishuCommandType.UNKNOWN)

    sub = args[0].lower()
    if sub == "set":
        if not PermissionService.check_permission(self._current_sender_id, "operator"):
            return FeishuCommandResult(success=False, message="权限不足，需要 operator 权限")
        schedule_text = " ".join(args[1:])
        ok, msg = SchedulerService.update_schedule(schedule_text)
        if ok:
            info = SchedulerService.get_schedule()
            return FeishuCommandResult(success=True,
                message=f"✅ 已更新\n\nCron: {info['cron']}\n下次运行: {info['next_run_time']}")
        return FeishuCommandResult(success=False, message=f"❌ {msg}\n\n可用示例:\n- 每天 9:30\n- 每周一 18:00\n- 0 9 * * *")

    return FeishuCommandResult(success=False, message=f"未知子命令: {sub}\n可用: set")
```

3. 更新 HELP_TEXT 增加 schedule 域

**`omka/app/services/nlu_service.py`**

在 `AVAILABLE_COMMANDS` 和 `FEW_SHOT_EXAMPLES` 分别新增:

```
AVAILABLE_COMMANDS:
- schedule.get — 查看定时任务
- schedule.set <schedule_text> — 设置定时任务

FEW_SHOT_EXAMPLES:
用户：以后每天早上 9 点自动跑
输出：{"command": "schedule.set", "args": ["每天 9 点"], "confidence": 0.96}

用户：把知识抓取改成每周一 18:00
输出：{"command": "schedule.set", "args": ["每周一 18:00"], "confidence": 0.94}

用户：现在定时任务是什么时候
输出：{"command": "schedule.get", "args": [], "confidence": 0.95}
```

### 验证方式
```
飞书群: /omka schedule
→ 📅 定时任务 Cron: 0 9 * * * 下次运行: 2026-05-04 09:00

飞书群: /omka schedule set 每天 14:30
→ ✅ 已更新 Cron: 30 14 * * * 下次运行: 2026-05-03 14:30

飞书群: 以后每天早上 9 点自动跑（自然语言）
→ NLU → schedule.set → ✅ 已更新
```

**涉及文件数: 2（修改）**

---

## M4: GitHub 搜索多策略召回 + 质量重排

### 新增文件

**`omka/app/pipeline/quality_reranker.py`**

```python
def compute_source_quality(item_metadata: dict) -> dict:
    """为单个搜索结果计算质量分。

    返回:
    {source_quality_score: float,   # 0-1
     source_quality_reasons: [str],  # 可解释原因
     search_strategy: str,           # best_match/stars/updated
     search_rank: int}               # 在该策略中的排名
    """
```

权重设计（与计划一致）:
- 查询相关度 0.38: 检查 query term 是否命中 name/full_name/description/topics
- popularity 0.28: `log10(stars) / log10(100000)` 标准化到 0-1
- freshness 0.18: `max(0, 1 - days_since_push / 365)`
- adoption 0.10: `log10(forks) / log10(10000)`
- GitHub rank bonus 0.06: `1 / (rank + 1)`（排名越靠前 bonus 越高）

惩罚项:
- `archived == True` → score *= 0
- `fork == True` → score *= 0.5
- `open_issues / max(stars, 1) > 0.5` → score *= 0.7

### 修改文件

**`omka/app/connectors/github/connector.py`** — `fetch()` 搜索分支重构:

```python
elif mode == "search":
    query = config.get("query", "")
    limit = config.get("limit", settings.search_results_per_query)
    
    # 多策略召回
    strategies = [("best_match", None), ("stars", "stars"), ("updated", "updated")]
    seen_names = set()
    
    for strategy_name, sort_param in strategies:
        items = await self.client.search_repositories(
            query, per_page=limit, sort=sort_param
        )
        for item in items:
            full_name = item.get("full_name", "")
            if full_name in seen_names:
                continue
            seen_names.add(full_name)
            
            # 前置过滤
            if item.get("archived") or item.get("disabled"):
                continue
            stars = item.get("stargazers_count", 0)
            if stars < settings.search_min_stars:
                continue
            
            results.append({...})  # 保留原格式
```

**`omka/app/core/config.py`** — 新增配置:
```python
search_min_stars: int = Field(default=10, description="搜索结果最低 star 数")
search_max_candidates_per_query: int = Field(default=15, description="每搜索源最大候选数")
search_expand_queries: bool = Field(default=False, description="是否启用多策略召回")
```

### 验证方式
```bash
# 运行单个搜索源
curl -X POST http://localhost:8000/sources/src_search_Hermes/run

# 检查 candidates 的 score_detail 包含 source_quality_score
sqlite3 data/db/app.sqlite "SELECT json_extract(score_detail, '$.source_quality_score') FROM candidate_items WHERE status='pending' LIMIT 5;"
```

**涉及文件数: 4（1 新建 + 3 修改）**

---

## M5: 前端 Dashboard + Settings

### 修改文件

**`frontend/src/pages/SettingsPage.tsx`** — 在 scheduler cron 输入框下方增加:

```tsx
{scheduleInfo && (
  <div className="text-sm text-muted-foreground">
    下次运行: {new Date(scheduleInfo.next_run_time).toLocaleString('zh-CN')}
  </div>
)}
```

**`frontend/src/pages/DashboardPage.tsx`** — 在仪表盘增加 schedule 状态卡片:

```tsx
<div className="rounded-xl border p-4">
  <h3 className="font-medium">定时任务</h3>
  <p>Cron: {schedule.cron}</p>
  <p>下次运行: {schedule.next_run_time}</p>
  <Button onClick={runNow}>立即运行</Button>  {/* 已有 */}
</div>
```

**`frontend/src/api/jobs.ts`** — 新增 API 方法:

```typescript
getSchedule: () => api.get<ScheduleInfo>("/jobs/schedule")
updateSchedule: (schedule: string) => api.put<ScheduleInfo>("/jobs/schedule", { schedule })
```

### 验证方式
1. 访问 Dashboard 页面 → 看到定时任务状态
2. 访问 Settings 页面 → 修改 cron → 保存后看到下次运行时间更新

**涉及文件数: 3（修改）**

---

## 总览

| 里程碑 | 涉及文件 | 预计时间 | 依赖 |
|--------|---------|---------|------|
| M1: SchedulerService | 1 新建 + 1 修改 | 1.5h | 无 |
| M2: Settings reschedule | 2 修改 | 0.5h | M1 |
| M3: Feishu schedule | 2 修改 | 1h | M1 |
| M4: GitHub 质量 | 1 新建 + 3 修改 | 3h | 无（可并行） |
| M5: 前端 | 3 修改 | 0.5h | M1 |
| **合计** | **11 文件** | **~6.5h** | |

**关键路径: M1 → M2 → M5（2.5h），M4 可并行（3h），M3 在 M1 后独立。**

---

## 快速启动

```bash
# 1. 创建分支
git checkout -b feat/search-quality-scheduler

# 2. 按 M1→M2→M3→M4→M5 顺序实施

# 3. 每完成一个里程碑即验证
curl http://localhost:8000/health
curl http://localhost:8000/jobs/schedule
cd frontend && npm run build
```
