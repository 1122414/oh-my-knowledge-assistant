import { PageHeader } from "@/components/layout/page-header"

export function JobLogsPage() {
  return (
    <div>
      <PageHeader title="Job Logs" description="任务运行日志" />
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <p className="text-muted-foreground">Job Logs page placeholder</p>
      </div>
    </div>
  )
}
