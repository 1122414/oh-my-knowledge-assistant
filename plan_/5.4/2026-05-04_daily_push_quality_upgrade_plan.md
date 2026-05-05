# 2026-05-04 OMKA 每日 GitHub 推送质量升级计划：搜索源头治理优先

## 0. 写给 opencode 的任务说明

本计划的核心判断是：每日推送质量首先取决于 GitHub 搜索源头。源头召回不相关、不稳定、不成体系，后面的排序、摘要、飞书推送都会变成对噪声的包装。

所以本阶段的优先级要调整为：

```text
先治理搜索源头
  -> 再做候选质量过滤
  -> 再做排序权重
  -> 再做摘要和 digest 升级
  -> 最后做反馈闭环
```

当前不要重写 OMKA 框架，不要另起一套推荐系统，不要接入复杂 agent 或向量数据库。要在现有链路上把 GitHub 搜索从“几个关键词”升级为“可配置、可解释、可观测、可迭代的搜索任务系统”。

现有链路：

```text
SourceConfig / sources.yaml
  -> GitHubConnector.fetch()
  -> RawItem
  -> cleaner.normalize
  -> NormalizedItem
  -> dedup_and_create_candidates()
  -> rank_candidates()
  -> generate_digest()
  -> Feishu / notification push
```

本计划只围绕这条链路补强，不推翻它。

## 1. 当前问题：源头搜索还不够像“发现系统”

### 1.1 当前已有能力

- `omka/app/connectors/github/connector.py` 支持 `repo` 和 `search` 两种来源。
- search 模式已支持多策略：`best_match`、`stars`、`updated`。
- `omka/app/pipeline/quality_reranker.py` 已有 `compute_source_quality()`。
- `normalize_search_repo()` 已把 `source_quality_score`、`source_quality_reasons`、`search_strategy`、`search_rank` 写入 `item_metadata`。
- `rank_candidates()` 已读取 `source_quality_score`，但当前没有真正纳入 final score。

### 1.2 当前源头问题

`data/profiles/sources.yaml` 目前只有少量泛 query：

```text
browser agent
rag agent
personal knowledge assistant llm
```

这些 query 的问题：

- 太短，语义边界不清。
- 容易搜到 demo、tutorial、awesome list、模板项目。
- 不能区分“成熟项目”“新兴项目”“可用工具”“研究原型”。
- 不能表达用户真正想看的项目形态。
- 不能解释为什么某个项目进入候选池。
- 搜索结果高度依赖 GitHub 默认排序，稳定性差。

结论：先不要把重点放在 LLM 摘要。要先把搜索源头改成“搜索任务矩阵”。

## 2. 本阶段目标

把 GitHub 搜索升级为以下形态：

```text
用户兴趣画像
  -> 搜索方向
  -> 搜索任务 SearchTask
  -> 多策略召回
  -> stars 分层
  -> 负向词降噪
  -> 源头质量门槛
  -> 候选池
  -> 后续排序和摘要
```

完成后，每一个进入候选池的项目都应该能回答：

- 它是被哪个搜索任务召回的？
- 它命中了哪个兴趣方向？
- 它属于成熟项目、新兴项目，还是近期活跃项目？
- 它为什么没有在源头被过滤？
- 它的源头质量证据是什么？

## 3. 任务边界

### 3.1 必须做

1. 将 `sources.yaml` 的 search 配置从简单 query 升级为搜索任务。
2. 兼容旧配置，不能让现有 sources.yaml 失效。
3. 为每个搜索任务增加意图、关键词、负向词、语言、star 分段、活跃时间等配置。
4. GitHubConnector 根据 SearchTask 生成多组 GitHub Search query。
5. 搜索结果必须记录召回来源、策略、star band、实际 query。
6. 在源头阶段过滤 archived、disabled、fork、长期不维护、明显低质量结果。
7. 控制每日总召回量，避免 GitHub API 和 LLM 成本失控。
8. 输出搜索质量报告，能看出每个 query 的召回和过滤情况。
9. 预留后续接入 GitHub Trending、RSS、Hacker News 等发现源接口。

### 3.2 现阶段严禁做

- 严禁重写 daily job。
- 严禁绕过 `SourceConfig` 和 `CandidateItem` 新建一套候选系统。
- 严禁把 GitHub 搜索改成无限分页或全网爬虫。
- 严禁现阶段抓 GitHub Trending 网页。
- 严禁 clone repo 做深度代码分析。
- 严禁接入向量数据库、embedding、复杂 RAG。
- 严禁让 LLM 自主生成无限 query 并直接执行。
- 严禁把 stars 当作唯一质量标准。
- 严禁只靠 LLM 判断项目好坏。
- 严禁在 API routes 中写业务逻辑。
- 严禁用 `hash()` 生成 ID。
- 严禁用 `as any` 或 `# type: ignore` 压掉类型问题。

## 4. P0：搜索源头治理

P0 是本次升级最重要的部分。排序和摘要都排在它之后。

### P0.1 定义 SearchTask 配置模型

位置：

```text
data/profiles/sources.yaml
omka/app/profiles/
omka/app/connectors/github/connector.py
omka/app/storage/db.py
```

建议配置形态：

```yaml
github:
  searches:
    - name: Browser Agent / Playwright
      enabled: true
      intent: discover_tool
      query: '"playwright agent"'
      description: 寻找基于 Playwright 的浏览器自动化 Agent 项目
      must_terms:
        - agent
      nice_terms:
        - playwright
        - automation
        - browser
        - llm
      negative_terms:
        - awesome
        - tutorial
        - template
        - demo
        - course
      languages:
        - Python
        - TypeScript
      star_bands:
        - 20..300
        - 300..5000
      pushed_after_days: 365
      limit_per_query: 5
      priority: 1.0
```

字段说明：

- `name`：搜索任务名称，用于报告和解释。
- `intent`：搜索意图，建议先支持 `discover_tool`、`discover_framework`、`discover_trend`、`track_known_area`。
- `query`：核心搜索词，不要太泛。
- `must_terms`：结果至少要在 name、description、topics、readme 中命中的词。
- `nice_terms`：加分词。
- `negative_terms`：降权或排除词。
- `languages`：优先语言，不强制时用于加分。
- `star_bands`：stars 分层。
- `pushed_after_days`：活跃时间窗口。
- `limit_per_query`：每个实际 GitHub query 最多取多少。
- `priority`：搜索任务自身权重。

兼容要求：

- 旧配置只有 `name/query/limit` 时仍可运行。
- 旧配置自动转换成默认 SearchTask。
- 不要第一阶段强制数据库大迁移，优先使用 `SourceConfig.config_json` 或现有配置扩展。

验收：

- 旧 `sources.yaml` 不改也能跑。
- 新 SearchTask 能生成多条实际 GitHub query。
- 每条搜索结果能记录来自哪个 SearchTask。

### P0.2 建立搜索任务矩阵

不要继续使用 3 个泛 query。第一版建议控制在 12 到 20 个搜索任务。

#### AI Agent

```text
"ai agent framework"
"multi agent framework"
"tool use agent"
"agent workflow"
"autonomous agent framework"
```

#### Browser Agent

```text
"browser agent" framework
"browser automation" llm agent
"playwright agent"
"computer use" agent
"web automation" ai agent
```

#### RAG

```text
"agentic rag"
"rag framework"
"knowledge graph rag"
"hybrid search" llm
"retrieval augmented generation" agent
```

#### Personal Knowledge Management

```text
"personal knowledge assistant"
"local knowledge base" llm
"second brain" ai
"markdown" ai assistant
"obsidian" ai assistant
```

原则：

- 宁可多个窄 query，不要一个大 query。
- 每个 query 要对应明确项目形态。
- 不要把论文、教程、awesome list 和真实工具混在一起。
- 第一版每日总候选控制在 80 个以内。

验收：

- 每个兴趣方向至少有 3 个搜索任务。
- 单个搜索任务最多产生 10 到 15 个候选。
- 每日总搜索结果不会爆量。

### P0.3 GitHub query 生成规则

位置：

```text
omka/app/connectors/github/connector.py
omka/app/connectors/github/client.py
```

GitHub query 不要由用户配置完整拼死。系统应根据 SearchTask 生成。

基础模板：

```text
{query} in:name,description,topics archived:false fork:false stars:{star_band} pushed:>{date}
```

README 补充模板：

```text
{query} in:readme archived:false fork:false stars:{star_band} pushed:>{date}
```

语言模板：

```text
{query} language:{language} in:name,description,topics archived:false fork:false stars:{star_band} pushed:>{date}
```

负向词处理：

第一阶段建议不要强行从 GitHub query 中排除全部 negative terms，而是分两级：

- 明确噪声词可以加 `NOT`：
  - `NOT awesome`
  - `NOT tutorial`
  - `NOT template`
- 其余 negative terms 进入后处理降权。

实际请求示例：

```text
"playwright agent" in:name,description,topics archived:false fork:false stars:20..300 pushed:>2025-05-04 NOT awesome NOT tutorial
"playwright agent" in:readme archived:false fork:false stars:20..300 pushed:>2025-05-04
"playwright agent" language:Python in:name,description,topics archived:false fork:false stars:300..5000 pushed:>2025-05-04
```

验收：

- 日志或 search report 中能看到实际 GitHub query。
- 每条 raw item metadata 中能保留 query 信息。
- query 生成函数可以单测。

### P0.4 多策略召回，但要控制组合爆炸

当前已有：

```text
best_match
stars
updated
```

保留这三路，但不要对每个 SearchTask 生成过多组合。

建议第一版上限：

```text
每个 SearchTask:
  star_bands 最多 2 个
  language 最多 2 个
  search scopes 最多 2 个：name/description/topics + readme
  sort strategies 最多 3 个
```

如果全组合太多，按优先级裁剪：

1. `in:name,description,topics` + best_match
2. `in:name,description,topics` + updated
3. `in:readme` + best_match
4. `sort=stars` 只对 priority 高的任务运行

默认每个 SearchTask 最多执行 4 到 6 个 GitHub Search API 请求。

验收：

- 有每日请求量上限。
- 单次 job 不会因为搜索任务增加而无限膨胀。

### P0.5 star 分层，不再只追大项目

只按 stars 排会导致老项目霸榜。每日推送更应该关注：

- 已有一定认可但还在成长的项目。
- 最近活跃的项目。
- 和用户兴趣精准相关的项目。

建议 star bands：

```text
20..300      新兴项目，可能有惊喜
300..5000    成长期项目，最值得推
5000..50000  成熟标杆，低频关注
```

第一阶段默认只开：

```text
20..300
300..5000
```

成熟标杆用固定 repo 或低频 search 处理，不要每天刷。

验收：

- report 能显示每个 star band 贡献的候选数。
- Top N 不再全是超高 stars 老项目。

### P0.6 源头质量门槛

位置：

```text
omka/app/connectors/github/connector.py
omka/app/pipeline/quality_reranker.py
```

在进入 RawItem 或 NormalizedItem 前后都可以做过滤，但要记录原因。

硬过滤：

- archived
- disabled
- fork
- full_name 为空
- stars 低于 SearchTask min_stars
- pushed_at 超过 `pushed_after_days` 太久

降权：

- name/description/topics/readme 都没有命中 must_terms
- negative_terms 命中
- open_issues_count / stars 过高
- README 缺失
- description 太短
- 最近一年无 release 且活跃度低

新增 metadata：

```text
search_task_name
search_task_intent
search_task_priority
actual_query
search_scope
search_strategy
star_band
source_filter_reasons
source_quality_score
source_quality_reasons
```

验收：

- 每个被过滤项目有原因。
- 每个入选候选有搜索来源证据。

### P0.7 搜索报告

位置建议：

```text
omka/app/services/push_quality_report.py
```

或先放在 daily job result 中。

搜索报告至少包含：

```json
{
  "search_tasks": [
    {
      "name": "Browser Agent / Playwright",
      "intent": "discover_tool",
      "request_count": 4,
      "fetched_count": 18,
      "unique_count": 9,
      "filtered_count": 5,
      "candidate_count": 4,
      "top_repos": ["owner/repo"],
      "filter_reasons": {
        "archived": 1,
        "stale": 2,
        "negative_term": 2
      }
    }
  ],
  "total_request_count": 0,
  "total_unique_repos": 0,
  "total_candidates": 0,
  "top_contributing_tasks": []
}
```

验收：

- 每天能看出哪个搜索任务质量高。
- 后续调 query 时有依据。

## 5. P1：搜索结果 enrich，但只 enrich 候选池

源头治理之后，再做轻量 repo 画像。

位置建议：

```text
omka/app/connectors/github/enricher.py
```

要做：

- 只 enrich 每个 SearchTask 的 Top 3 到 5。
- 每日 enrich 总量默认不超过 40。
- enrich 内容：
  - repo detail
  - README excerpt
  - latest release
  - license
  - homepage
  - default_branch
  - pushed_at
  - created_at
  - subscribers_count
  - network_count

沉淀字段：

```text
item_metadata.github_profile
```

严禁：

- 不 clone repo。
- 不读取大量文件。
- 不分析 commit diff。
- 不因 enrich 失败中断 daily job。

验收：

- 摘要输入里能看到 README excerpt。
- enrich 失败仍保留基础 search result。

## 6. P2：排序接入源头质量

位置：

```text
omka/app/pipeline/ranker.py
omka/app/core/config.py
.env.example
```

要做：

- 新增 `score_weight_source_quality`。
- `final_score` 纳入 `source_quality_score`。
- `score_detail` 保留搜索证据。

建议初始权重：

```env
SCORE_WEIGHT_INTEREST=0.30
SCORE_WEIGHT_PROJECT=0.20
SCORE_WEIGHT_FRESHNESS=0.15
SCORE_WEIGHT_POPULARITY=0.10
SCORE_WEIGHT_SOURCE_QUALITY=0.25
```

注意：

- 搜索源头治理后，source quality 权重应该高于 popularity。
- stars 只是成熟度信号，不是价值本身。

验收：

- 高相关中等 stars 项目可以超过低相关高 stars 项目。
- `score_detail` 能解释排名。

## 7. P3：摘要和 digest 升级

只有当搜索结果更干净后，再升级摘要。

位置：

```text
omka/app/pipeline/summarizer.py
omka/app/pipeline/digest_builder.py
```

LLM JSON 合同：

```json
{
  "one_liner": "一句话说明项目是什么",
  "problem": "它主要解决什么问题",
  "why_now": "为什么今天值得关注",
  "strengths": ["优势1", "优势2"],
  "risks": ["风险1", "风险2"],
  "fit_to_user": "和当前兴趣/项目的关系",
  "suggested_action": "star/read/try/skip",
  "summary": "100 到 160 字中文摘要",
  "recommendation_reason": "80 到 120 字中文推荐理由"
}
```

Digest 模板建议：

```markdown
# OMKA GitHub 技术雷达 | YYYY-MM-DD

## 今日搜索概览

- 搜索任务：N
- 唯一仓库：N
- 入选候选：N
- 今日主线：

## Top Picks

### 1. owner/repo

> 一句话定位

- 推荐等级：
- 搜索来源：
- 质量证据：
- Stars / Forks / Language：
- 为什么今天值得看：
- 风险：
- 建议动作：
- 链接：

## 观察池
```

严禁：

- 严禁让 LLM 编造 benchmark、融资、下载量、作者背景。
- 信息不足要明确写信息不足。

验收：

- 推送读者能快速判断是否值得点击。
- 每个项目都能显示搜索来源和质量证据。

## 8. P4：反馈闭环

位置：

```text
omka/app/services/recommendation_service.py
omka/app/services/memory_service.py
omka/app/pipeline/ranker.py
```

第一版只做轻量规则：

- confirm 过同类 query/topic：相关 SearchTask 加权。
- dislike/not_interested 过同类 query/topic：相关 SearchTask 降权。
- read_later 轻微加权，不等同喜欢。

预留字段：

```text
feedback_score
feedback_reasons
search_task_feedback_weight
```

验收：

- 用户反馈能影响后续搜索任务权重。
- 不需要机器学习模型。

## 9. 后续接口预留

### 9.1 DiscoveryProvider

预留目标：未来接入 GitHub Trending、Hacker News、RSS、Reddit、papers。

```python
class DiscoveryProvider(Protocol):
    source_type: str

    async def discover(self, config: DiscoveryConfig) -> list[DiscoveryItem]:
        ...
```

本阶段不要正式多源化，只让 GitHub Search 的结构向这个接口靠拢。

### 9.2 SearchTaskProvider

预留目标：未来可由用户画像、反馈、手动配置、LLM 建议共同生成搜索任务。

```python
class SearchTaskProvider(Protocol):
    def load_tasks(self) -> list[SearchTask]:
        ...
```

本阶段只从 YAML 加载。

### 9.3 ProjectProfiler

预留目标：未来深度分析 README、docs、examples、issues。

```python
class ProjectProfiler(Protocol):
    async def profile(self, repo_full_name: str) -> ProjectProfile:
        ...
```

本阶段只做轻量 enrich。

### 9.4 DigestRenderer

预留目标：未来支持 Markdown、Feishu card、HTML、前端页面。

本阶段只改 Markdown digest。

## 10. 建议文件改动清单

第一批必须改：

```text
data/profiles/sources.yaml
omka/app/connectors/github/client.py
omka/app/connectors/github/connector.py
omka/app/connectors/github/normalizer.py
omka/app/pipeline/quality_reranker.py
omka/app/pipeline/ranker.py
omka/app/core/config.py
.env.example
```

建议新增：

```text
omka/app/connectors/github/search_task.py
omka/app/connectors/github/enricher.py
omka/app/services/push_quality_report.py
tests/test_github_search_task.py
tests/test_github_query_builder.py
tests/test_github_quality_scoring.py
```

暂不改：

```text
frontend/
omka/app/api/
omka/app/integrations/feishu/
```

除非只是透传或展示已有字段。

## 11. 推荐实施顺序

### Step 1：SearchTask 模型和 query builder

完成：

- 定义 SearchTask。
- 兼容旧 search config。
- 实现 GitHub query builder。
- 增加 query builder 单测。

### Step 2：搜索任务矩阵

完成：

- 重写 `sources.yaml` 的 searches。
- 覆盖 AI Agent、Browser Agent、RAG、PKM。
- 总搜索任务控制在 12 到 20 个。

### Step 3：多策略召回和源头过滤

完成：

- best_match / updated / stars 分层召回。
- star bands。
- negative terms。
- archived/fork/stale 过滤。
- metadata 保留搜索证据。

### Step 4：搜索报告

完成：

- 每日搜索任务统计。
- 过滤原因统计。
- top contributing tasks。

### Step 5：enrich、排序、摘要

完成：

- enrich Top 候选。
- ranker 接入 source quality。
- digest 展示搜索来源和质量证据。

## 12. 配置建议

```env
SEARCH_RESULTS_PER_QUERY=5
SEARCH_MIN_STARS=20
SEARCH_MAX_CANDIDATES_PER_QUERY=15
SEARCH_EXPAND_QUERIES=true
SEARCH_QUALITY_MIN_SCORE=0.35
SEARCH_STALE_DAYS_THRESHOLD=365
SEARCH_DAILY_REQUEST_LIMIT=120
SEARCH_DAILY_ENRICH_LIMIT=40

SCORE_WEIGHT_INTEREST=0.30
SCORE_WEIGHT_PROJECT=0.20
SCORE_WEIGHT_FRESHNESS=0.15
SCORE_WEIGHT_POPULARITY=0.10
SCORE_WEIGHT_SOURCE_QUALITY=0.25

DIGEST_TOP_N=8
```

## 13. 测试要求

### 13.1 SearchTask 兼容测试

- 旧配置 `name/query/limit` 可转换。
- 新配置字段可正确加载。
- 缺省字段有合理默认值。

### 13.2 query builder 测试

覆盖：

- star band。
- pushed date。
- language。
- `in:name,description,topics`。
- `in:readme`。
- negative terms。

### 13.3 源头过滤测试

覆盖：

- archived。
- fork。
- stale。
- negative term。
- must_terms 未命中。
- 低 source quality。

### 13.4 搜索报告测试

覆盖：

- request_count。
- fetched_count。
- unique_count。
- filtered_count。
- candidate_count。
- filter_reasons。

### 13.5 排序测试

构造：

- A：高 stars，低相关。
- B：中 stars，高相关，高 source quality。
- C：低 stars，高相关，但长期不维护。

期望：

- B 排在 A 前。
- C 被降权或过滤。

## 14. 完成定义

第一阶段完成标准：

- 搜索源不再只是几个泛关键词。
- 每个候选项目都有搜索来源证据。
- 每日搜索任务可观测、可调参。
- 低质量项目在源头被过滤或降权。
- Top N 不再只由 stars 或 GitHub 默认排序决定。
- 后续改摘要、改飞书卡片、接入多源时，不需要推翻搜索治理结构。

一句话：先把“从哪里找、怎么找、为什么找到它”做扎实，再谈“怎么总结、怎么推送”。
