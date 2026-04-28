import { PageHeader } from "@/components/layout/page-header"

export function SettingsPage() {
  return (
    <div>
      <PageHeader title="Settings" description="管理应用配置" />
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <p className="text-muted-foreground">Settings page placeholder</p>
      </div>
    </div>
  )
}
