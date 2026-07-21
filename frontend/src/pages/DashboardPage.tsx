import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  Play,
  Loader2,
  AlertCircle,
  Check,
  Clock3,
  Brain,
  Newspaper,
  Activity,
  CalendarClock,
  ArrowUpRight,
  Sparkles,
} from "lucide-react"
import { useDashboard } from "@/hooks/use-dashboard"
import { jobsApi, type ScheduleInfo } from "@/api/jobs"
import { cn } from "@/lib/cn"

export function DashboardPage() {
  const { data, loading, error, fetchData } = useDashboard()
  const [running, setRunning] = useState(false)
  const [schedule, setSchedule] = useState<ScheduleInfo | null>(null)

  const fetchSchedule = async () => {
    try {
      setSchedule(await jobsApi.getSchedule())
    } catch {
      // The dashboard remains useful when scheduler data is unavailable.
    }
  }

  useEffect(() => {
    fetchSchedule()
  }, [])

  const handleRunNow = async () => {
    setRunning(true)
    try {
      await jobsApi.runNow()
      await Promise.all([fetchData(), fetchSchedule()])
    } finally {
      setRunning(false)
    }
  }

  if (loading) {
    return <DashboardSkeleton />
  }

  const isHealthy = data?.today_run.status === "success"
  const metrics = [
    {
      label: "今日运行",
      value: data?.today_run.status === "none" ? "待运行" : isHealthy ? "已完成" : "需关注",
      icon: Activity,
      accent: isHealthy,
    },
    {
      label: "今日采集",
      value: String(data?.today_run.fetched_count ?? 0),
      suffix: " 条",
      icon: Newspaper,
    },
    {
      label: "待决策",
      value: String(data?.pending_candidates ?? 0),
      suffix: " 条",
      icon: Clock3,
    },
    {
      label: "长期知识",
      value: String(data?.knowledge_count ?? 0),
      suffix: " 条",
      icon: Brain,
    },
  ]

  return (
    <div className="space-y-6 sm:space-y-8">
      <section className="apple-surface relative min-h-[390px] overflow-hidden px-6 py-8 sm:px-10 sm:py-11 lg:min-h-[430px] lg:px-14 lg:py-14">
        <img
          src="/images/knowledge-flow-hero.png"
          alt=""
          className="absolute inset-0 h-full w-full object-cover object-center"
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(255,255,255,0.99)_0%,rgba(255,255,255,0.96)_34%,rgba(255,255,255,0.38)_68%,rgba(255,255,255,0.08)_100%)]" />
        <div className="relative z-10 flex min-h-[310px] max-w-[600px] flex-col justify-center lg:min-h-[320px]">
          <div className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-black/[0.055] bg-white/78 px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-sm backdrop-blur-xl">
            <span className="relative flex h-2 w-2">
              <span className="absolute h-full w-full animate-ping rounded-full bg-success opacity-25" />
              <span className="relative h-2 w-2 rounded-full bg-success" />
            </span>
            Agent Runtime 在线
          </div>
          <p className="eyebrow">Personal Knowledge Intelligence</p>
          <h1 className="mt-3 text-balance text-[clamp(2.6rem,5.5vw,5rem)] font-semibold leading-[0.98] tracking-[-0.06em] text-foreground">
            让知识开始
            <br />
            形成判断力。
          </h1>
          <p className="mt-5 max-w-[500px] text-[15px] leading-6 text-muted-foreground sm:text-[17px] sm:leading-7">
            OMKA 持续采集、理解并沉淀与你真正相关的内容，把信息流变成可行动的长期知识。
          </p>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <button onClick={handleRunNow} disabled={running} className="primary-button">
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-current" />}
              {running ? "正在运行" : "立即更新"}
            </button>
            <Link to="/digest" className="secondary-button">
              查看今日精选
              <ArrowUpRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      {error && (
        <div className="alert-panel border-destructive/15 bg-destructive/[0.055] text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">部分数据暂时不可用</p>
            <p className="mt-0.5 text-destructive/80">{error}</p>
          </div>
        </div>
      )}

      <section className="apple-surface grid divide-y divide-black/[0.055] overflow-hidden sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon
          return (
            <div key={metric.label} className="group px-6 py-6 sm:px-7 sm:py-7">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium tracking-wide text-muted-foreground">{metric.label}</p>
                <Icon
                  className={cn(
                    "h-[18px] w-[18px] transition-transform duration-300 group-hover:-translate-y-0.5",
                    metric.accent ? "text-success" : "text-muted-foreground/65"
                  )}
                  strokeWidth={1.75}
                />
              </div>
              <p className="mt-4 text-[30px] font-semibold leading-none tracking-[-0.045em]">
                {metric.value}
                {metric.suffix && (
                  <span className="ml-1 text-sm font-medium tracking-normal text-muted-foreground">{metric.suffix}</span>
                )}
              </p>
            </div>
          )
        })}
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.35fr_0.85fr]">
        <div className="apple-surface p-6 sm:p-8">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Automation</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.035em]">下一次知识更新</h2>
            </div>
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-secondary text-foreground">
              <CalendarClock className="h-5 w-5" strokeWidth={1.7} />
            </div>
          </div>

          {schedule ? (
            <div className="mt-8 grid gap-5 sm:grid-cols-3">
              <Detail label="运行频率" value={humanizeCron(schedule.cron)} />
              <Detail label="下次运行" value={schedule.next_run_time ? formatDate(schedule.next_run_time) : "等待调度"} />
              <Detail label="运行时区" value={schedule.timezone} />
            </div>
          ) : (
            <p className="mt-8 text-sm text-muted-foreground">尚未读取到调度信息。</p>
          )}

          <div className="mt-8 flex items-center justify-between rounded-2xl bg-secondary/70 px-4 py-3.5">
            <div className="flex items-center gap-3">
              <span className={cn("h-2.5 w-2.5 rounded-full", schedule?.running ? "bg-success" : "bg-muted-foreground/40")} />
              <div>
                <p className="text-sm font-medium">{schedule?.running ? "自动任务运行正常" : "自动任务等待启动"}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">可在设置中调整采集节奏</p>
              </div>
            </div>
            <Link to="/settings" className="text-xs font-medium text-primary hover:underline">管理</Link>
          </div>
        </div>

        <div className="apple-surface relative overflow-hidden p-6 sm:p-8">
          <div className="absolute -right-10 -top-10 h-36 w-36 rounded-full bg-primary/[0.07] blur-2xl" />
          <div className="relative">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-white shadow-[0_8px_24px_rgba(0,113,227,0.22)]">
              <Sparkles className="h-5 w-5" strokeWidth={1.8} />
            </div>
            <p className="eyebrow mt-7">Today</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-[-0.035em]">
              {data?.today_run.started_at ? "今日知识流已更新" : "准备好开始今天的学习"}
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              {data?.today_run.started_at
                ? `最近一次运行始于 ${formatDate(data.today_run.started_at)}。`
                : "运行一次采集任务，OMKA 会为你筛选值得投入注意力的内容。"}
            </p>
            <div className="mt-7 flex items-center gap-2 text-sm">
              {isHealthy ? (
                <>
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-success/10 text-success">
                    <Check className="h-3.5 w-3.5" strokeWidth={2.4} />
                  </span>
                  <span className="font-medium text-success">所有阶段完成</span>
                </>
              ) : (
                <>
                  <Clock3 className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium text-muted-foreground">等待下一次成功运行</span>
                </>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-5 text-foreground">{value}</p>
    </div>
  )
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function humanizeCron(cron: string) {
  const parts = cron.trim().split(/\s+/)
  if (parts.length === 5 && /^\d+$/.test(parts[0]) && /^\d+$/.test(parts[1])) {
    return `每天 ${parts[1].padStart(2, "0")}:${parts[0].padStart(2, "0")}`
  }
  return cron
}

function DashboardSkeleton() {
  return (
    <div className="space-y-8" aria-label="正在加载概览">
      <div className="apple-surface h-[420px] animate-pulse bg-white/65" />
      <div className="apple-surface grid grid-cols-2 divide-x divide-black/[0.05] overflow-hidden lg:grid-cols-4">
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="h-32 animate-pulse bg-white/45 p-6">
            <div className="h-3 w-20 rounded bg-muted" />
            <div className="mt-5 h-8 w-24 rounded bg-muted" />
          </div>
        ))}
      </div>
    </div>
  )
}
