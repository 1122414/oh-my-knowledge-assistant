import { useState, useEffect } from "react"
import { Loader2, AlertCircle, ScrollText, Check, X, Clock } from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import { jobsApi, type JobRun } from "@/api/jobs"
import { cn } from "@/lib/cn"

export function JobLogsPage() {
  const [runs, setRuns] = useState<JobRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchRuns = async () => {
      try {
        const data = await jobsApi.getRuns()
        setRuns(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载失败")
      } finally {
        setLoading(false)
      }
    }
    fetchRuns()
  }, [])

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="运行记录"
        description="追踪每一次采集、清洗、排序和知识生成任务。"
      />

      {error && (
        <div className="alert-panel mb-6 border-destructive/15 bg-destructive/[0.055] text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="space-y-4">
        {runs.length === 0 ? (
          <div className="empty-state">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary">
              <ScrollText className="h-6 w-6 text-muted-foreground" strokeWidth={1.6} />
            </div>
            <h2 className="mt-5 text-xl font-semibold tracking-[-0.03em]">暂无运行记录</h2>
            <p className="mt-2 text-sm text-muted-foreground">首次运行知识采集后，这里会显示完整轨迹。</p>
          </div>
        ) : (
          runs.map((run) => (
            <div
              key={run.id}
              className="apple-surface p-5 sm:p-6"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-full",
                      run.status === "success"
                        ? "bg-success/10 text-success"
                        : run.status === "failed"
                        ? "bg-destructive/10 text-destructive"
                        : "bg-muted text-muted-foreground"
                    )}
                  >
                    {run.status === "success" ? (
                      <Check className="h-4 w-4" />
                    ) : run.status === "failed" ? (
                      <X className="h-4 w-4" />
                    ) : (
                      <Clock className="h-4 w-4" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium">{run.job_type}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(run.started_at).toLocaleString("zh-CN")}
                    </p>
                  </div>
                </div>
                <div className="flex gap-4 text-sm text-muted-foreground">
                  <span>抓取: {run.fetched_count}</span>
                  <span>候选: {run.candidate_count}</span>
                </div>
              </div>
              {run.error_message && (
                <p className="mt-2 text-sm text-destructive">{run.error_message}</p>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
