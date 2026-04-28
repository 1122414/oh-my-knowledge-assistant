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
    <div className="space-y-6">
      <PageHeader title="Job Logs" description="任务运行日志" />

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="space-y-3">
        {runs.length === 0 ? (
          <div className="rounded-2xl border border-border bg-card p-12 text-center shadow-sm">
            <ScrollText className="mx-auto h-12 w-12 text-muted-foreground" />
            <p className="mt-4 text-muted-foreground">暂无任务记录</p>
          </div>
        ) : (
          runs.map((run) => (
            <div
              key={run.id}
              className="rounded-2xl border border-border bg-card p-5 shadow-sm"
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
