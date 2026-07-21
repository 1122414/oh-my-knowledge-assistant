import { useCallback, useEffect, useMemo, useState } from "react"
import {
  Activity,
  AlertCircle,
  BookOpen,
  Bot,
  Brain,
  Check,
  ChevronDown,
  ChevronRight,
  CirclePause,
  Clock3,
  Database,
  FileSearch,
  Gauge,
  ListFilter,
  Loader2,
  MessageSquareText,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  Trash2,
  UserRound,
  Wrench,
  X,
} from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import {
  agentApi,
  type AgentEvaluation,
  type AgentGoal,
  type AgentHarnessSummary,
  type AgentRunDetail,
  type AgentRunSummary,
  type AgentTaskBrief,
} from "@/api/agent"
import { cn } from "@/lib/cn"

const WEB_OWNER = "web-console"
const WEB_CONVERSATION = "web-agent-console"
const TERMINAL_RUN_STATUSES = new Set([
  "success",
  "completed",
  "degraded",
  "needs_confirm",
  "needs_clarification",
  "failed",
  "error",
  "step_limit",
])

const proactiveTools = [
  "system.status",
  "knowledge.search",
  "candidate.list",
  "source.list",
  "memory.search",
  "recommendation.explain",
]

export function AgentPage() {
  const [goals, setGoals] = useState<AgentGoal[]>([])
  const [runs, setRuns] = useState<AgentRunSummary[]>([])
  const [selectedRun, setSelectedRun] = useState<AgentRunDetail | null>(null)
  const [evaluation, setEvaluation] = useState<AgentEvaluation | null>(null)
  const [harness, setHarness] = useState<AgentHarnessSummary | null>(null)
  const [taskBrief, setTaskBrief] = useState<AgentTaskBrief | null>(null)
  const [understanding, setUnderstanding] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState("")
  const [answer, setAnswer] = useState("")
  const [activeRunId, setActiveRunId] = useState<number | null>(null)
  const [showGoalForm, setShowGoalForm] = useState(false)
  const [objective, setObjective] = useState("")
  const [scheduleCron, setScheduleCron] = useState("")
  const [maxSteps, setMaxSteps] = useState(4)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [goalData, runData, harnessData] = await Promise.all([
        agentApi.getGoals(WEB_OWNER),
        agentApi.getRuns(30),
        agentApi.getHarnessSummary(50),
      ])
      setGoals(goalData)
      setRuns(runData)
      setHarness(harnessData)
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法加载 Agent 数据")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    const prompt = message.trim()
    if (!prompt) {
      setTaskBrief(null)
      setUnderstanding(false)
      return
    }
    let cancelled = false
    setUnderstanding(true)
    const timer = window.setTimeout(() => {
      void agentApi.understand(prompt)
        .then((brief) => {
          if (!cancelled) setTaskBrief(brief)
        })
        .catch(() => {
          if (!cancelled) setTaskBrief(null)
        })
        .finally(() => {
          if (!cancelled) setUnderstanding(false)
        })
    }, 320)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [message])

  useEffect(() => {
    if (activeRunId === null) return

    let cancelled = false
    let timer: number | undefined

    const pollRun = async () => {
      try {
        const detail = await agentApi.getRun(activeRunId)
        if (cancelled) return
        setSelectedRun(detail)
        setRuns((current) => {
          const summary = { ...detail }
          const existing = current.findIndex((run) => run.id === detail.id)
          if (existing === -1) return [summary, ...current]
          return current.map((run) => run.id === detail.id ? summary : run)
        })

        if (TERMINAL_RUN_STATUSES.has(detail.status)) {
          setAnswer(detail.answer || detail.answer_preview)
          setBusyKey(null)
          setActiveRunId(null)
          try {
            setEvaluation(await agentApi.evaluateRun(detail.id))
          } catch {
            setEvaluation(null)
          }
          await refresh()
          return
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "无法读取 Agent 实时轨迹")
          setBusyKey(null)
          setActiveRunId(null)
        }
        return
      }

      timer = window.setTimeout(() => {
        void pollRun()
      }, 650)
    }

    void pollRun()
    return () => {
      cancelled = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [activeRunId, refresh])

  const activeGoals = useMemo(
    () => goals.filter((goal) => goal.status === "active" || goal.status === "running").length,
    [goals]
  )
  const successfulRuns = useMemo(
    () => runs.filter((run) => ["success", "completed"].includes(run.status)).length,
    [runs]
  )

  const runPrompt = async () => {
    const prompt = message.trim()
    if (!prompt) return
    setBusyKey("prompt")
    setError(null)
    setAnswer("")
    setEvaluation(null)
    try {
      const result = await agentApi.startRun(
        prompt,
        WEB_CONVERSATION,
        WEB_OWNER
      )
      setMessage("")
      setTaskBrief(null)
      setActiveRunId(result.run_id)
      setSelectedRun(await agentApi.getRun(result.run_id))
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent 运行失败")
      setBusyKey(null)
    }
  }

  const createGoal = async () => {
    const goalObjective = objective.trim()
    if (!goalObjective) return
    setBusyKey("create-goal")
    setError(null)
    try {
      await agentApi.createGoal({
        owner_external_id: WEB_OWNER,
        conversation_id: WEB_CONVERSATION,
        objective: goalObjective,
        schedule_cron: scheduleCron.trim() || null,
        allowed_tools: proactiveTools,
        max_steps: maxSteps,
      })
      setObjective("")
      setScheduleCron("")
      setMaxSteps(4)
      setShowGoalForm(false)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "目标创建失败")
    } finally {
      setBusyKey(null)
    }
  }

  const runGoal = async (goal: AgentGoal) => {
    setBusyKey(`run-${goal.id}`)
    setError(null)
    setEvaluation(null)
    try {
      const updated = await agentApi.runGoal(goal.id)
      setGoals((current) => current.map((item) => item.id === updated.id ? updated : item))
      if (updated.last_run_id) {
        setAnswer("")
        setActiveRunId(updated.last_run_id)
        setSelectedRun(await agentApi.getRun(updated.last_run_id))
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "目标运行失败")
      setBusyKey(null)
    }
  }

  const toggleGoal = async (goal: AgentGoal) => {
    const status = goal.status === "paused" ? "active" : "paused"
    setBusyKey(`status-${goal.id}`)
    setError(null)
    try {
      await agentApi.updateGoalStatus(goal.id, status)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "目标状态更新失败")
    } finally {
      setBusyKey(null)
    }
  }

  const deleteGoal = async (goal: AgentGoal) => {
    if (!window.confirm(`删除目标“${goal.objective}”？`)) return
    setBusyKey(`delete-${goal.id}`)
    setError(null)
    try {
      await agentApi.deleteGoal(goal.id)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "目标删除失败")
    } finally {
      setBusyKey(null)
    }
  }

  const openRun = async (runId: number) => {
    setBusyKey(`detail-${runId}`)
    setError(null)
    try {
      const [detail, score] = await Promise.all([
        agentApi.getRun(runId),
        TERMINAL_RUN_STATUSES.has(
          runs.find((run) => run.id === runId)?.status || ""
        )
          ? agentApi.evaluateRun(runId)
          : Promise.resolve(null),
      ])
      setSelectedRun(detail)
      setEvaluation(score)
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行详情加载失败")
    } finally {
      setBusyKey(null)
    }
  }

  const replayRun = async (runId: number) => {
    setBusyKey("replay")
    setError(null)
    setEvaluation(null)
    try {
      const result = await agentApi.replayRun(runId)
      setAnswer("")
      setActiveRunId(result.run_id)
      setSelectedRun(await agentApi.getRun(result.run_id))
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "回放失败")
      setBusyKey(null)
    }
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-7 w-7 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        eyebrow="Agent Runtime"
        title="让知识真正行动。"
        description="同一套 Runtime 驱动网页与飞书对话；每一步工具调用都可追踪、可回放，并受到权限与确认策略约束。"
      >
        <button className="secondary-button" onClick={() => void refresh()}>
          <RotateCcw className="h-4 w-4" />
          刷新
        </button>
        <button className="primary-button" onClick={() => setShowGoalForm(true)}>
          <Plus className="h-4 w-4" />
          新建目标
        </button>
      </PageHeader>

      {error && (
        <div className="alert-panel mb-6 border-destructive/15 bg-destructive/[0.055] text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
          <button className="ml-auto" onClick={() => setError(null)} aria-label="关闭错误提示">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <section className="apple-surface relative overflow-hidden p-5 sm:p-8">
        <div className="pointer-events-none absolute right-[-5rem] top-[-7rem] h-64 w-64 rounded-full bg-primary/[0.08] blur-3xl" />
        <div className="relative grid gap-7 lg:grid-cols-[minmax(0,1.35fr)_minmax(260px,.65fr)] lg:items-end">
          <div>
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-foreground text-background shadow-sm">
              <Sparkles className="h-5 w-5" strokeWidth={1.7} />
            </div>
            <h2 className="max-w-xl text-2xl font-semibold tracking-[-0.04em] sm:text-3xl">
              给 Agent 一个任务，看见它如何思考与行动。
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              它会先检索你的知识、记忆与候选内容，仅在需要时调用工具；有风险的操作会暂停并等待确认。
            </p>
            <div className="mt-5 flex flex-col gap-2 sm:flex-row">
              <input
                className="field-control min-h-11 flex-1"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault()
                    void runPrompt()
                  }
                }}
                placeholder="例如：找出最值得今天阅读的三个项目，并说明原因"
                aria-label="Agent 任务"
              />
              <button
                className="primary-button min-h-11 justify-center"
                onClick={() => void runPrompt()}
                disabled={!message.trim() || busyKey === "prompt"}
              >
                {busyKey === "prompt" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                运行
              </button>
            </div>
            {(understanding || taskBrief) && (
              <TaskUnderstandingPreview
                brief={taskBrief}
                loading={understanding}
              />
            )}
          </div>

          <div className="grid grid-cols-3 gap-2 sm:gap-3">
            <Metric label="活跃目标" value={activeGoals} />
            <Metric label="运行总数" value={runs.length} />
            <Metric label="成功完成" value={successfulRuns} />
          </div>
        </div>
      </section>

      {answer && (
        <section className="apple-surface-subtle mt-5 p-5 sm:p-6">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-primary">
            <Bot className="h-4 w-4" />
            最新回答
          </div>
          <p className="mt-3 whitespace-pre-wrap text-[15px] leading-7">{answer}</p>
        </section>
      )}

      {harness && <HarnessPanel harness={harness} />}

      <div className="mt-6 grid min-w-0 gap-6 xl:grid-cols-[minmax(0,.9fr)_minmax(0,1.1fr)]">
        <section className="apple-surface min-w-0 p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="eyebrow">Proactive</p>
              <h2 className="mt-1 text-xl font-semibold tracking-[-0.03em]">长期目标</h2>
            </div>
            <span className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-muted-foreground">
              {goals.length} 个
            </span>
          </div>

          {showGoalForm && (
            <div className="mt-5 rounded-2xl border border-black/[0.06] bg-secondary/45 p-4">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="goal-objective">
                目标
              </label>
              <textarea
                id="goal-objective"
                className="field-control mt-2 min-h-24 resize-y"
                value={objective}
                onChange={(event) => setObjective(event.target.value)}
                placeholder="持续关注与我兴趣匹配的新知识，并给出简明建议"
              />
              <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_110px]">
                <div>
                  <label className="text-xs font-medium text-muted-foreground" htmlFor="goal-cron">
                    Cron（留空为手动）
                  </label>
                  <input
                    id="goal-cron"
                    className="field-control mt-2"
                    value={scheduleCron}
                    onChange={(event) => setScheduleCron(event.target.value)}
                    placeholder="0 9 * * *"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground" htmlFor="goal-steps">
                    最大步数
                  </label>
                  <select
                    id="goal-steps"
                    className="field-control mt-2"
                    value={maxSteps}
                    onChange={(event) => setMaxSteps(Number(event.target.value))}
                  >
                    {[2, 3, 4, 5, 6, 7, 8].map((step) => (
                      <option key={step} value={step}>{step}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <button className="secondary-button" onClick={() => setShowGoalForm(false)}>
                  取消
                </button>
                <button
                  className="primary-button"
                  onClick={() => void createGoal()}
                  disabled={!objective.trim() || busyKey === "create-goal"}
                >
                  {busyKey === "create-goal" && <Loader2 className="h-4 w-4 animate-spin" />}
                  保存目标
                </button>
              </div>
            </div>
          )}

          <div className="mt-5 space-y-3">
            {goals.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-black/10 px-5 py-12 text-center">
                <CirclePause className="mx-auto h-6 w-6 text-muted-foreground" strokeWidth={1.6} />
                <p className="mt-3 text-sm font-medium">还没有长期目标</p>
                <p className="mt-1 text-xs text-muted-foreground">目标可手动运行，也可按 Cron 自动执行。</p>
              </div>
            ) : goals.map((goal) => (
              <GoalCard
                key={goal.id}
                goal={goal}
                busyKey={busyKey}
                onRun={runGoal}
                onToggle={toggleGoal}
                onDelete={deleteGoal}
              />
            ))}
          </div>
        </section>

        <section className="apple-surface min-w-0 p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="eyebrow">Observability</p>
              <h2 className="mt-1 text-xl font-semibold tracking-[-0.03em]">运行轨迹</h2>
            </div>
            <Activity className="h-5 w-5 text-primary" strokeWidth={1.7} />
          </div>

          <div className="mt-5 divide-y divide-black/[0.055]">
            {runs.length === 0 ? (
              <div className="py-12 text-center text-sm text-muted-foreground">尚无 Agent 运行记录。</div>
            ) : runs.slice(0, 12).map((run) => (
              <button
                key={run.id}
                className="group flex w-full items-center gap-3 py-3.5 text-left"
                onClick={() => void openRun(run.id)}
              >
                <StatusMark status={run.status} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{run.user_message || "主动目标运行"}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    #{run.id} · {run.model || "runtime"} · {formatDuration(run.latency_ms)}
                  </p>
                </div>
                {busyKey === `detail-${run.id}` ? (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                )}
              </button>
            ))}
          </div>
        </section>
      </div>

      {selectedRun && (
        <RunInspector
          run={selectedRun}
          evaluation={evaluation}
          live={activeRunId === selectedRun.id}
          replaying={busyKey === "replay"}
          onReplay={replayRun}
          onClose={() => {
            setSelectedRun(null)
            setEvaluation(null)
          }}
        />
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-black/[0.05] bg-white/65 px-3 py-4 text-center shadow-sm">
      <p className="text-2xl font-semibold tracking-[-0.04em]">{value}</p>
      <p className="mt-1 text-[10px] font-medium text-muted-foreground">{label}</p>
    </div>
  )
}

function TaskUnderstandingPreview({
  brief,
  loading,
}: {
  brief: AgentTaskBrief | null
  loading: boolean
}) {
  if (loading && !brief) {
    return (
      <div className="mt-3 flex items-center gap-2 rounded-xl border border-black/[0.055] bg-white/55 px-3 py-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
        正在形成任务契约…
      </div>
    )
  }
  if (!brief) return null
  return (
    <div className={cn(
      "mt-3 rounded-2xl border p-3.5",
      brief.needs_clarification
        ? "border-warning/20 bg-warning/[0.065]"
        : "border-primary/15 bg-white/65"
    )}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-foreground">
          <Target className="h-3.5 w-3.5 text-primary" />
          我理解为：{brief.goal}
        </span>
        <TaskChip>{taskIntentLabel(brief.intent)}</TaskChip>
        <TaskChip>{Math.round(brief.confidence * 100)}% 置信</TaskChip>
        <TaskChip tone={brief.risk === "safe" ? "neutral" : "warning"}>
          {taskRiskLabel(brief.risk)}
        </TaskChip>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
        <span>将使用</span>
        {brief.required_context.map((source) => (
          <span key={source} className="rounded-md bg-secondary/85 px-1.5 py-0.5">
            {contextSourceLabel(source)}
          </span>
        ))}
        <span>· 交付 {outputShapeLabel(brief.expected_output)}</span>
      </div>
      {brief.needs_clarification && (
        <p className="mt-2 text-xs leading-5 text-warning">
          {brief.clarification_question} 你可以直接修改上面的任务表述。
        </p>
      )}
    </div>
  )
}

function TaskChip({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode
  tone?: "neutral" | "warning"
}) {
  return (
    <span className={cn(
      "rounded-full px-2 py-0.5 text-[9px] font-semibold",
      tone === "warning"
        ? "bg-warning/10 text-warning"
        : "bg-secondary text-muted-foreground"
    )}>
      {children}
    </span>
  )
}

function HarnessPanel({ harness }: { harness: AgentHarnessSummary }) {
  const score = Math.round(harness.health_score * 100)
  return (
    <section className="apple-surface mt-6 overflow-hidden">
      <div className="grid lg:grid-cols-[minmax(240px,.55fr)_minmax(0,1.45fr)]">
        <div className="border-b border-black/[0.055] p-5 sm:p-6 lg:border-b-0 lg:border-r">
          <div className="flex items-center gap-2 text-primary">
            <ShieldCheck className="h-4 w-4" />
            <p className="eyebrow">Agent Harness</p>
          </div>
          <div className="mt-4 flex items-end gap-2">
            <p className="text-4xl font-semibold tracking-[-0.06em]">{score}</p>
            <p className="pb-1 text-xs text-muted-foreground">/ 100 健康度</p>
          </div>
          <p className="mt-3 text-xs leading-5 text-muted-foreground">
            {harness.findings[0]}
          </p>
        </div>
        <div className="grid grid-cols-2 divide-x divide-y divide-black/[0.055] sm:grid-cols-3 sm:divide-y-0">
          <HarnessMetric
            label="理解回归"
            value={`${Math.round(harness.scenario_pass_rate * 100)}%`}
            detail={`${harness.scenario_count} 个黄金场景`}
          />
          <HarnessMetric
            label="完整完成"
            value={`${Math.round(harness.completion_rate * 100)}%`}
            detail={`${harness.sample_size} 次近期运行`}
          />
          <HarnessMetric
            label="轨迹覆盖"
            value={`${Math.round(harness.trace_coverage * 100)}%`}
            detail="理解 · 检索 · 规划 · 回答"
          />
          <HarnessMetric
            label="引用覆盖"
            value={`${Math.round(harness.grounding_rate * 100)}%`}
            detail="使用知识时可追溯"
          />
          <HarnessMetric
            label="P95 耗时"
            value={formatDuration(harness.p95_latency_ms)}
            detail="近期尾延迟"
          />
          <HarnessMetric
            label="降级比例"
            value={`${Math.round(harness.degraded_rate * 100)}%`}
            detail="失败与恢复质量"
          />
        </div>
      </div>
    </section>
  )
}

function HarnessMetric({
  label,
  value,
  detail,
}: {
  label: string
  value: string
  detail: string
}) {
  return (
    <div className="min-w-0 p-4 sm:p-5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-xl font-semibold tracking-[-0.04em]">{value}</p>
      <p className="mt-1 truncate text-[10px] text-muted-foreground">{detail}</p>
    </div>
  )
}

function GoalCard({
  goal,
  busyKey,
  onRun,
  onToggle,
  onDelete,
}: {
  goal: AgentGoal
  busyKey: string | null
  onRun: (goal: AgentGoal) => void
  onToggle: (goal: AgentGoal) => void
  onDelete: (goal: AgentGoal) => void
}) {
  const running = busyKey === `run-${goal.id}` || goal.status === "running"
  return (
    <article className="rounded-2xl border border-black/[0.06] bg-white/65 p-4 shadow-[0_1px_2px_rgba(0,0,0,.025)]">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary/[0.09] text-primary">
          <Bot className="h-4 w-4" strokeWidth={1.8} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium leading-5">{goal.objective}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <span className={cn(
              "rounded-full px-2 py-0.5 font-medium",
              goal.status === "failed" ? "bg-destructive/10 text-destructive" :
                goal.status === "paused" ? "bg-secondary text-muted-foreground" :
                  "bg-success/10 text-success"
            )}>
              {goalStatusLabel(goal.status)}
            </span>
            <span>{goal.schedule_cron ? `Cron ${goal.schedule_cron}` : "手动运行"}</span>
            <span>最多 {goal.max_steps} 步</span>
          </div>
          {goal.last_result_preview && (
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">
              {goal.last_result_preview}
            </p>
          )}
          {goal.last_error && <p className="mt-2 text-xs text-destructive">{goal.last_error}</p>}
        </div>
      </div>
      <div className="mt-3 flex justify-end gap-1.5">
        <button
          className="icon-button"
          onClick={() => onRun(goal)}
          disabled={running || goal.status === "paused"}
          aria-label="立即运行"
          title="立即运行"
        >
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        </button>
        <button
          className="icon-button"
          onClick={() => onToggle(goal)}
          disabled={busyKey === `status-${goal.id}`}
          aria-label={goal.status === "paused" ? "恢复目标" : "暂停目标"}
          title={goal.status === "paused" ? "恢复目标" : "暂停目标"}
        >
          {goal.status === "paused" ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
        </button>
        <button
          className="icon-button text-destructive"
          onClick={() => onDelete(goal)}
          disabled={busyKey === `delete-${goal.id}`}
          aria-label="删除目标"
          title="删除目标"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </article>
  )
}

function RunInspector({
  run,
  evaluation,
  live,
  replaying,
  onReplay,
  onClose,
}: {
  run: AgentRunDetail
  evaluation: AgentEvaluation | null
  live: boolean
  replaying: boolean
  onReplay: (runId: number) => void
  onClose: () => void
}) {
  const [expandedStep, setExpandedStep] = useState<number | null>(null)
  const latestStep = run.steps.length > 0
    ? run.steps[run.steps.length - 1]
    : null
  const taskBrief = taskBriefFromRun(run)

  useEffect(() => {
    if (
      latestStep &&
      (latestStep.status === "running" || latestStep.status === "failed")
    ) {
      setExpandedStep(latestStep.id)
    }
  }, [latestStep])

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/20 backdrop-blur-[2px]" role="dialog" aria-modal="true">
      <button className="absolute inset-0 cursor-default" onClick={onClose} aria-label="关闭运行详情" />
      <aside className="relative h-full w-full max-w-2xl overflow-y-auto border-l border-black/[0.06] bg-[#fbfbfd] p-5 shadow-2xl sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <p className="eyebrow">Run #{run.id}</p>
              <span className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold",
                live
                  ? "bg-primary/10 text-primary"
                  : ["failed", "error"].includes(run.status)
                    ? "bg-destructive/10 text-destructive"
                    : run.status === "degraded"
                      ? "bg-warning/10 text-warning"
                    : "bg-success/10 text-success"
              )}>
                {live && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
                {live ? "实时运行中" : runStatusLabel(run.status)}
              </span>
            </div>
            <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em]">运行详情</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{run.user_message}</p>
          </div>
          <button className="icon-button shrink-0" onClick={onClose} aria-label="关闭">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-6 grid grid-cols-3 gap-2">
          <InspectorMetric icon={Gauge} label="质量评分" value={evaluation ? `${Math.round(evaluation.score * 100)}` : live ? "…" : "—"} />
          <InspectorMetric icon={Wrench} label="工具调用" value={`${run.steps.filter((step) => step.step_type === "tool").length}`} />
          <InspectorMetric icon={Clock3} label={live ? "当前阶段" : "总耗时"} value={live ? `${run.steps.length}` : formatDuration(run.latency_ms)} />
        </div>

        {taskBrief && (
          <div className="mt-4 rounded-2xl border border-primary/15 bg-primary/[0.045] p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-primary">
              <Target className="h-4 w-4" />
              任务契约
            </div>
            <p className="mt-2 text-sm font-medium leading-6">{taskBrief.goal}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <TaskChip>{taskIntentLabel(taskBrief.intent)}</TaskChip>
              <TaskChip>{Math.round(taskBrief.confidence * 100)}% 置信</TaskChip>
              <TaskChip tone={taskBrief.risk === "safe" ? "neutral" : "warning"}>
                {taskRiskLabel(taskBrief.risk)}
              </TaskChip>
              {taskBrief.required_context.map((source) => (
                <TaskChip key={source}>{contextSourceLabel(source)}</TaskChip>
              ))}
            </div>
            <ul className="mt-3 space-y-1 text-[11px] leading-5 text-muted-foreground">
              {taskBrief.success_criteria.slice(0, 3).map((criterion) => (
                <li key={criterion}>· {criterion}</li>
              ))}
            </ul>
          </div>
        )}

        {latestStep && (
          <div className={cn(
            "mt-4 flex items-start gap-3 rounded-2xl border p-4",
            latestStep.status === "failed"
              ? "border-destructive/15 bg-destructive/[0.055]"
              : live
                ? "border-primary/15 bg-primary/[0.055]"
                : "border-black/[0.06] bg-white"
          )}>
            <StageGlyph step={latestStep} />
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                {live ? "当前正在进行" : "最后阶段"}
              </p>
              <p className="mt-1 text-sm font-medium">{stepTitle(latestStep)}</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                {stepSummary(latestStep)}
              </p>
            </div>
          </div>
        )}

        {evaluation && evaluation.findings.length > 0 && (
          <div className={cn(
            "mt-4 rounded-2xl border p-4 text-sm",
            evaluation.passed
              ? "border-success/15 bg-success/[0.055]"
              : "border-warning/20 bg-warning/[0.07]"
          )}>
            <p className="font-medium">{evaluation.passed ? "评估通过" : "需要关注"}</p>
            <ul className="mt-2 space-y-1 text-xs leading-5 text-muted-foreground">
              {evaluation.findings.map((finding) => <li key={finding}>· {finding}</li>)}
            </ul>
          </div>
        )}

        <div className="mt-7 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">完整执行时间线</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              上下文收集、规划、工具、观察与回答均按发生顺序记录
            </p>
          </div>
          <span className="text-xs text-muted-foreground">{run.steps.length} 个阶段</span>
        </div>
        <div className="relative mt-4 space-y-3 before:absolute before:bottom-5 before:left-[1.1rem] before:top-5 before:w-px before:bg-black/[0.07]">
          {run.steps.map((step) => {
            const expanded = expandedStep === step.id
            return (
              <div
                key={step.id}
                className={cn(
                  "relative rounded-2xl border bg-white p-3.5 transition-colors",
                  step.status === "running"
                    ? "border-primary/25 shadow-[0_0_0_3px_rgba(37,99,235,.05)]"
                    : step.status === "failed"
                      ? "border-destructive/20"
                      : "border-black/[0.06]"
                )}
              >
                <button
                  className="flex w-full items-center gap-3 text-left"
                  onClick={() => setExpandedStep(expanded ? null : step.id)}
                >
                  <StepMark status={step.status} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-medium">
                        {stepTitle(step)}
                      </p>
                      <span className="rounded-full bg-secondary px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                        {stepTypeLabel(step.step_type)}
                      </span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                      {stepSummary(step)}
                    </p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      阶段 {step.step_index + 1} · {stepStatusLabel(step.status)} · {step.status === "running" ? "计时中" : formatDuration(step.latency_ms)}
                    </p>
                  </div>
                  {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </button>
                {expanded && (
                  <div className="mt-3 grid gap-2">
                    {Object.keys(step.input_json).length > 0 && (
                      <JsonBlock label="输入" value={step.input_json} />
                    )}
                    {Object.keys(step.output_json).length > 0 && (
                      <JsonBlock label="输出" value={step.output_json} />
                    )}
                    {step.error_message && (
                      <p className="rounded-xl bg-destructive/[0.06] p-3 text-xs text-destructive">
                        {step.error_message}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )
          })}
          {run.steps.length === 0 && (
            <div className="rounded-2xl border border-dashed border-black/10 px-5 py-10 text-center">
              <Loader2 className="mx-auto h-5 w-5 animate-spin text-primary" />
              <p className="mt-3 text-sm font-medium">正在初始化 Agent Run</p>
              <p className="mt-1 text-xs text-muted-foreground">首个上下文收集阶段即将出现。</p>
            </div>
          )}
        </div>

        {run.answer && !live && (
          <div className="mt-7 rounded-2xl border border-black/[0.06] bg-white p-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.1em] text-primary">
              <MessageSquareText className="h-4 w-4" />
              最终回答
            </div>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{run.answer}</p>
          </div>
        )}

        {run.error_message && (
          <div className="mt-4 rounded-2xl border border-destructive/15 bg-destructive/[0.055] p-4">
            <p className="text-xs font-semibold text-destructive">失败原因</p>
            <p className="mt-2 break-words text-xs leading-5 text-destructive/85">{run.error_message}</p>
          </div>
        )}

        <div className="mt-7 flex justify-end">
          <button
            className="secondary-button"
            onClick={() => onReplay(run.id)}
            disabled={replaying || live}
          >
            {replaying ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
            回放本次任务
          </button>
        </div>
      </aside>
    </div>
  )
}

function InspectorMetric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Gauge
  label: string
  value: string
}) {
  return (
    <div className="rounded-2xl border border-black/[0.05] bg-white p-3">
      <Icon className="h-4 w-4 text-primary" strokeWidth={1.7} />
      <p className="mt-3 text-lg font-semibold tracking-[-0.03em]">{value}</p>
      <p className="text-[10px] text-muted-foreground">{label}</p>
    </div>
  )
}

function JsonBlock({ label, value }: { label: string; value: Record<string, unknown> }) {
  return (
    <div className="rounded-xl bg-secondary/65 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">{label}</p>
      <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words text-[11px] leading-5">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}

function StatusMark({ status }: { status: string }) {
  const successful = ["success", "completed"].includes(status)
  const failed = ["failed", "error"].includes(status)
  return (
    <span className={cn(
      "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
      successful ? "bg-success/10 text-success" :
        failed ? "bg-destructive/10 text-destructive" :
          ["needs_confirm", "needs_clarification", "degraded", "step_limit"].includes(status) ? "bg-warning/10 text-warning" :
            "bg-primary/10 text-primary"
    )}>
      {successful ? <Check className="h-4 w-4" /> :
        failed ? <X className="h-4 w-4" /> :
          <Activity className="h-4 w-4" />}
    </span>
  )
}

function StepMark({ status }: { status: string }) {
  if (status === "running") {
    return (
      <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Loader2 className="h-4 w-4 animate-spin" />
      </span>
    )
  }
  if (status === "failed" || status === "error" || status === "denied") {
    return (
      <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <X className="h-4 w-4" />
      </span>
    )
  }
  return status === "success" ? (
    <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-success/10 text-success">
      <Check className="h-4 w-4" />
    </span>
  ) : (
    <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-warning/10 text-warning">
      <Clock3 className="h-4 w-4" />
    </span>
  )
}

function StageGlyph({ step }: { step: AgentRunDetail["steps"][number] }) {
  const iconClass = "h-4 w-4"
  const stage = step.tool_name || ""
  if (stage === "understanding.task") return <Target className={iconClass} />
  if (stage === "context.recent_messages") return <MessageSquareText className={iconClass} />
  if (stage === "context.daily_digest") return <BookOpen className={iconClass} />
  if (stage === "context.knowledge") return <Database className={iconClass} />
  if (stage === "context.candidates") return <FileSearch className={iconClass} />
  if (stage === "context.memory") return <Brain className={iconClass} />
  if (stage === "context.profile") return <UserRound className={iconClass} />
  if (stage === "context.assemble") return <ListFilter className={iconClass} />
  if (step.step_type === "tool") return <Wrench className={iconClass} />
  if (step.step_type === "decision") return <Sparkles className={iconClass} />
  return <Activity className={iconClass} />
}

function stepTitle(step: AgentRunDetail["steps"][number]) {
  const stageLabels: Record<string, string> = {
    "understanding.task": "理解任务并建立执行契约",
    "context.recent_messages": "读取最近对话",
    "context.daily_digest": "读取最新简报",
    "context.knowledge": "检索本地知识库",
    "context.candidates": "筛选候选内容",
    "context.memory": "检索相关记忆",
    "context.profile": "加载兴趣与项目画像",
    "context.assemble": "组装 Agent 上下文",
    "planner.decide": "规划下一步行动",
    "memory.extract": "提取可沉淀记忆",
    "response.final": "生成最终回答",
    "response.failed": "记录失败结果",
  }

  if (step.step_type === "decision" && step.status !== "running") {
    if (step.output_json.kind === "tool") {
      return `规划调用工具：${String(step.output_json.tool_name || "未知工具")}`
    }
    if (step.output_json.kind === "final") return "规划完成：准备回答"
  }
  if (step.step_type === "tool") {
    return `执行工具：${step.tool_name || "未知工具"}`
  }
  return stageLabels[step.tool_name || ""] || stepTypeLabel(step.step_type)
}

function stepSummary(step: AgentRunDetail["steps"][number]) {
  if (step.status === "running") return "该阶段正在执行，结果会自动更新。"
  if (step.error_message) return step.error_message

  if (step.tool_name === "understanding.task") {
    const goal = String(step.output_json.goal || "任务目标")
    const confidence = Math.round(Number(step.output_json.confidence || 0) * 100)
    return `理解为“${goal}”，置信度 ${confidence}%，风险级别 ${taskRiskLabel(String(step.output_json.risk || "safe"))}。`
  }
  if (step.step_type === "decision") {
    return String(
      step.output_json.decision_summary ||
      "模型已根据当前上下文和工具观察完成一次规划。"
    )
  }
  if (step.step_type === "tool") {
    return String(
      step.output_json.content ||
      step.output_json.error_message ||
      "工具调用已完成，可展开查看输入与结构化输出。"
    )
  }
  if (step.tool_name === "context.assemble") {
    const total = step.output_json.total_chars
    const counts = step.output_json.counts as Record<string, number> | undefined
    const itemCount = counts
      ? Object.values(counts).reduce((sum, count) => sum + Number(count || 0), 0)
      : 0
    return `上下文组装完成：${itemCount} 项信息，约 ${String(total || 0)} 个字符。`
  }
  if (step.step_type === "context") {
    return `已收集 ${String(step.output_json.count || 0)} 项，可展开查看具体来源与内容。`
  }
  if (step.tool_name === "memory.extract") {
    return `记忆提取完成，新增 ${String(step.output_json.created_count || 0)} 条候选记忆。`
  }
  if (step.step_type === "final") {
    return String(
      step.output_json.answer ||
      "本次运行已结束。"
    ).slice(0, 160)
  }
  return "阶段已完成，可展开查看输入与输出。"
}

function stepStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "等待中",
    running: "执行中",
    success: "成功",
    completed: "已完成",
    degraded: "降级完成",
    failed: "失败",
    error: "错误",
    denied: "已拒绝",
    needs_confirm: "等待确认",
    needs_clarification: "等待补充",
    step_limit: "达到步数上限",
  }
  return labels[status] || status
}

function runStatusLabel(status: string) {
  return stepStatusLabel(status)
}

function formatDuration(milliseconds: number) {
  if (milliseconds < 1000) return `${milliseconds} ms`
  return `${(milliseconds / 1000).toFixed(1)} s`
}

function goalStatusLabel(status: string) {
  const labels: Record<string, string> = {
    active: "运行中",
    running: "执行中",
    paused: "已暂停",
    failed: "失败",
    completed: "已完成",
  }
  return labels[status] || status
}

function stepTypeLabel(stepType: string) {
  const labels: Record<string, string> = {
    understanding: "任务理解",
    decision: "决策",
    tool: "工具调用",
    observation: "工具观察",
    final: "最终回答",
  }
  return labels[stepType] || stepType
}

function taskBriefFromRun(run: AgentRunDetail): AgentTaskBrief | null {
  const value = run.used_context_json.task_brief
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  const brief = value as Partial<AgentTaskBrief>
  if (
    typeof brief.goal !== "string" ||
    typeof brief.intent !== "string" ||
    !Array.isArray(brief.required_context) ||
    !Array.isArray(brief.success_criteria)
  ) {
    return null
  }
  return brief as AgentTaskBrief
}

function taskIntentLabel(intent: string) {
  const labels: Record<string, string> = {
    retrieve: "检索",
    compare: "比较",
    summarize: "总结",
    organize: "整理",
    monitor: "持续跟踪",
    act: "执行动作",
    configure: "配置",
    converse: "对话",
  }
  return labels[intent] || intent
}

function taskRiskLabel(risk: string) {
  const labels: Record<string, string> = {
    safe: "只读安全",
    sensitive: "有副作用 · 受控",
    destructive: "高风险 · 需确认",
  }
  return labels[risk] || risk
}

function contextSourceLabel(source: string) {
  const labels: Record<string, string> = {
    conversation: "最近对话",
    digest: "最新简报",
    knowledge: "知识库",
    candidate: "候选池",
    memory: "长期记忆",
    profile: "用户画像",
  }
  return labels[source] || source
}

function outputShapeLabel(output: string) {
  const labels: Record<string, string> = {
    answer: "直接回答",
    list: "排序列表",
    summary: "结构化摘要",
    comparison: "对比结论",
    action_result: "执行结果",
  }
  return labels[output] || output
}
