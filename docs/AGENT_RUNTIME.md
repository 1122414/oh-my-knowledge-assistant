# OMKA Agent Runtime

## 定位

OMKA 现在是一个“工作流 + Agent”的混合系统：

- 每日采集、清洗、去重、排序和推送仍采用确定性 Pipeline，便于重跑与审计。
- 用户交互、知识检索、记忆、推荐解释和受控操作由统一 Agent Runtime 驱动。
- Web、飞书自然语言对话和主动 Goal 复用同一套 Runtime 与工具注册表。

这种边界保留了知识流水线的稳定性，同时让需要理解目标、选择工具和多步执行的部分具备 Agent 能力。

## 执行模型

```text
User message
    │
    ▼
TaskInterpreter → TaskBrief（目标、来源、风险、成功标准）
    │                         │
    │ 模糊/高风险且对象不明   └─→ Clarification
    ▼
ContextBuilder
    │
    ├─ 对话、知识、候选、记忆
    └─ UserProfileSnapshot（证据、置信度、确认状态）
    ▼
Planner ── final ───────────────────────────────┐
    │ tool                                      │
    ▼                                           │
ToolRegistry → 权限检查 → 持久确认 → Handler     │
    │                                           │
    └─ Observation ──> Planner（最多 1–8 步）    │
                                                ▼
                                      AgentResponse
                                                │
                           ┌────────────────────┼──────────────┐
                           ▼                    ▼              ▼
                       AgentStep          候选记忆提取      Evaluation
                                                                  │
                                                                  ▼
                                                      Agent Harness
                                           黄金场景 + 近期运行质量基线
```

核心实现：

- `omka/app/agents/runtime.py`：有界规划/工具循环和运行持久化。
- `omka/app/agents/task_understanding.py`：结构化任务契约及可替换的 `TaskInterpreter` 接口。
- `omka/app/agents/tools.py`：类型化工具、风险等级、权限与持久确认。
- `omka/app/agents/tool_adapters.py`：知识、候选、来源、记忆和推荐工具。
- `omka/app/agents/context_builder.py`：用户域检索与引用上下文。
- `omka/app/agents/memory_extractor.py`：保守提取明确、长期有效的用户事实。
- `omka/app/agents/evaluation.py`：对已记录运行进行确定性检查。
- `omka/app/agents/harness.py`：任务理解黄金场景与近期运行质量聚合。
- `omka/app/services/user_profile_service.py`：带证据、置信度和冲突信号的用户画像快照。
- `omka/app/services/agent_goal_service.py`：主动目标的持久化与 Cron 调度。

## 安全边界

工具按风险分为三类：

| 风险 | 示例 | 默认策略 |
|---|---|---|
| `read` | 搜索知识、查询状态 | 通过读取权限后直接执行 |
| `write` | 收藏候选、添加记忆 | 要求写权限；工具可声明需要确认 |
| `destructive` | 忽略、删除或覆盖 | 要求破坏性权限并强制确认 |

待确认操作写入 `SystemAction`，记录发起人、会话、工具名和参数。确认时再次校验操作者，服务重启后仍可恢复，避免把高风险状态只放在进程内存中。

主动 Goal 默认只能使用只读工具，并且每次运行限制最大步数。需要扩大工具范围时，应在创建 Goal 时显式声明。

## 数据隔离与可追溯性

- 每次规划前先生成 `TaskBrief`，写入 `AgentRun.used_context_json` 和
  `understanding.task` 轨迹；任务目标、风险和成功标准可在 Web 中检查。
- `MemoryItem.owner_external_id` 隔离不同用户；会话记忆可再由 `conversation_id` 限定。
- 检索排除过期、拒绝和归档记忆，并记录 `last_used_at`。
- 工具结果和回答使用 `[knowledge:ID]`、`[candidate:ID]`、`[memory:ID]` 引用。
- 每次运行写入 `AgentRun`，每个决策与工具观察写入 `AgentStep`。
- `/agent/runs/{id}/replay` 使用最新知识上下文重新执行，而不是伪造旧结果。
- `/agent/runs/{id}/evaluation` 检查失败工具、拒绝操作、未知工具、步骤完整性和引用情况。

## 记忆与推荐闭环

Runtime 只把明确表达、可长期复用的偏好或事实写为候选记忆，避免把一次性命令误当画像。用户确认后记忆才进入稳定上下文。

收藏、忽略和显式推荐反馈会生成用户域结构化记忆。推荐服务读取这些反馈，对匹配候选做个性化调整，并在解释中显示反馈影响。

`UserProfileSnapshot` 不直接“总结用户是什么样的人”，而是合并显式配置与
`MemoryItem` 证据。每个画像切面都有来源、置信度和 `verified / inferred /
review` 状态；候选画像可确认、拒绝，已有记忆可修改内容和置信度。

## Harness 质量门

`/agent/harness/summary` 同时检查两类质量：

1. 固定黄金场景：意图、所需上下文、输出形态、风险和澄清策略。
2. 近期真实运行：完成率、任务契约覆盖、轨迹完整度、引用覆盖、降级率和
   P50/P95 耗时。

新增意图规则、工具或 Planner 适配器时，应先扩充黄金场景；真实运行指标用于
发现模型连接、引用和恢复策略的回归。旧运行不会被伪装成新架构产生的样本，
因此升级初期的 Harness 分数会保守，随着新运行积累逐步反映当前能力。

## 扩展工具

1. 在 `tool_adapters.py` 定义 Pydantic 参数模型。
2. 实现接收参数和 `ToolContext` 的 handler。
3. 使用稳定、命名空间化的名称注册 `AgentTool`。
4. 明确 `risk`、`required_permission` 和 `requires_confirmation`。
5. 为成功、拒绝、持久确认和错误路径添加隔离数据库测试。

不要在规划器提示词中直接拼接密钥、完整配置或无界原文；工具输出也应只返回完成下一步决策所需的数据。

## Web 运维入口

`/agent` 提供：

- 即时任务输入和最新回答；
- 输入阶段实时预览任务契约与高风险澄清；
- Harness 健康度与回归/运行指标；
- 主动目标创建、暂停、恢复、运行与删除；
- 运行列表、步骤展开、耗时和工具调用数；
- 确定性质量评分与运行回放。

`/memory` 提供画像置信度、证据状态和直接修正入口。Agent 中心用于观察和控制
执行，不替代知识、来源、推送和设置等专用工作区。
