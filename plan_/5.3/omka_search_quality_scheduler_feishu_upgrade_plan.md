# OMKA 搜索质量与定时任务升级计划

**日期:** 2026-05-03  
**范围:** 仅规划，不直接改代码  
**目标:** 解决搜索来源质量差、任务只能手动触发、飞书 Agent 不能设置定时任务这三个阻塞问题。

## 1. 当前问题判断

### 1.1 搜索质量问题

现有 GitHub 搜索源主要依赖 `SourceConfig.mode = search` 的单一 query，然后由 `GitHubClient.search_repositories()` 拉取结果。当前链路的问题是：

- 搜索侧只拿一批 GitHub Search API 结果，缺少多策略召回。
- 搜索源 query 比较宽，例如 `browser agent`、`rag agent`，容易召回噪声项目。
- 搜索结果缺少本地质量重排，GitHub 的 `score`、stars、topics、recent activity、fork/archived 状态没有形成稳定的质量门槛。
- 候选池生成后才进入 ranker，低质量搜索结果已经污染候选池。
- ranker 更偏内容匹配和新鲜度，无法充分区分“关键词碰瓷但项目质量差”的结果。

### 1.2 定时任务问题

当前启动时在 `main.py` 调用 `schedule_daily_job(run_daily_job)` 注册每日任务，配置来自 `scheduler_daily_cron`。问题是：

- 前端虽然能编辑 `scheduler_daily_cron`，但运行中的 APScheduler job 不一定会重载。
- `/jobs/run-now` 只能手动触发，没有查询当前 schedule、更新 schedule、查看下次运行时间的 API。
- 调度配置缺少校验，错误 cron 可能在运行时才暴露。

### 1.3 飞书 Agent 问题

飞书命令路由和 NLU 已经存在，能处理 `run`、`source.*`、`candidate.*`、`config.*` 等命令。缺口是：

- 没有 `schedule` / `job` 命令域。
- NLU prompt 没有“每天 9 点跑”“改成每周一 18:00”之类意图。
- Agent 自然语言设置定时任务需要共用后端服务，而不是直接写配置。

## 2. 设计原则

- 搜索质量优先在“入库前”解决，减少候选池污染。
- 定时任务能力抽成服务层，API、飞书命令、未来 UI 都调用同一套服务。
- 自然语言只做意图解析，真正 cron 校验和调度变更由服务层负责。
- 保持现有 YAML sources、DB SourceConfig、APScheduler、settings_service 的架构，不引入新系统。
- 先做确定性规则和可解释打分，LLM 只作为后续增强，不作为首版必要路径。

## 3. Phase 1：搜索源质量升级

### 3.1 GitHub 搜索多策略召回

在 `GitHubConnector` 搜索模式中，将一次 query 扩展为多种 Search API 策略：

- best-match：不传 sort，保留 GitHub 默认相关性。
- stars：`sort=stars&order=desc`，提高成熟项目召回。
- updated：`sort=updated&order=desc`，保留新鲜项目召回。

同一 repo 用 `full_name` 去重，每个结果保留最佳质量分和召回策略信息。

### 3.2 搜索限定符配置

新增或强化运行时配置：

- `search_qualifiers`: 默认建议 `in:name,description,readme stars:>=50 archived:false`
- `search_min_stars`: 默认建议 `50`
- `search_expand_queries`: 默认 `true`
- `search_max_candidates_per_query`: 可选，控制每个 query 召回后参与重排的上限

这些配置应纳入 `settings_service` 初始化和 Settings UI。

### 3.3 本地质量重排

为每个搜索结果计算 `source_quality_score`，建议权重：

- 查询相关度 0.38：query term 是否命中 name、full_name、description、topics。
- popularity 0.28：stars 使用 log 缩放。
- freshness 0.18：最近 pushed/updated 时间分段。
- adoption 0.10：forks 使用 log 缩放。
- GitHub rank bonus 0.06：保留原搜索 rank 的弱信号。

惩罚项：

- `archived`、`disabled` 直接过滤。
- fork 项目降权。
- open issues 相对 stars 异常高时降权。

将结果写入 `NormalizedItem.item_metadata`：

- `source_quality_score`
- `source_quality_reasons`
- `search_strategy`
- `search_rank`

### 3.4 候选池前置过滤

在搜索结果进入 RawItem/NormalizedItem 或 CandidateItem 前，过滤：

- stars < `search_min_stars`
- archived/disabled
- `source_quality_score` 低于阈值，例如 0.35

这样能明显减少“泛关键词污染”。

### 3.5 ranker 联动

ranker 中对搜索结果增加一项质量信号：

- repo/release 原有评分保持。
- `repo_search_result` 使用 `source_quality_score` 作为附加权重。
- 低于 `candidate_score_threshold` 的候选自动 ignored，但必须记录 ignored_count，便于调试。

建议输出 score_detail：

- `interest_score`
- `project_score`
- `freshness_score`
- `popularity_score`
- `source_quality_score`
- `matched_interests`
- `matched_projects`

## 4. Phase 2：定时任务服务化

### 4.1 新增 SchedulerService

新增服务层模块，例如 `omka/app/services/scheduler_service.py`，职责：

- 查询当前每日任务 schedule。
- 校验 cron 表达式。
- 更新 `scheduler_daily_cron` 到 DB settings。
- 重新注册 APScheduler job。
- 返回下次运行时间。

核心方法建议：

- `get_daily_job_schedule()`
- `update_daily_job_schedule(schedule_text: str)`
- `normalize_schedule_to_cron(text: str)`

### 4.2 支持自然语言时间

首版支持确定性中文解析即可：

- `每天 9 点` -> `0 9 * * *`
- `每天 9:30` -> `30 9 * * *`
- `每日 18:00` -> `0 18 * * *`
- `每周一 9:00` -> `0 9 * * mon`
- 直接 5 段 cron -> 原样校验后保存

暂不支持复杂表达式如“工作日每两小时”，避免误设。

### 4.3 Jobs API

新增：

- `GET /jobs/schedule`
- `PUT /jobs/schedule`，body: `{ "schedule": "每天 9:30" }`

返回：

- `cron`
- `timezone`
- `next_run_time`
- `running`
- `message`

更新 Settings API 时，如果 key 是 `scheduler_daily_cron`，也应走 SchedulerService，而不是只写 DB。

## 5. Phase 3：飞书命令与 Agent NLU

### 5.1 命令设计

新增命令域：

- `/omka schedule`：查看当前定时任务。
- `/omka schedule set 每天 9:30`：设置每日任务。
- `/omka schedule set 0 9 * * *`：直接设置 cron。

权限：

- 查看 schedule：viewer。
- 修改 schedule：operator 或 admin。

### 5.2 NLU 意图

在 `AVAILABLE_COMMANDS` 加：

- `schedule.get`
- `schedule.set <schedule_text>`

few-shot 示例：

- “以后每天早上 9 点自动跑” -> `{"command": "schedule.set", "args": ["每天 9 点"], "confidence": 0.96}`
- “把知识抓取改成每周一 18:00” -> `{"command": "schedule.set", "args": ["每周一 18:00"], "confidence": 0.94}`
- “现在定时任务是什么时候” -> `{"command": "schedule.get", "args": [], "confidence": 0.95}`

### 5.3 飞书回复格式

设置成功：

```text
已更新定时任务

Cron: 30 9 * * *
时区: Asia/Shanghai
下次运行: 2026-05-04 09:30
```

设置失败：

```text
定时任务格式无法识别

可用示例:
- 每天 9:30
- 每周一 18:00
- 0 9 * * *
```

## 6. Phase 4：前端体验

### 6.1 Settings 页面

保留 Cron 输入，同时增加提示：

- `每天 9:30`
- `每周一 18:00`
- `0 9 * * *`

保存后展示服务端返回的下次运行时间。

### 6.2 Dashboard 页面

增加定时任务状态区域：

- 当前 cron。
- 时区。
- 下次运行时间。
- 手动 Run Now 按钮保留。

## 7. 验收标准

### 搜索质量

- 同一搜索源结果中 archived/disabled 项目不进入候选。
- stars 低于阈值的项目不进入候选。
- 每个搜索候选都能看到 `source_quality_score` 和原因。
- `browser agent`、`rag agent`、`personal knowledge assistant llm` 三个源的候选明显减少低质量项目。

### 定时任务

- `GET /jobs/schedule` 能返回当前 cron 和 next_run_time。
- `PUT /jobs/schedule` 能在不重启服务的情况下改变 APScheduler 下次运行时间。
- Settings 页面保存 `scheduler_daily_cron` 后实际调度同步更新。

### 飞书 Agent

- `/omka schedule` 能查看计划。
- `/omka schedule set 每天 9:30` 能设置计划。
- 自然语言“以后每天九点自动更新知识库”能被 NLU 映射为 schedule.set。
- 非 operator 用户不能修改 schedule。

## 8. 建议实施顺序

1. 先实现 SchedulerService 和 Jobs API，因为这是手动、前端、飞书共用基础。
2. 接入 Settings API 的 runtime reschedule，避免 UI 设置无效。
3. 添加飞书 `/omka schedule` 命令和 NLU 示例。
4. 做 GitHub 搜索多策略召回和本地质量重排。
5. 最后调整 Settings/Dashboard UI 展示。

## 9. 风险与回滚

- 搜索阈值过高会漏掉新项目：保留 `search_min_stars` 和质量阈值为可配置项。
- 多策略搜索会增加 GitHub Search API 调用量：默认每个搜索源最多 3 次请求，并受 `search_rate_limit` 控制。
- cron 解析误判会造成任务时间错误：自然语言解析只支持少量明确模式，模糊表达直接拒绝。
- APScheduler job 更新失败时不能只写 DB：服务层必须先校验、再写 DB、再 reschedule，失败则返回错误。

## 10. 不在本轮做的事

- 不引入第三方搜索引擎。
- 不做网页/RSS 新 connector。
- 不用 LLM 对每条 GitHub repo 做质量判断。
- 不改数据库表结构，首版质量分放到 `item_metadata`。
