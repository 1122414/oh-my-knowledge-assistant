import { useState, useEffect } from "react"
import { Play, Loader2, AlertCircle, Check, Clock, Brain, Newspaper, Activity, CalendarClock } from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import { useDashboard } from "@/hooks/use-dashboard"
import { jobsApi, type ScheduleInfo } from "@/api/jobs"
import { cn } from "@/lib/cn"

export function DashboardPage() {
  const { data, loading, error, fetchData } = useDashboard()
  const [running, setRunning] = useState(false)
  const [schedule, setSchedule] = useState<ScheduleInfo | null>(null)

  const fetchSchedule = async () => {
    try {
      const info = await jobsApi.getSchedule()
      setSchedule(info)
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    fetchSchedule()
  }, [])

  const handleRunNow = async () => {
    setRunning(true)
    try {
      await jobsApi.runNow()
      await fetchData()
    } catch {
      // ignore
    } finally {
      setRunning(false)
    }
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const metrics = [
    {
      label: "今日运行",
      value: data?.today_run.status === "none" ? "未运行" : data?.today_run.status === "success" ? "成功" : "失败",
      icon: Activity,
      status: data?.today_run.status === "success" ? "success" : "neutral",
    },
    {
      label: "抓取数量",
      value: String(data?.today_run.fetched_count ?? 0),
      icon: Newspaper,
      status: "neutral",
    },
    {
      label: "候选内容",
      value: String(data?.pending_candidates ?? 0),
      icon: Clock,
      status: "neutral",
    },
    {
      label: "知识库",
      value: String(data?.knowledge_count ?? 0),
      icon: Brain,
      status: "neutral",
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="OMKA 运行状态概览">
        <button
          onClick={handleRunNow}
          disabled={running}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {running ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Run Now
        </button>
      </PageHeader>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon
          return (
            <div
              key={metric.label}
              className="rounded-2xl border border-border bg-card p-6 shadow-sm"
            >
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-lg",
                    metric.status === "success"
                      ? "bg-success/10 text-success"
                      : "bg-primary/10 text-primary"
                  )}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <span className="text-sm text-muted-foreground">{metric.label}</span>
              </div>
              <p className="mt-3 text-3xl font-semibold">{metric.value}</p>
            </div>
          )
        })}
      </div>

      {schedule && (
        <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <CalendarClock className="h-5 w-5 text-muted-foreground" />
            <h3 className="text-lg font-semibold">定时任务</h3>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Cron 表达式</p>
              <p className="font-mono font-medium">{schedule.cron}</p>
            </div>
            <div>
              <p className="text-muted-foreground">时区</p>
              <p className="font-medium">{schedule.timezone}</p>
            </div>
            <div>
              <p className="text-muted-foreground">下次运行</p>
              <p className="font-medium">
                {schedule.next_run_time
                  ? new Date(schedule.next_run_time).toLocaleString("zh-CN")
                  : "未启动"}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">状态</p>
              <span className={cn(
                "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
                schedule.running ? "bg-success/10 text-success" : "bg-muted text-muted-foreground"
              )}>
                {schedule.running ? "运行中" : "未启动"}
              </span>
            </div>
          </div>
        </div>
      )}

      {data?.today_run.started_at && (
        <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
          <h3 className="text-lg font-semibold">今日任务详情</h3>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">开始时间</p>
              <p className="font-medium">{new Date(data.today_run.started_at).toLocaleString("zh-CN")}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">状态</p>
              <div className="flex items-center gap-1">
                {data.today_run.status === "success" ? (
                  <>
                    <Check className="h-4 w-4 text-success" />
                    <span className="text-success">成功</span>
                  </>
                ) : (
                  <span>{data.today_run.status}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
