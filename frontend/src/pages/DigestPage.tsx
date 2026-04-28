import { PageHeader } from "@/components/layout/page-header"

export function DigestPage() {
  return (
    <div>
      <PageHeader title="Digest" description="每日推荐内容" />
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <p className="text-muted-foreground">Digest page placeholder</p>
      </div>
    </div>
  )
}
