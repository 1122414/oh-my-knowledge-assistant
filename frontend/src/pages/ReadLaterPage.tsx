import { PageHeader } from "@/components/layout/page-header"

export function ReadLaterPage() {
  return (
    <div>
      <PageHeader title="Read Later" description="稍后阅读列表" />
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <p className="text-muted-foreground">Read Later page placeholder</p>
      </div>
    </div>
  )
}
