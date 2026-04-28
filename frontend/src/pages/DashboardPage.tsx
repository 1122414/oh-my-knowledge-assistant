import { PageHeader } from "@/components/layout/page-header"

export function DashboardPage() {
  return (
    <div>
      <PageHeader title="Dashboard" description="OMKA 运行状态概览" />
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "今日运行", value: "--", status: "未运行" },
          { label: "抓取数量", value: "0", status: "仓库" },
          { label: "候选内容", value: "0", status: "条" },
          { label: "知识库", value: "0", status: "条" },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-2xl border border-border bg-card p-6 shadow-sm"
          >
            <p className="text-sm text-muted-foreground">{item.label}</p>
            <p className="mt-2 text-3xl font-semibold">{item.value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{item.status}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
