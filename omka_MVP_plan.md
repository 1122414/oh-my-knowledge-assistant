# OMKA MVP Plan

> OMKA = Oh My Knowledge Assistant  
> 目标：先做一个**个人个性化智能知识助手 MVP**。MVP 阶段只接入 GitHub，但架构必须提前设计成可扩展信息源、可沉淀知识、可演进为长期个人知识系统的底座。

---

## 1. 项目定位

OMKA 是一个面向个人用户的个性化智能知识助手。它会根据用户配置的信息源、兴趣方向、当前项目和长期目标，定期从外部信息源获取内容，并完成清洗、去重、结构化、个性化排序、摘要、推荐和知识沉淀。

MVP 阶段只做 GitHub 信息源，但不能做成简单 GitHub 爬虫，而要做成一个可扩展的信息采集与知识沉淀框架。

长期目标是：

> 从“每天帮我看 GitHub 有什么值得关注的东西”，逐步升级成“持续理解我、主动帮我筛选信息、沉淀知识、辅助项目研发和学习决策的个人知识操作系统”。

---

## 2. MVP 核心目标

MVP 只验证最小闭环：

```text
GitHub 信息源
    ↓
自动抓取
    ↓
统一结构化
    ↓
去重与候选池
    ↓
基于用户画像的个性化排序
    ↓
摘要与推荐理由生成
    ↓
每日 Markdown 简报
    ↓
用户收藏 / 忽略 / 入库
```

MVP 要做到：

1. 用户可以配置自己关注的 GitHub 仓库和关键词搜索。
2. 系统每天自动抓取最少量但高价值的 GitHub 信息。
3. 抓取结果统一转换为标准数据结构。
4. 系统对内容去重，并先进入候选池，而不是直接进入正式知识库。
5. 系统根据用户兴趣、当前项目、新鲜度和 GitHub 热度进行打分排序。
6. 系统为高分内容生成摘要、推荐理由、相关标签和建议动作。
7. 系统每天生成一份 Markdown 简报。
8. 用户可以将有价值内容收藏入库，也可以忽略低价值内容。

---

## 3. MVP 不做什么

为了避免过度设计，MVP 阶段暂时不做：

1. 知识图谱。
2. 多 Agent 协作。
3. 复杂 UI。
4. 多模态内容解析。
5. 聊天问答系统。
6. Neo4j。
7. 向量数据库。
8. 浏览器插件。
9. 飞书、Telegram、QQ Bot、邮箱等多端接入。
10. 大规模分布式爬虫。
11. GitHub commit 全量抓取。
12. GitHub 全量 Issue / PR / Discussion 抓取。
13. GitHub 代码文件解析。

这些能力可以后续扩展，但不进入 MVP 的最小交付范围。

---

## 4. MVP 必须完成的 7 个点

### 4.1 GitHub 信息源配置

MVP 只支持 GitHub，但接口必须预留扩展能力。

P0 只支持两类 GitHub 来源：

```yaml
github_sources:
  repos:
    - langchain-ai/langgraph
    - microsoft/playwright
    - browser-use/browser-use

  searches:
    - "browser agent"
    - "langgraph agent"
    - "personal knowledge assistant llm"
    - "rag agent"
```

暂时不做 Topic 独立抓取。Topic 可以后续并入 Search 查询，例如 `topic:ai-agent` 或 `topic:browser-automation`。

注意：GitHub 只是第一个 Connector，不能把系统主流程和 GitHub 强绑定。

统一 Connector 接口：

```python
class SourceConnector:
    source_type: str

    def fetch(self, config) -> list[RawItem]:
        pass

    def normalize(self, raw_item: RawItem) -> NormalizedItem:
        pass
```

后续 RSS、网页、论文、邮箱、飞书文档、Telegram 等来源，都通过实现这个接口接入。

---

### 4.2 每日自动抓取 GitHub 信息

MVP 必须支持每天自动运行一次，也支持手动触发。

P0 最小抓取范围只保留 3 类：

```text
1. 用户关注仓库的基础信息
2. 用户关注仓库的最新 1 条 Release
3. 用户关键词搜索得到的新仓库
```

暂时不要默认抓取：

```text
commit 列表
完整 README
完整代码文件
全部 Issue
全部 PR
Discussion
Contributor
Star 历史变化
Workflow
Dependency graph
```

推荐技术：

```text
APScheduler + GitHub REST API + httpx
```

---

### 4.3 统一数据结构

所有外部信息必须先转换成统一结构，后续才能扩展其他信息源。

核心流程：

```text
RawItem → GitHubRepoData / GitHubReleaseData → NormalizedItem → CandidateItem → KnowledgeItem
```

最小结构：

```python
class NormalizedItem:
    id: str
    source_id: str
    source_type: str
    item_type: str
    title: str
    url: str
    content: str
    author: str | None
    repo_full_name: str | None
    published_at: datetime | None
    updated_at: datetime | None
    fetched_at: datetime
    tags: list[str]
    metadata: dict
```

设计重点：

- GitHub repo、release、repo_search_result 都要被转换成统一 `NormalizedItem`。
- 未来网页、RSS、邮件、文档也要转换成同样结构。
- 系统核心 Pipeline 只处理统一数据结构，不关心具体来源。

---

### 4.4 去重与候选池

MVP 不能把抓到的所有信息直接进入正式知识库，否则知识库会很快被低价值内容污染。

必须设计三层：

```text
Raw Data 原始采集层
    ↓
Candidate Pool 候选知识池
    ↓
Confirmed Knowledge 正式知识库
```

必须支持：

```text
URL 去重
内容 hash 去重
候选状态管理：pending / ignored / confirmed
```

候选状态：

```python
status = "pending" | "ignored" | "confirmed"
```

最小去重策略：

```text
dedup_key = source_type + url
content_hash = sha256(normalized_title + normalized_content[:1000])
```

---

### 4.5 用户画像与兴趣配置

MVP 不做复杂长期记忆，但必须有显式可编辑的用户画像配置。

建议配置文件：

```text
data/profiles/
  identity.md
  interests.yaml
  projects.yaml
  sources.yaml
```

示例：

```yaml
interests:
  - name: AI Agent
    keywords:
      - agent
      - langgraph
      - multi-agent
      - tool use
    weight: 1.0

  - name: Browser Agent
    keywords:
      - playwright
      - browser automation
      - drissionpage
      - aria snapshot
    weight: 1.2

projects:
  - name: Personal Knowledge Assistant
    keywords:
      - personal ai
      - knowledge assistant
      - memory
      - recommendation
    weight: 1.3
```

MVP 阶段先使用：

```text
显式关键词 + 权重
```

不要一开始就依赖复杂 embedding 用户画像。显式画像更容易调试、解释和人工修改。

---

### 4.6 个性化排序与推荐理由

MVP 必须让系统能解释：

> 为什么这条内容值得推荐给我？

最小打分公式：

```text
final_score =
  兴趣匹配分 * 0.40
+ 项目相关分 * 0.30
+ 新鲜度分   * 0.15
+ GitHub 热度分 * 0.15
```

每条推荐至少包含：

```text
标题
链接
摘要
推荐理由
相关兴趣
相关项目
建议动作
```

推荐结果不能只是 GitHub 列表，否则它只是 RSS 聚合器，不是个性化知识助手。

---

### 4.7 每日 Markdown 简报与收藏入库

MVP 最小输出形式优先用 Markdown，不急着做复杂 UI。

每日简报路径：

```text
data/digests/YYYY-MM-DD.md
```

示例结构：

```markdown
# 今日 GitHub 知识简报

## 一、最值得关注

### 1. xxx 项目 / 更新
- 链接：
- 类型：repo / release / repo_search_result
- 摘要：
- 推荐理由：
- 相关兴趣：
- 相关项目：
- 建议动作：收藏 / 阅读 README / 研究实现 / 暂时忽略

## 二、与你当前项目相关

### Personal Knowledge Assistant 相关
- ...

### Browser Agent 相关
- ...

## 三、候选入库

- [ ] xxx
- [ ] xxx
```

必须支持用户反馈：

```text
收藏 → 进入正式知识库
忽略 → 后续不再推荐
不感兴趣 → 降低相关标签权重
稍后阅读 → 进入待读列表
```

正式知识保存路径：

```text
data/knowledge/github/xxx.md
```

---

## 5. GitHub MVP 抓取方案

这一节是 GitHub 信息源的最小实现规划。原则是：**先抓尽量少但最核心的数据，把全流程跑通，而不是做 GitHub 数据采集系统。**

---

### 5.1 通过什么方式、技术进行抓取

#### 5.1.1 抓取方式

MVP 阶段优先使用 GitHub REST API，不使用网页爬虫。

原因：

1. GitHub API 字段稳定，适合做工程化采集。
2. 不依赖网页 DOM，稳定性比 Playwright / Selenium / DrissionPage 更高。
3. 返回 JSON，天然适合结构化入库。
4. 后续可以通过 Token 支持更高额度和私有仓库。

基础链路：

```text
GitHub REST API
    ↓
httpx 请求
    ↓
RawItem 原始保存
    ↓
GitHubRepoData / GitHubReleaseData 事实模型
    ↓
NormalizedItem 统一知识条目
    ↓
CandidateItem 候选推荐
```

#### 5.1.2 推荐技术栈

| 模块 | 技术 | 作用 |
|---|---|---|
| API 服务 | FastAPI | 查看来源、手动触发抓取、查看候选池 |
| 定时任务 | APScheduler | 每天自动抓取 GitHub |
| HTTP 客户端 | httpx | 请求 GitHub REST API |
| 数据结构 | Pydantic | 规范 RawItem / NormalizedItem |
| ORM | SQLModel / SQLAlchemy | 写入 SQLite |
| 数据库 | SQLite | 存抓取记录、候选池、状态 |
| 输出 | Markdown | 生成每日简报 |
| 密钥 | `.env` | 保存 `GITHUB_TOKEN` |

#### 5.1.3 最小 API 端点

MVP 只需要使用 3 类 GitHub API：

```text
1. 获取指定仓库信息
GET /repos/{owner}/{repo}

2. 获取指定仓库最新 Release
GET /repos/{owner}/{repo}/releases?per_page=1

3. 根据关键词搜索新仓库
GET /search/repositories?q={query}&sort=updated&order=desc&per_page=5
```

基础请求头：

```python
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}
```

---

### 5.2 抓取什么东西

#### 5.2.1 P0：用户关注仓库基础信息

用户主动配置一些仓库，例如：

```yaml
github:
  repos:
    - langchain-ai/langgraph
    - microsoft/playwright
    - browser-use/browser-use
```

抓取字段：

| 字段 | 类型 | 用途 |
|---|---|---|
| id | int | GitHub 仓库 ID |
| full_name | str | 仓库唯一标识，例如 `langchain-ai/langgraph` |
| name | str | 仓库名 |
| owner.login | str | 作者 / 组织 |
| html_url | str | GitHub 页面链接 |
| description | Optional[str] | 判断项目做什么 |
| topics | list[str] | 判断技术方向 |
| language | Optional[str] | 判断技术栈 |
| stargazers_count | int | 热度 |
| forks_count | int | 传播度 |
| watchers_count | int | 关注度 |
| open_issues_count | int | 活跃问题数 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 元数据更新时间 |
| pushed_at | Optional[datetime] | 代码最近更新时间 |
| default_branch | str | 默认分支 |
| archived | bool | 是否归档 |
| disabled | bool | 是否不可用 |
| fork | bool | 是否 fork 仓库 |
| private | bool | 是否私有 |
| license.name | Optional[str] | 开源协议名称 |
| license.spdx_id | Optional[str] | 开源协议 ID |

用途：

```text
判断仓库是否活跃
判断它和用户兴趣是否匹配
判断最近是否值得关注
生成每日简报中的项目卡片
```

---

#### 5.2.2 P0：用户关注仓库最新 Release

Release 是 MVP 最值得抓的更新类型，因为它天然适合做“今日技术更新”。

只抓：

```text
每个仓库最新 1 条 Release
```

抓取字段：

| 字段 | 类型 | 用途 |
|---|---|---|
| id | int | Release ID |
| repo_full_name | str | 所属仓库 |
| tag_name | str | 版本号 |
| name | Optional[str] | Release 标题 |
| body | Optional[str] | Release 内容 |
| html_url | str | Release 链接 |
| author.login | Optional[str] | 发布者 |
| draft | bool | 是否草稿 |
| prerelease | bool | 是否预发布 |
| created_at | Optional[datetime] | 创建时间 |
| published_at | Optional[datetime] | 发布时间 |

用途：

```text
判断某个项目最近发布了什么新功能
生成技术更新摘要
推荐用户是否需要关注新版本
```

---

#### 5.2.3 P0：关键词搜索新仓库

如果只监控用户已关注仓库，系统会更像“GitHub 监控器”，不像“主动发现知识的助手”。所以 MVP 需要一个最小发现能力。

配置示例：

```yaml
github:
  searches:
    - name: Browser Agent
      query: "browser agent"
      limit: 5

    - name: RAG Agent
      query: "rag agent"
      limit: 5

    - name: Personal Knowledge Assistant
      query: "personal knowledge assistant llm"
      limit: 5
```

抓取限制：

```text
每个关键词每天只取 Top 5
每天搜索结果总量控制在 20-30 条以内
```

抓取字段与 repo 基础信息基本一致，额外保留：

| 字段 | 类型 | 用途 |
|---|---|---|
| search_query | str | 来源搜索词 |
| search_score | Optional[float] | GitHub 搜索相关性分数 |
| source_weight | float | 该搜索源配置权重 |

用途：

```text
主动发现用户没有手动关注的新项目
为每日简报提供新鲜内容
验证个性化排序是否有效
```

---

#### 5.2.4 P1 可选：高热 Issue / PR

第一版可以不抓 Issue 和 PR。等 P0 跑通后，如果内容太少，再加轻量版本。

P1 规则：

```text
每个配置仓库只抓最近 3 个高热 Issue
每个配置仓库只抓最近 3 个高热 PR
只看最近 7 天 updated 的内容
优先 comments 数较高、带 enhancement / feature / roadmap / discussion 标签的条目
```

P1 不是第一版必须项。

---

### 5.3 稳定性保证

#### 5.3.1 使用 GitHub Token

MVP 也建议使用 `GITHUB_TOKEN`，不要裸请求。

原因：

```text
请求额度更高
更稳定
后续支持私有仓库时不用重构
方便做用户级配置
```

`.env` 示例：

```env
GITHUB_TOKEN=ghp_xxx
```

---

#### 5.3.2 ETag / Last-Modified 条件请求

每次请求后保存响应头：

```text
ETag
Last-Modified
```

下次请求同一个 URL 时带上：

```text
If-None-Match: <etag>
If-Modified-Since: <last_modified>
```

如果内容没有变化，会返回：

```text
304 Not Modified
```

这样可以减少无效请求、降低额度消耗，并让每日任务更稳定。

---

#### 5.3.3 请求限速与重试

不要并发乱打 GitHub API。

MVP 建议：

```text
全局并发：2-5
Search API 单独限速
失败重试：最多 3 次
重试间隔：指数退避
```

伪代码：

```python
for attempt in range(3):
    try:
        response = await client.get(url)
        break
    except TimeoutError:
        await sleep(2 ** attempt)
```

如果遇到：

```text
403 / 429
```

读取响应头：

```text
x-ratelimit-remaining
x-ratelimit-reset
retry-after
```

然后等待，而不是继续硬重试。

---

#### 5.3.4 幂等写入，避免重复数据

所有抓取结果必须有唯一键。

建议：

```text
repo 类型唯一键：
github:repo:{full_name}

release 类型唯一键：
github:release:{full_name}:{tag_name}

search_result 类型唯一键：
github:search_repo:{full_name}
```

数据库写入使用 upsert：

```text
存在则更新
不存在则插入
```

这样定时任务重复跑不会产生脏数据。

---

#### 5.3.5 分层保存，方便排错

至少保存三层：

```text
raw_items          原始抓取数据
normalized_items   统一结构化数据
candidate_items    候选推荐数据
```

好处：

```text
摘要错了，可以回看 normalized item
字段映射错了，可以回看 raw item
推荐错了，可以回看 score_detail
```

---

#### 5.3.6 单个来源失败不影响全局任务

例如 10 个仓库中有 1 个 404，不能让整个每日任务失败。

任务状态设计：

```text
success
partial_success
failed
```

单个 source 失败后记录错误，然后继续抓其他 source。

---

### 5.4 抓取数据字段、类型设计

GitHub MVP 数据模型分成 5 层：

```text
SourceConfig      用户配置的数据源
RawItem           GitHub API 原始抓取结果
GitHubRepoData    GitHub 仓库事实数据
GitHubReleaseData GitHub Release 事实数据
NormalizedItem    统一知识条目
CandidateItem     候选推荐条目
```

---

#### 5.4.1 SourceConfig

```python
class SourceConfig(BaseModel):
    id: str
    source_type: Literal["github"]

    name: str
    enabled: bool = True

    mode: Literal["repo", "search"]

    # repo 模式
    repo_full_name: str | None = None

    # search 模式
    query: str | None = None
    limit: int = 5

    weight: float = 1.0

    created_at: datetime
    updated_at: datetime
    last_fetched_at: datetime | None = None
```

repo 来源示例：

```json
{
  "id": "src_github_langgraph",
  "source_type": "github",
  "name": "LangGraph",
  "enabled": true,
  "mode": "repo",
  "repo_full_name": "langchain-ai/langgraph",
  "weight": 1.2
}
```

search 来源示例：

```json
{
  "id": "src_search_browser_agent",
  "source_type": "github",
  "name": "Browser Agent Search",
  "enabled": true,
  "mode": "search",
  "query": "browser agent",
  "limit": 5,
  "weight": 1.1
}
```

---

#### 5.4.2 RawItem

RawItem 用来保存 GitHub API 返回的原始数据。

```python
class RawItem(BaseModel):
    id: str

    source_id: str
    source_type: Literal["github"]

    item_type: Literal[
        "github_repo",
        "github_release",
        "github_repo_search_result"
    ]

    fetch_url: str
    http_status: int

    raw_data: dict

    etag: str | None = None
    last_modified: str | None = None

    fetched_at: datetime
```

设计重点：

```text
raw_data 保留完整 JSON
etag / last_modified 用于下次条件请求
fetch_url 用于排查问题
```

---

#### 5.4.3 GitHubRepoData

```python
class GitHubRepoData(BaseModel):
    id: int
    node_id: str | None = None

    full_name: str
    name: str
    owner_login: str

    html_url: str
    api_url: str

    description: str | None = None
    topics: list[str] = []
    language: str | None = None

    stargazers_count: int = 0
    forks_count: int = 0
    watchers_count: int = 0
    open_issues_count: int = 0

    default_branch: str | None = None

    archived: bool = False
    disabled: bool = False
    fork: bool = False
    private: bool = False

    license_name: str | None = None
    license_spdx_id: str | None = None

    created_at: datetime
    updated_at: datetime
    pushed_at: datetime | None = None

    # search 模式可选字段
    search_query: str | None = None
    search_score: float | None = None
```

这个模型用于：

```text
repo 基础信息
repo_search_result 搜索结果
```

---

#### 5.4.4 GitHubReleaseData

```python
class GitHubReleaseData(BaseModel):
    id: int
    repo_full_name: str

    tag_name: str
    name: str | None = None
    body: str | None = None

    html_url: str
    api_url: str

    author_login: str | None = None

    draft: bool = False
    prerelease: bool = False

    created_at: datetime | None = None
    published_at: datetime | None = None
```

---

#### 5.4.5 NormalizedItem

这是最重要的结构。后续不管来源是 GitHub、网页、RSS、飞书、邮箱，都要转成这个结构。

```python
class NormalizedItem(BaseModel):
    id: str

    source_type: Literal["github"]
    source_id: str

    item_type: Literal[
        "repo",
        "release",
        "repo_search_result"
    ]

    title: str
    url: str
    content: str

    author: str | None = None
    repo_full_name: str | None = None

    published_at: datetime | None = None
    updated_at: datetime | None = None
    fetched_at: datetime

    tags: list[str] = []

    metadata: dict = {}
```

不同类型的转换规则：

repo 类型：

```python
title = repo.full_name
url = repo.html_url
content = f"""
{repo.description}

Topics: {repo.topics}
Language: {repo.language}
Stars: {repo.stargazers_count}
Forks: {repo.forks_count}
Recently pushed at: {repo.pushed_at}
"""
tags = repo.topics + [repo.language]
```

release 类型：

```python
title = f"{repo_full_name} {release.tag_name}: {release.name}"
url = release.html_url
content = release.body or release.name or ""
published_at = release.published_at
tags = ["release", repo_full_name]
```

repo_search_result 类型：

```python
title = repo.full_name
url = repo.html_url
content = f"""
{repo.description}

Topics: {repo.topics}
Language: {repo.language}
Stars: {repo.stargazers_count}
Updated at: {repo.updated_at}
"""
tags = repo.topics + [repo.language]
```

---

#### 5.4.6 CandidateItem

CandidateItem 是进入每日简报前的数据。

```python
class CandidateItem(BaseModel):
    id: str
    normalized_item_id: str

    title: str
    url: str
    item_type: Literal[
        "repo",
        "release",
        "repo_search_result"
    ]

    summary: str | None = None
    recommendation_reason: str | None = None

    score: float = 0.0

    score_detail: dict = {
        "interest_score": 0.0,
        "project_score": 0.0,
        "freshness_score": 0.0,
        "popularity_score": 0.0,
        "source_weight": 1.0
    }

    matched_interests: list[str] = []
    matched_projects: list[str] = []

    status: Literal[
        "pending",
        "ignored",
        "confirmed"
    ] = "pending"

    created_at: datetime
    updated_at: datetime
```

---

### 5.5 推荐数据库表设计

MVP SQLite 可以先有这些表：

```text
source_configs
fetch_runs
request_cache
raw_items
normalized_items
candidate_items
knowledge_items
user_feedback
```

#### source_configs

```text
id
source_type
name
mode
repo_full_name
query
limit
weight
enabled
last_fetched_at
created_at
updated_at
```

#### fetch_runs

```text
id
job_type
started_at
finished_at
status
fetched_count
normalized_count
candidate_count
error_count
error_message
```

#### request_cache

```text
id
request_url
etag
last_modified
last_status
last_fetched_at
```

#### raw_items

```text
id
source_id
source_type
item_type
fetch_url
http_status
raw_data_json
etag
last_modified
fetched_at
```

#### normalized_items

```text
id
source_id
source_type
item_type
title
url
content
author
repo_full_name
published_at
updated_at
fetched_at
tags_json
metadata_json
content_hash
```

#### candidate_items

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

---

### 5.6 GitHub MVP 最小抓取流程

最终流程可以这样落地：

```text
1. Scheduler 每天触发 github_daily_job

2. 读取 source_configs

3. 对 repo 类型 source：
   - GET /repos/{owner}/{repo}
   - GET /repos/{owner}/{repo}/releases?per_page=1

4. 对 search 类型 source：
   - GET /search/repositories?q={query}&sort=updated&order=desc&per_page=5

5. 保存 RawItem

6. 转成 GitHubRepoData / GitHubReleaseData

7. 转成 NormalizedItem

8. 用 url + content_hash 去重

9. 根据 interests.yaml / projects.yaml 打分

10. Top 5-10 进入每日简报

11. 调用 LLM 生成：
    - summary
    - recommendation_reason
    - matched_interests
    - matched_projects
    - suggested_action

12. 生成 data/digests/YYYY-MM-DD.md

13. 用户收藏后写入 knowledge_items 和 data/knowledge/github/
```

---

## 6. MVP 总体架构

```text
                ┌────────────────────┐
                │   User Config       │
                │ 用户兴趣 / 项目 / 来源 │
                └─────────┬──────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                 Scheduler 调度层                    │
│              定时任务 / 手动触发                     │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│              Source Connectors 信息源接入层          │
│        GitHub Connector / Future RSS / Web / Email  │
└───────────────────────┬─────────────────────────────┘
                        │ RawItem
                        ▼
┌─────────────────────────────────────────────────────┐
│              Normalize & Clean 规范化层              │
│          清洗 / 统一字段 / 提取正文 / 元数据            │
└───────────────────────┬─────────────────────────────┘
                        │ NormalizedItem
                        ▼
┌─────────────────────────────────────────────────────┐
│              Dedup & Candidate Pool 候选池            │
│            URL 去重 / 内容指纹去重 / 状态管理           │
└───────────────────────┬─────────────────────────────┘
                        │ CandidateItem
                        ▼
┌─────────────────────────────────────────────────────┐
│              Personal Ranker 个性化排序层             │
│       兴趣匹配 / 项目相关度 / 新鲜度 / GitHub 热度       │
└───────────────────────┬─────────────────────────────┘
                        │ RankedItem
                        ▼
┌─────────────────────────────────────────────────────┐
│              Summarizer & Tagger 摘要打标层           │
│          摘要 / 标签 / 推荐理由 / 建议动作              │
└───────────────────────┬─────────────────────────────┘
                        │ DigestItem
                        ▼
┌─────────────────────────────────────────────────────┐
│              Digest & Knowledge Store 输出层          │
│          每日简报 / 候选知识池 / 正式知识库             │
└─────────────────────────────────────────────────────┘
```

---

## 7. 推荐目录结构

```text
omka/
  app/
    main.py

    core/
      config.py
      scheduler.py
      logging.py

    connectors/
      base.py
      github/
        connector.py
        client.py
        normalizer.py
        schemas.py

    pipeline/
      fetcher.py
      cleaner.py
      deduper.py
      ranker.py
      summarizer.py
      tagger.py
      digest_builder.py
      knowledge_writer.py

    profiles/
      profile_loader.py
      interest_model.py

    storage/
      db.py
      models.py
      repositories.py
      markdown_store.py

    api/
      routes_sources.py
      routes_digest.py
      routes_feedback.py
      routes_knowledge.py

    services/
      daily_job.py
      manual_run.py

  data/
    profiles/
      identity.md
      interests.yaml
      projects.yaml
      sources.yaml

    raw/
      github/

    digests/

    knowledge/
      github/

    db/
      app.sqlite
```

---

## 8. 推荐技术选型

| 模块 | MVP 推荐 |
|---|---|
| 后端 | FastAPI |
| 定时任务 | APScheduler |
| 数据库 | SQLite |
| ORM | SQLModel 或 SQLAlchemy |
| GitHub 接入 | GitHub REST API |
| HTTP 客户端 | httpx |
| 配置文件 | YAML + Markdown |
| 摘要模型 | OpenAI / Qwen / 本地模型均可 |
| 输出 | Markdown 文件 + 简单 API |
| 部署 | Docker Compose |

MVP 不建议一开始就引入：

```text
Kafka
Neo4j
Milvus
多 Agent 框架
微服务
复杂前端
```

---

## 9. MVP API 设计

### 9.1 信息源管理

```http
GET /sources
POST /sources
PUT /sources/{source_id}
DELETE /sources/{source_id}
POST /sources/{source_id}/run
```

### 9.2 每日简报

```http
GET /digests
GET /digests/{date}
POST /digests/run-today
```

### 9.3 候选知识池

```http
GET /candidates
POST /candidates/{id}/confirm
POST /candidates/{id}/ignore
POST /candidates/{id}/feedback
```

### 9.4 正式知识库

```http
GET /knowledge
GET /knowledge/{id}
POST /knowledge
PUT /knowledge/{id}
DELETE /knowledge/{id}
```

### 9.5 用户画像

```http
GET /profile
PUT /profile/interests
PUT /profile/projects
```

---

## 10. 开发阶段规划

### Phase 1：项目骨架与配置系统

目标：

1. 搭建 FastAPI 项目。
2. 建立目录结构。
3. 实现配置文件读取。
4. 初始化 SQLite 数据库。
5. 实现基础日志。

验收标准：

1. 后端可以启动。
2. 可以读取 `sources.yaml`、`interests.yaml`、`projects.yaml`。
3. 可以初始化数据库表。
4. 可以通过 API 查看当前配置。

---

### Phase 2：GitHub Connector P0

目标：

1. 支持 repo 模式。
2. 支持 search 模式。
3. 支持抓取 repo 基础信息。
4. 支持抓取 repo 最新 1 条 Release。
5. 支持关键词搜索新仓库。
6. 统一输出 RawItem。
7. 保存原始抓取记录。

验收标准：

1. 配置 GitHub repo 后可以抓取仓库基础信息。
2. 配置 GitHub repo 后可以抓取最新 Release。
3. 配置搜索关键词后可以返回相关仓库。
4. 所有结果写入数据库。
5. 重复运行不会重复插入相同 URL。

---

### Phase 3：规范化、去重、候选池

目标：

1. RawItem 转 GitHubRepoData / GitHubReleaseData。
2. 再转成 NormalizedItem。
3. URL 去重。
4. 内容 hash 去重。
5. 生成 CandidateItem。

验收标准：

1. 同一个 GitHub 内容不会重复进入候选池。
2. 每条候选内容都有统一标题、URL、正文、类型、元数据。
3. 可以通过 API 查看候选池。

---

### Phase 4：个性化排序

目标：

1. 读取用户兴趣和当前项目。
2. 对候选内容计算分数。
3. 输出 score_detail。
4. 按分数排序。

验收标准：

1. 与用户兴趣匹配的内容排名更高。
2. 与当前项目相关的内容排名更高。
3. 每个分数都有可解释字段。
4. 可以通过 API 查看排序结果。

---

### Phase 5：摘要与每日简报

目标：

1. 对 Top N 内容生成摘要。
2. 生成推荐理由。
3. 生成标签。
4. 输出 Markdown 每日简报。

验收标准：

1. 每天可以生成一个 `YYYY-MM-DD.md`。
2. 简报中包含摘要、推荐理由、相关项目、建议动作。
3. 摘要失败时不影响整个任务运行。
4. 支持手动重新生成今日简报。

---

### Phase 6：用户反馈与知识入库

目标：

1. 支持收藏、忽略、不感兴趣、稍后阅读。
2. 支持候选内容转正式知识。
3. 正式知识写入 Markdown 和数据库。
4. 用户反馈影响后续排序。

验收标准：

1. 用户点击收藏后，候选条目变成 KnowledgeItem。
2. 知识内容保存到 `data/knowledge/`。
3. 忽略内容不会再次出现在推荐中。
4. 收藏过的标签后续权重提升。

---

## 11. 最小可交付版本定义

MVP 最小可交付版本必须包含：

```text
1. GitHub 信息源配置
2. GitHub P0 抓取：repo 基础信息 / 最新 Release / 关键词搜索新仓库
3. 每日自动抓取
4. 统一数据结构
5. 去重与候选池
6. 用户兴趣 / 项目画像配置
7. 个性化排序 + 推荐理由
8. 每日 Markdown 简报
9. 收藏 / 忽略 / 入库反馈
```

最终交付效果：

> 每天从 GitHub 自动发现和用户高度相关的技术信息，解释为什么推荐，并允许用户将有价值内容沉淀成个人知识库。

---

## 12. 后续扩展预留

MVP 完成后，可以按以下方向扩展。

### 12.1 GitHub 内部扩展

```text
MVP+：Topic 查询
MVP+：最近 3 个高热 Issue
MVP+：最近 3 个高热 PR
V2：README 摘要
V2：Issue / PR 讨论摘要
V3：代码结构理解
V3：项目依赖与技术栈分析
```

扩展原则：先增加 item_type，再统一转成 NormalizedItem，不要破坏主 Pipeline。

---

### 12.2 信息源扩展

```text
RSS Connector
Webpage Connector
Arxiv Connector
Email Connector
Feishu Connector
Telegram Connector
QQ Bot Connector
Local File Connector
Meeting Notes Connector
```

扩展原则：

```python
fetch() -> list[RawItem]
normalize() -> NormalizedItem
```

只要实现统一 Connector 接口，就可以接入主 Pipeline。

---

### 12.3 知识库升级

演进路径：

```text
MVP：SQLite + Markdown
    ↓
第二阶段：PostgreSQL + Markdown
    ↓
第三阶段：PostgreSQL + Vector DB
    ↓
最终阶段：结构化数据库 + 向量检索 + 知识图谱 + 文件知识库
```

---

### 12.4 知识图谱预留

MVP 暂时不上 Neo4j，但 `KnowledgeItem` 中预留字段：

```python
entities: list[str]
relations: list[dict]
related_projects: list[str]
```

未来可抽取：

```text
GitHub 项目
作者
组织
技术栈
框架
论文
产品
用户项目
用户兴趣标签
```

关系示例：

```text
LangGraph → belongs_to → langchain-ai
LangGraph → related_to → Agent Workflow
Personal Knowledge Assistant → may_use → LangGraph
```

---

### 12.5 Agent 协同预留

未来可以拆分为：

| Agent | 职责 |
|---|---|
| Collection Agent | 采集信息 |
| Cleaning Agent | 清洗和去重 |
| Ranking Agent | 个性化排序 |
| Summary Agent | 摘要和解释 |
| Knowledge Agent | 知识入库和关联 |
| Governance Agent | 删除、过期、归档、冲突检测 |
| Recommendation Agent | 主动推荐 |

MVP 阶段不要真正上多 Agent，但模块命名和接口可以提前对齐。

---

## 13. 关键风险与控制

### 风险 1：信息太多，用户不想看

控制方式：

1. 每天只推荐 Top 5 到 Top 10。
2. 每条内容必须有推荐理由。
3. 支持忽略和不感兴趣反馈。
4. 不把所有抓取内容直接展示给用户。

### 风险 2：知识库被低价值内容污染

控制方式：

1. 引入候选池。
2. 用户确认后再正式入库。
3. 高置信内容才考虑自动入库。
4. 支持删除、归档和过期。

### 风险 3：GitHub 内容噪声大

控制方式：

1. P0 只抓 repo 基础信息、最新 Release、关键词搜索新仓库。
2. 默认不抓每条 commit。
3. 默认不抓全量 Issue / PR / Discussion。
4. 搜索结果按热度、活跃度、新鲜度和用户兴趣过滤。
5. 引入用户兴趣和项目相关度打分。

### 风险 4：后续扩展困难

控制方式：

1. Connector 插件化。
2. 数据模型统一。
3. Pipeline 分层。
4. 存储层隔离。
5. 不让 GitHub 逻辑污染核心业务。

---

## 14. 最终总结

OMKA MVP 的重点不是做一个功能复杂的知识管理平台，也不是做 GitHub 全量数据采集系统，而是先做出一个稳定的最小闭环：

```text
GitHub → 抓取 → 结构化 → 去重 → 个性化排序 → 摘要推荐 → 每日简报 → 收藏入库
```

GitHub MVP 第一版只需要抓：

```text
1. 用户关注仓库的基础信息
2. 用户关注仓库的最新 1 条 Release
3. 用户关键词搜索到的新仓库
```

MVP 的核心价值是：

> 每天自动从 GitHub 中筛选出真正与用户兴趣、当前项目和长期目标相关的信息，并通过可解释推荐和知识入库机制，把碎片信息逐步沉淀为个人知识资产。
