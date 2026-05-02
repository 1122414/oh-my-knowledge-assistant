# OMKA 记忆、推荐、飞书与多模态升级计划

> 生成日期：2026-05-02  
> 适用项目：Oh My Knowledge Assistant  
> 当前定位：从 GitHub 知识 Digest MVP 升级为具备个人记忆、可解释推荐、主动推送、飞书 Agent 对话执行通道和多模态知识资产管理能力的个人知识助手。

---

## 1. 升级目标

这次升级围绕五个重点能力展开：

1. 三大记忆：用户记忆、对话记忆、系统记忆。
2. 推荐与解释：让推荐不仅给结果，还能说明依据，并能被用户反馈修正。
3. 主动推送：从“每日摘要通知”升级为“基于用户目标、上下文和时机的主动建议”。
4. 飞书渠道完善：飞书作为对话接入通道，用户通过飞书和 Agent 对话，由 Agent 按权限调用系统能力，执行信息源、候选知识、知识库、配置、任务、推送和记忆相关操作。
5. 多模态知识资产：支持图片、PDF、文档、表格、PPT、网页截图等资产进入统一知识生命周期。

升级完成后的产品目标不是简单的“知识库”，而是：

```text
采集信息 -> 形成候选 -> 结合记忆排序 -> 解释推荐 -> 主动推送 -> 用户反馈 -> 更新记忆 -> 沉淀知识资产
```

也就是把 OMKA 从“内容处理工具”推进到“个人知识助理系统”。

---

## 2. 当前系统基线

### 2.1 已有能力

当前系统已经具备以下基础：

| 能力 | 当前实现 |
|---|---|
| 数据源 | GitHub repo、GitHub release、GitHub repository search |
| 数据管线 | RawItem -> NormalizedItem -> CandidateItem -> KnowledgeItem |
| 推荐排序 | 按兴趣、项目、新鲜度、GitHub 热度加权 |
| AI 摘要 | LLM 生成 summary、recommendation_reason，失败时降级为简单摘要 |
| Digest | 生成每日 Markdown digest |
| 人工确认 | candidate 支持 confirm、ignore、dislike、read_later |
| 知识库 | confirmed candidate 写入 KnowledgeItem 和 Markdown |
| 飞书 | App Bot、Webhook、私聊绑定、基础命令、Agent 对话雏形 |
| 对话记录 | ConversationMessage 保存飞书 user/assistant 消息 |
| Agent 上下文 | 取最近对话、digest、knowledge、candidate、interest profile 拼接上下文 |
| 系统日志 | FetchRun、AgentRun、NotificationRun、FeishuMessageRun 等记录运行情况 |

本地数据库当前状态：

| 表 | 数量 |
|---|---:|
| source_configs | 6 |
| raw_items | 59 |
| normalized_items | 41 |
| candidate_items | 41 |
| knowledge_items | 1 |
| conversation_messages | 16 |
| agent_runs | 8 |
| fetch_runs | 5 |
| feishu_direct_conversations | 1 |

### 2.2 关键短板

| 问题 | 影响 |
|---|---|
| 记忆类型没有统一模型 | 用户画像、对话、系统运行、知识资产分散在不同表和文件中，难以形成可治理的长期记忆 |
| identity.md 未充分接入 | 个人身份、目标、偏好没有进入 Agent 和推荐主链路 |
| 对话只取最近消息 | 没有长期总结、事实抽取、记忆候选、过期策略 |
| 推荐反馈没有学习闭环 | ignore、dislike、confirm 只改变状态，不更新兴趣权重和推荐策略 |
| 推送内容较粗 | 自动推送主要是任务结果和 digest 链接，不够个性化 |
| 飞书 Agent 执行能力不够 | 用户还不能通过飞书对话让 Agent 完整执行配置、信息源、知识库和记忆管理任务 |
| 多模态基本缺失 | 当前主要处理 GitHub 文本和 metadata，没有统一资产表、文件存储、解析队列、OCR/摘要链路 |
| 中文文案和 prompt 存在乱码 | 会影响前端体验、飞书体验和 LLM 输出质量 |

---

## 3. 总体架构升级

建议新增一层“记忆与资产内核”，放在现有 pipeline、agent、feishu、api 之间。

```text
                 +---------------------+
                 |   Feishu / Web UI   |
                 +----------+----------+
                            |
                            v
                 +---------------------+
                 |  Agent Orchestrator |
                 +----------+----------+
                            |
          +-----------------+-----------------+
          |                                   |
          v                                   v
+--------------------+              +--------------------+
| Memory Service     |              | Action Service     |
| user/conversation/ |              | sources/settings/  |
| system memory      |              | jobs/knowledge     |
+---------+----------+              +---------+----------+
          |                                   |
          v                                   v
+--------------------+              +--------------------+
| Recommendation     |              | Pipeline Services  |
| Service            |              | fetch/clean/rank   |
+---------+----------+              +---------+----------+
          |                                   |
          v                                   v
+--------------------+              +--------------------+
| Asset Service      |              | Notification       |
| multimodal files   |              | Service            |
+--------------------+              +--------------------+
```

核心原则：

1. 记忆是独立资源，不再散落在 YAML、聊天表和运行日志里。
2. Agent 不直接操作底层表，而是通过 Action Service 执行可审计操作。
3. 推荐服务必须输出“推荐结果 + 解释 + 可操作反馈入口”。
4. 飞书是第一优先交互端，Web UI 是管理端和可视化补充。
5. 多模态资产先统一建模，再逐步扩展解析能力。

---

## 4. 模块一：三大记忆升级

### 4.1 目标

建立统一记忆系统，明确区分：

| 记忆类型 | 含义 | 示例 |
|---|---|---|
| 用户记忆 | 与用户身份、偏好、目标、长期项目有关的信息 | 用户关注 AI Agent、正在做 OMKA、偏好飞书操作 |
| 对话记忆 | 从对话中沉淀出的事实、意图、决策、待办和上下文摘要 | 用户说“下一步重点做记忆系统” |
| 系统记忆 | 系统运行、配置、数据源、任务、推送、Agent 操作记录 | 某数据源失败、上次推送成功、LLM 配置变更 |

### 4.2 新增数据模型

建议新增 `MemoryItem`：

```python
class MemoryItem(SQLModel, table=True):
    __tablename__ = "memory_items"

    id: str = Field(primary_key=True)
    memory_type: str  # user / conversation / system
    scope: str         # global / user / conversation / source / project
    subject: str       # user profile / project / preference / task / setting
    content: str
    summary: str | None = None
    source_type: str   # manual / conversation / feedback / system_event / import
    source_ref: str | None = None
    confidence: float = 0.8
    importance: float = 0.5
    status: str = "active"  # candidate / active / archived / rejected / expired
    visibility: str = "private"
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
```

建议新增 `MemoryEvent`：

```python
class MemoryEvent(SQLModel, table=True):
    __tablename__ = "memory_events"

    id: int | None = Field(default=None, primary_key=True)
    memory_id: str
    event_type: str  # created / confirmed / edited / used / rejected / expired
    actor_type: str  # user / agent / system
    actor_id: str | None = None
    detail_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 4.3 用户记忆

当前用户记忆主要散落在：

```text
data/profiles/interests.yaml
data/profiles/projects.yaml
data/profiles/identity.md
UserFeedback
CandidateItem.matched_interests
```

升级方式：

1. 保留 YAML 作为初始化配置，但运行时以 `memory_items` 为主。
2. 启动时将 interests、projects、identity.md 同步为 `user` 类型记忆。
3. 每次用户 confirm / dislike / read_later 后，生成或更新 preference memory。
4. 用户可在飞书中查看、修改和删除用户记忆。

飞书命令建议：

```text
/omka memory profile
/omka memory interests
/omka memory add 我最近重点关注多模态知识资产
/omka memory forget 记忆ID
/omka memory update 记忆ID 新内容
```

### 4.4 对话记忆

当前对话只存消息，并在 Agent 上下文里取最近 N 条。升级后分三层：

| 层级 | 存储 | 用途 |
|---|---|---|
| 原始消息 | ConversationMessage | 审计和短期上下文 |
| 会话摘要 | MemoryItem(memory_type=conversation, subject=session_summary) | 降低上下文长度 |
| 长期记忆候选 | MemoryItem(status=candidate) | 等待用户确认是否写入长期记忆 |

对话处理流程：

```text
用户消息 -> 保存 ConversationMessage
        -> Agent 回复
        -> 保存 assistant 消息
        -> MemoryExtractor 抽取候选记忆
        -> 低风险系统记忆自动 active
        -> 用户偏好/身份类记忆进入 candidate
        -> 飞书提示用户确认
```

记忆抽取示例：

```text
用户说：“我现在要重点做用户、对话、系统记忆”

抽取：
- type: user
  subject: current_priority
  content: 用户当前优先级是建设用户记忆、对话记忆和系统记忆。
  confidence: 0.95
  status: candidate
```

### 4.5 系统记忆

当前系统记忆散落在 FetchRun、AgentRun、NotificationRun、FeishuMessageRun、AppSetting。升级后应保留原始运行表，同时沉淀可读系统记忆。

示例：

| 系统事件 | 是否沉淀为系统记忆 |
|---|---|
| 连续 3 次 GitHub 抓取失败 | 是 |
| 用户修改 LLM model | 是 |
| 飞书推送失败 | 是 |
| 单次普通成功运行 | 不一定，只保留 run log |
| 数据源长期没有新内容 | 是 |

飞书命令建议：

```text
/omka system status
/omka system recent
/omka system errors
/omka system explain last-run
/omka system settings
```

### 4.6 API 建议

```http
GET    /memories
POST   /memories
GET    /memories/{id}
PUT    /memories/{id}
DELETE /memories/{id}
POST   /memories/{id}/confirm
POST   /memories/{id}/reject
POST   /memories/extract-from-conversation
GET    /memories/profile
```

### 4.7 验收标准

1. 用户可以在飞书中查看、添加、修改、删除记忆。
2. Agent 回答时能引用用户记忆、对话摘要和系统状态。
3. 对话能自动产生候选记忆。
4. 用户确认后的记忆会影响推荐排序和推送。
5. 所有记忆变更有事件日志。

---

## 5. 模块二：推荐与解释升级

### 5.1 目标

从当前的简单加权排序升级为“可解释、可反馈、可学习”的推荐系统。

当前推荐公式：

```text
score = interest_score * 0.40
      + project_score * 0.30
      + freshness_score * 0.15
      + popularity_score * 0.15
```

建议升级为：

```text
final_score =
  profile_match_score
+ project_relevance_score
+ memory_relevance_score
+ novelty_score
+ source_trust_score
+ freshness_score
+ popularity_score
+ feedback_adjustment
+ push_timing_score
```

### 5.2 新增数据模型

建议新增 `RecommendationRun`：

```python
class RecommendationRun(SQLModel, table=True):
    __tablename__ = "recommendation_runs"

    id: int | None = Field(default=None, primary_key=True)
    trigger_type: str  # daily / manual / feishu_query / push
    user_external_id: str | None = None
    candidate_count: int = 0
    selected_count: int = 0
    strategy: str = "default"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
```

建议新增 `RecommendationDecision`：

```python
class RecommendationDecision(SQLModel, table=True):
    __tablename__ = "recommendation_decisions"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int
    candidate_item_id: str
    final_score: float
    rank: int
    explanation: str
    explanation_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    action_hint: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 5.3 推荐解释结构

每条推荐必须输出：

```json
{
  "why_recommended": "与当前 OMKA 记忆系统升级目标高度相关",
  "matched_memories": ["用户当前重点关注：三大记忆", "项目：Personal Knowledge Assistant"],
  "matched_interests": ["AI Agent", "Personal Knowledge Management"],
  "freshness": "最近 3 天更新",
  "source_reason": "来自用户订阅的 GitHub 搜索源 RAG Agent",
  "suggested_action": "建议加入候选知识，稍后用于记忆系统设计参考"
}
```

### 5.4 反馈闭环

当前状态：

```text
confirm -> KnowledgeItem
ignore -> status=ignored
dislike -> status=disliked
read_later -> status=read_later
```

升级后：

| 用户行为 | 反馈含义 | 系统动作 |
|---|---|---|
| confirm | 强正反馈 | 提升匹配记忆、兴趣、来源权重 |
| read_later | 弱正反馈 | 维持推荐方向，降低即时推送频率 |
| ignore | 中性或时机不对 | 降低短期同类推送 |
| dislike | 强负反馈 | 记录负向偏好，降低相似内容 |
| ask why | 解释需求 | 增强推荐解释展示 |
| more like this | 强化方向 | 新增或更新偏好记忆 |

飞书交互建议：

```text
推荐消息：
1. LangGraph Memory Store
原因：与你的“个人知识助手记忆系统”目标相关，且匹配 AI Agent / RAG 兴趣。

[入库] [稍后读] [不感兴趣] [为什么推荐] [更多类似]
```

如果飞书按钮交互暂不做，先用命令替代：

```text
/omka save candidate:xxx
/omka later candidate:xxx
/omka dislike candidate:xxx
/omka why candidate:xxx
/omka more-like candidate:xxx
```

### 5.5 API 建议

```http
POST /recommendations/run
GET  /recommendations/latest
GET  /recommendations/{candidate_id}/explain
POST /recommendations/{candidate_id}/feedback
GET  /recommendations/profile-impact
```

### 5.6 验收标准

1. 每条推荐都能解释“为什么推荐给我”。
2. 推荐解释能引用用户记忆、项目记忆、兴趣、来源和时效。
3. 用户反馈会更新记忆或偏好权重。
4. 飞书中可以完成推荐操作闭环。
5. Digest 页面和飞书推送展示同一套解释结构。

---

## 6. 模块三：主动推送升级

### 6.1 目标

当前推送偏“任务执行结果”。升级后应变成“个人知识助理主动提醒”。

主动推送分四类：

| 推送类型 | 触发条件 | 示例 |
|---|---|---|
| 每日 Digest | 定时任务完成 | 今天有 6 条与你的记忆系统目标相关 |
| 高价值即时推送 | 分数超过阈值、强匹配当前目标 | 发现一个 LangGraph memory 新实现 |
| 待办/回访推送 | read_later 到期、候选长期未处理 | 你上周标记的多模态资产方案还未入库 |
| 系统异常推送 | 抓取失败、LLM 失败、飞书失败 | GitHub token 可能失效 |

### 6.2 新增数据模型

建议新增 `PushPolicy`：

```python
class PushPolicy(SQLModel, table=True):
    __tablename__ = "push_policies"

    id: str = Field(primary_key=True)
    name: str
    enabled: bool = True
    channel: str = "feishu"
    trigger_type: str  # daily / high_score / reminder / system_alert
    threshold: float | None = None
    quiet_hours_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    max_per_day: int = 5
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
```

建议新增 `PushEvent`：

```python
class PushEvent(SQLModel, table=True):
    __tablename__ = "push_events"

    id: int | None = Field(default=None, primary_key=True)
    policy_id: str
    channel: str
    target_id: str
    title: str
    content: str
    status: str = "pending"  # pending / sent / failed / skipped
    reason: str | None = None
    related_candidate_id: str | None = None
    related_memory_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: datetime | None = None
    response_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
```

### 6.3 推送策略

P0 建议只做四条策略：

1. daily_digest：每天固定时间推送 Top N。
2. high_score_candidate：推荐分数超过阈值，且匹配当前重点目标。
3. read_later_reminder：稍后读超过 3 天未处理。
4. system_alert：关键任务失败或配置异常。

推送前需要去重：

```text
同一 candidate 24 小时内不重复推送
同一 source 异常 1 小时内合并推送
每日主动推送不超过 max_per_day
安静时间不推普通内容，只推系统高危异常
```

### 6.4 飞书命令建议

```text
/omka push status
/omka push pause
/omka push resume
/omka push policy
/omka push set daily 09:00
/omka push set max 5
/omka push test
```

### 6.5 验收标准

1. 用户能在飞书中暂停/恢复推送。
2. 每条推送都有触发原因。
3. 系统异常能主动推送。
4. read_later 能形成回访提醒。
5. 推送日志可在 Web 和飞书中查询。

---

## 7. 模块四：飞书 Agent 对话执行通道升级

### 7.1 目标

飞书不是产品控制台本身，而是用户和 OMKA Agent 对话的渠道。用户在飞书中提出意图，Agent 识别任务、校验权限、必要时请求确认，然后调用系统服务执行操作。

| Agent 可执行范围 | 能力 |
|---|---|
| 信息源 | 新增、查看、启用、停用、删除、立即运行 |
| 候选知识 | 查看、入库、忽略、不感兴趣、稍后读、解释推荐 |
| 知识库 | 查询、查看、删除、打标签 |
| 记忆 | 查看、添加、修改、删除、确认候选记忆 |
| 配置 | 查看和修改非敏感配置，敏感配置走确认流程 |
| 任务 | 运行、查看状态、查看失败原因 |
| 推送 | 开关、频率、策略、测试 |
| 多模态资产 | 上传后的解析状态、入库、摘要、删除 |

### 7.2 Agent 权限模型

用户希望在飞书中和 Agent 对话，并让 Agent 代为执行系统任务。这里的核心不是让渠道承担控制台职责，而是让 Agent 按权限调用系统工具。建议分为三层权限：

| 权限 | 能力 |
|---|---|
| viewer | 查询状态、查看推荐、查看知识 |
| operator | 运行任务、处理候选、添加信息源、管理记忆 |
| admin | 修改配置、删除数据源、删除知识、修改推送策略 |

新增 `SystemAction` 审计表：

```python
class SystemAction(SQLModel, table=True):
    __tablename__ = "system_actions"

    id: int | None = Field(default=None, primary_key=True)
    action_type: str
    actor_channel: str
    actor_external_id: str
    permission_level: str
    target_type: str
    target_id: str | None = None
    request_text: str | None = None
    params_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "pending"  # pending / success / failed / denied / needs_confirm
    result_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: datetime | None = None
```

危险操作需要二次确认：

```text
/omka source delete xxx
系统：该操作会删除数据源 xxx。回复 /omka confirm action:123 继续。
```

危险操作包括：

1. 删除信息源。
2. 删除知识。
3. 删除记忆。
4. 修改 LLM/GitHub/Feishu secret。
5. 停止全部推送。
6. 批量清理数据。
7. 修改全局推荐权重、推送策略或 Agent 权限。
8. 导入、覆盖或批量更新用户画像和长期记忆。

危险操作无论来自自然语言还是斜杠命令，都不能直接执行，必须二次确认。

确认交互建议：

```text
用户：删除 browser agent 这个搜索源

Agent：这是一个高风险操作，会删除数据源 src_search_browser_agent，并影响后续抓取。
请回复：
/omka confirm action:123
继续执行；或回复：
/omka cancel action:123
取消操作。
```

确认规则：

1. `SystemAction.status` 先写为 `needs_confirm`。
2. 确认消息必须绑定 `action_id`、用户 open_id、会话 id 和过期时间。
3. 只有发起人或 admin 可以确认该操作。
4. 超过确认有效期后自动变为 `expired` 或 `cancelled`。
5. 执行后将结果写入 `SystemAction.result_json`。
6. Agent 回复中必须说明操作结果和影响范围。

### 7.3 飞书命令体系

建议采用“自然语言 Agent 优先 + 斜杠命令兜底”的混合模式。

飞书中的主要体验应该是自然语言对话，而不是要求用户记住大量命令。用户可以直接说：

```text
帮我新增一个 GitHub 搜索源，关键词是 memory agent，每次抓 10 条
把今天推荐的第二条加入知识库
以后少推前端框架，多推 RAG 和多模态知识资产
暂停今天的主动推送
查一下最近 GitHub 抓取有没有失败
```

Agent 负责把自然语言解析为结构化系统动作：

```json
{
  "action_type": "source.create",
  "params": {
    "source_type": "github",
    "mode": "search",
    "query": "memory agent",
    "limit": 10
  }
}
```

斜杠命令用于稳定兜底、调试和高级用户快捷操作。无论是自然语言还是斜杠命令，最终都应进入同一条执行链路：

```text
飞书消息
-> FeishuEventHandler
-> Agent / Intent Parser
-> 生成 SystemAction 草案
-> 权限校验
-> 风险等级判断
-> 如需确认，先返回确认请求
-> ActionService 执行真实系统操作
-> 写入审计日志
-> 返回执行结果到飞书
```

#### 基础命令

```text
/omka help
/omka status
/omka run
/omka latest
/omka search 关键词
```

#### 信息源

```text
/omka source list
/omka source add repo owner/repo
/omka source add search "personal knowledge assistant llm" limit 5
/omka source disable source_id
/omka source enable source_id
/omka source delete source_id
/omka source run source_id
```

#### 候选与知识

```text
/omka candidates
/omka save candidate_id
/omka ignore candidate_id
/omka dislike candidate_id
/omka later candidate_id
/omka why candidate_id
/omka knowledge search 关键词
/omka knowledge delete knowledge_id
```

#### 记忆

```text
/omka memory list
/omka memory profile
/omka memory candidates
/omka memory confirm memory_id
/omka memory reject memory_id
/omka memory add 内容
/omka memory update memory_id 内容
/omka memory delete memory_id
```

#### 配置

```text
/omka config list
/omka config get key
/omka config set key value
/omka config test github
/omka config test llm
/omka config test feishu
```

#### 推送

```text
/omka push status
/omka push pause
/omka push resume
/omka push set daily 09:00
/omka push test
```

#### 多模态

```text
/omka assets
/omka asset status asset_id
/omka asset summarize asset_id
/omka asset save asset_id
/omka asset delete asset_id
```

### 7.4 自然语言控制

命令之外，Agent 应支持自然语言：

```text
“帮我新增一个 GitHub 搜索源，关键词是 memory agent，限制 10 条”
“把今天推荐的第一条加入知识库”
“以后少推前端 UI 框架，多推 RAG 和多模态知识资产”
“把飞书推送改成每天上午 10 点”
```

实现方式：

```text
Feishu message
-> CommandRouter 判断是否显式命令
-> 如果不是命令，交给 Agent Intent Parser
-> 生成 SystemAction 草案
-> 权限校验
-> 需要确认则返回确认消息
-> 执行 Action Service
-> 写审计日志
-> 返回结果
```

### 7.5 验收标准

1. 飞书中能完成信息源增删改查。
2. 飞书中能处理候选知识。
3. 飞书中能管理用户记忆和候选记忆。
4. 飞书中能运行任务、查看任务状态和失败原因。
5. 飞书中能修改推送策略。
6. 高危操作有权限校验和二次确认。
7. 所有 Agent 操作都有 `SystemAction` 审计记录。

---

## 8. 模块五：多模态知识资产升级

### 8.1 目标

把知识资产从“GitHub 文本条目”扩展为统一资产系统，支持：

| 类型 | P0 支持 | P1/P2 支持 |
|---|---|---|
| 图片 | JPG、PNG、截图 OCR/视觉摘要 | 图像问答、区域标注 |
| PDF | 文本提取、摘要 | 版面理解、表格提取 |
| Markdown/Text | 直接入库 | 结构化实体关系 |
| Word/PPT | 文件存储、异步解析 | 完整内容抽取 |
| CSV/XLSX | 文件存储、摘要 | 表格问答、指标分析 |
| 网页 | URL 快照、正文抽取 | 定时监控 |
| 音视频 | 暂不做 | 转写、摘要 |

### 8.2 新增数据模型

建议新增 `KnowledgeAsset`：

```python
class KnowledgeAsset(SQLModel, table=True):
    __tablename__ = "knowledge_assets"

    id: str = Field(primary_key=True)
    asset_type: str  # image / pdf / doc / sheet / ppt / webpage / text
    title: str
    source_type: str  # upload / feishu / url / github / manual
    source_ref: str | None = None
    file_path: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    content_hash: str
    status: str = "uploaded"  # uploaded / processing / processed / failed / archived
    extracted_text: str | None = None
    summary: str | None = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

建议新增 `AssetProcessingRun`：

```python
class AssetProcessingRun(SQLModel, table=True):
    __tablename__ = "asset_processing_runs"

    id: int | None = Field(default=None, primary_key=True)
    asset_id: str
    processor: str  # ocr / pdf_text / vision_summary / document_parser
    status: str = "running"
    output_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    error_message: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
```

### 8.3 存储目录

建议：

```text
data/assets/
  images/
  pdf/
  documents/
  sheets/
  slides/
  webpage/
  derived/
    thumbnails/
    extracted_text/
    previews/
```

### 8.4 多模态处理流程

P0 流程：

```text
上传/接收文件
-> 保存 KnowledgeAsset
-> 计算 content_hash 去重
-> 进入 processing
-> 按 mime_type 选择处理器
-> 抽取文本/生成摘要
-> 生成 CandidateItem 或 KnowledgeItem
-> 用户确认入库
```

图片 P0：

1. 保存原图。
2. 生成缩略图。
3. 调用视觉模型或 OCR 生成描述和文字。
4. 生成 asset summary。
5. 可作为候选知识推送给用户确认。

PDF P0：

1. 提取文本。
2. 按页或章节切块。
3. 生成摘要。
4. 进入知识候选池。

飞书文件接入 P1：

1. 监听文件消息。
2. 下载文件到 `data/assets`。
3. 建立 KnowledgeAsset。
4. 返回“已接收，正在解析”。
5. 解析后推送摘要和入库按钮/命令。

### 8.5 API 建议

```http
GET    /assets
POST   /assets/upload
GET    /assets/{id}
DELETE /assets/{id}
POST   /assets/{id}/process
POST   /assets/{id}/save-to-knowledge
GET    /assets/{id}/runs
```

### 8.6 飞书命令建议

```text
/omka assets
/omka asset status asset_id
/omka asset summarize asset_id
/omka asset save asset_id
/omka asset delete asset_id
```

自然语言：

```text
“总结我刚上传的这张图”
“把这个 PDF 变成知识条目”
“从这份文档里提取和 OMKA 记忆系统有关的内容”
```

### 8.7 验收标准

1. 可以上传图片和 PDF。
2. 系统能保存资产、去重、记录处理状态。
3. 图片/PDF 能产生摘要和候选知识。
4. 用户能在飞书中查看资产状态并确认入库。
5. 资产能被 Agent 检索和引用。

---

## 9. 实施阶段规划

### Phase 0：基础治理与编码清理

目标：先让后续升级建立在干净基础上。

任务：

1. 修复中文文案、prompt、README、前端页面乱码。
2. 梳理 FastAPI route 中 raw dict 请求，补 Pydantic model。
3. 修复 cleaner 全量 RawItem 读取问题，改为 SQL 层过滤未 normalized。
4. 将 `routes_digest.py` 中直接 pipeline 调用下沉到 service。
5. 为新增表准备迁移策略，避免 SQLite 自动建表不可控。

验收：

1. `python -m py_compile omka/app/main.py` 通过。
2. `npx tsc -b` 通过。
3. 主要飞书回复和 Agent prompt 无乱码。

优先级：P0  
建议耗时：1-2 天。

### Phase 1：统一记忆内核

目标：完成三大记忆的基础模型和服务。

任务：

1. 新增 `MemoryItem`、`MemoryEvent`。
2. 新增 `MemoryService`。
3. 将 interests、projects、identity.md 导入用户记忆。
4. ContextBuilder 接入 active memory。
5. 对话结束后抽取候选记忆。
6. 新增记忆 API。
7. 飞书支持 memory list/add/confirm/reject/delete。

验收：

1. 飞书可查看用户记忆。
2. Agent 回答能使用用户记忆。
3. 对话能生成候选记忆。
4. 用户确认后候选记忆变 active。

优先级：P0  
建议耗时：4-6 天。

### Phase 2：推荐解释与反馈学习

目标：让推荐结果可解释，并能被反馈修正。

任务：

1. 新增 `RecommendationRun`、`RecommendationDecision`。
2. 抽出 `RecommendationService`，替代直接 `rank_candidates()`。
3. 推荐解释结构化。
4. 反馈写入 MemoryItem 或更新偏好权重。
5. Digest 和飞书使用同一推荐解释。
6. 新增 `/recommendations/{id}/explain`。
7. 飞书支持 why、more-like、dislike、later。

验收：

1. 每条推荐都有 explanation_json。
2. 飞书可询问“为什么推荐”。
3. dislike 后类似内容分数下降。
4. confirm 后相关兴趣/项目/记忆权重上升。

优先级：P0  
建议耗时：4-5 天。

### Phase 3：飞书 Agent 任务执行通道

目标：飞书成为对话入口，Agent 成为可审计的系统任务执行器。

任务：

1. 新增 `SystemAction` 审计表。
2. 新增 `ActionService` 封装系统操作。
3. 扩展 CommandRouter。
4. 支持 source、candidate、knowledge、memory、config、push、job 命令。
5. 增加权限模型：viewer/operator/admin。
6. 高危操作二次确认。
7. 自然语言意图转 action draft。

验收：

1. 飞书能新增 GitHub repo/search 数据源。
2. 飞书能修改非敏感配置。
3. 飞书能运行任务并查看状态。
4. 飞书能处理候选知识和记忆。
5. 危险操作有确认和审计。

优先级：P0  
建议耗时：5-8 天。

### Phase 4：主动推送策略

目标：把推送从通知升级为主动助理。

任务：

1. 新增 `PushPolicy`、`PushEvent`。
2. 新增 `PushService`。
3. 支持 daily、high_score、read_later、system_alert 四类策略。
4. 推送去重、安静时间、每日上限。
5. 飞书 push status/pause/resume/set/test。
6. 推送内容引用推荐解释。

验收：

1. 每日 Digest 正常推送。
2. 高价值候选可触发即时推送。
3. read_later 到期提醒。
4. 系统异常推送。
5. 飞书可控制推送策略。

优先级：P1  
建议耗时：3-5 天。

### Phase 5：多模态资产 P0

目标：支持图片、PDF 作为知识资产进入系统。

任务：

1. 新增 `KnowledgeAsset`、`AssetProcessingRun`。
2. 新增 `AssetService`。
3. 实现本地文件上传 API。
4. 图片保存、缩略图、OCR/视觉摘要。
5. PDF 文本提取和摘要。
6. 资产生成 CandidateItem。
7. 飞书查询资产状态并确认入库。

验收：

1. 图片和 PDF 能上传。
2. 资产能去重和记录处理状态。
3. 解析结果能生成摘要。
4. 用户能将资产保存为 KnowledgeItem。
5. Agent 能检索资产摘要。

优先级：P1  
建议耗时：5-8 天。

### Phase 6：Web 管理页面补齐

目标：Web UI 作为可视化管理台。

任务：

1. Memory 页面。
2. Recommendation explanation 页面。
3. Push policy 页面。
4. Feishu control/status 页面。
5. Assets 页面。
6. 修复前端乱码。
7. 前端 API client 改为支持 Vite proxy 或环境变量。

验收：

1. Web 可查看和管理记忆。
2. Web 可查看推荐解释。
3. Web 可查看推送日志。
4. Web 可查看资产处理状态。
5. 前端 build/typecheck 通过。

优先级：P2  
建议耗时：4-7 天。

---

## 10. 推荐开发顺序

建议不要先做多模态，也不要先扩更多外部数据源。最优顺序是：

```text
1. 编码和文案治理
2. 统一记忆内核
3. 推荐解释与反馈学习
4. 飞书 Agent 任务执行通道
5. 主动推送
6. 多模态资产 P0
7. Web 管理页面补齐
```

原因：

1. 记忆是推荐、推送和 Agent 控制的底座。
2. 推荐解释依赖记忆。
3. 飞书 Agent 执行系统任务依赖 ActionService 和权限审计。
4. 主动推送依赖推荐解释和用户记忆。
5. 多模态资产进入系统后，也需要走同一套记忆、推荐和入库流程。

---

## 11. 风险与控制

| 风险 | 处理方式 |
|---|---|
| Agent 拥有全系统权限后误操作 | ActionService + 权限模型 + 二次确认 + SystemAction 审计 |
| 记忆污染 | 候选记忆机制，身份/偏好类记忆默认需确认 |
| 推送打扰用户 | 安静时间、每日上限、push pause、负反馈学习 |
| 多模态处理成本高 | P0 只做图片/PDF，异步处理，失败可重试 |
| prompt/文案乱码影响质量 | Phase 0 优先处理 |
| SQLite 表结构继续膨胀 | 新增 service 层，后续预留迁移到 Postgres 的边界 |
| 飞书自然语言控制不稳定 | 明确命令优先，自然语言先生成 action draft，不直接执行高危动作 |

---

## 12. 关键验收清单

### 三大记忆

- [ ] 用户记忆可查看、添加、编辑、删除。
- [ ] 对话可生成候选记忆。
- [ ] 系统异常可沉淀为系统记忆。
- [ ] Agent 上下文包含三类记忆。
- [ ] 记忆有确认、拒绝、归档和事件日志。

### 推荐与解释

- [ ] 推荐解释结构化保存。
- [ ] 飞书和 Web 都能查看推荐原因。
- [ ] 用户反馈能影响后续推荐。
- [ ] 推荐能引用记忆和项目目标。

### 主动推送

- [ ] 每日 Digest 推送可配置。
- [ ] 高价值候选可即时推送。
- [ ] read_later 可回访提醒。
- [ ] 系统异常可主动告警。
- [ ] 飞书可暂停/恢复/调整推送。

### 飞书 Agent 任务执行

- [ ] 用户可通过飞书对话让 Agent 管理信息源。
- [ ] 用户可通过飞书对话让 Agent 处理候选知识。
- [ ] 用户可通过飞书对话让 Agent 管理记忆。
- [ ] 用户可通过飞书对话让 Agent 运行任务和查看状态。
- [ ] 用户可通过飞书对话让 Agent 修改配置。
- [ ] 高危操作有二次确认。
- [ ] 所有操作有审计日志。

### 多模态知识资产

- [ ] 图片可上传、保存、摘要。
- [ ] PDF 可上传、提取文本、摘要。
- [ ] 资产可生成候选知识。
- [ ] 资产可被确认入库。
- [ ] 飞书可查询资产状态。

---

## 13. 升级后的整体目标进度评估

参考你前面图片里的 12 项整体目标，当前项目大约是 35% 完成度。完成本次升级后，预计整体目标进度如下：

| 目标能力 | 当前估计 | 本次升级后估计 |
|---|---:|---:|
| 多源异构知识接入能力 | 25% | 40% |
| 个体化画像与长期记忆能力 | 20% | 70% |
| 多渠道统一交互能力 | 30% | 65% |
| 主动式任务调度与持续推荐能力 | 35% | 70% |
| 候选知识池与确认式入库机制 | 55% | 75% |
| 知识生命周期治理能力 | 30% | 60% |
| 冷启动分析与初始画像生成能力 | 15% | 45% |
| 多模态知识资产管理能力 | 5% | 45% |
| 知识图谱与关系建模能力 | 10% | 25% |
| 可解释推荐与个性化演进能力 | 45% | 75% |
| 统一记忆内核与 Agent 协同能力 | 25% | 70% |
| 用户可控与隐私安全能力 | 25% | 65% |

综合评估：

```text
当前整体目标完成度：约 35%
完成本次升级后：约 62% - 68%
```

其中提升最大的部分是：

1. 个人长期记忆。
2. 推荐解释与反馈闭环。
3. 飞书 Agent 对话执行通道。
4. 主动推送。
5. 多模态资产 P0。

仍然不会完全完成的部分：

1. 多源异构接入还需要 RSS、网页、文档平台、即时通讯、邮件、会议纪要等更多 connector。
2. 知识图谱只会有字段和初步抽取，距离完整图谱还有距离。
3. 多模态 P0 只覆盖图片/PDF，音视频、复杂 PPT/表格理解还需要后续阶段。
4. 多 Agent 协同可以先用 ActionService 和单 Agent 实现，完整多 Agent 体系建议放到下一阶段。

---

## 14. 最小可交付版本定义

如果希望快速形成一个可用版本，本次升级的最小闭环应包含：

```text
MemoryItem + MemoryService
RecommendationService + explanation_json
Feishu ActionService + 权限审计
PushPolicy + PushEvent
KnowledgeAsset 图片/PDF P0
```

最小闭环用户故事：

```text
用户在飞书说：“我最近重点做 OMKA 记忆系统。”
系统抽取候选用户记忆并请求确认。
用户确认后，系统把它作为长期用户记忆。
每日 GitHub 抓取后，推荐服务发现 LangGraph memory 相关内容。
系统推送到飞书，并解释推荐原因：匹配用户当前重点、项目目标和 AI Agent 兴趣。
用户在飞书回复“入库”。
系统保存为 KnowledgeItem，并更新偏好权重。
用户上传一张架构图。
系统保存为 KnowledgeAsset，生成图像摘要，并询问是否加入知识库。
```

做到这个闭环，OMKA 就会从“知识 Digest 工具”明显升级为“个人知识助手”。
