import { useState } from "react"
import { Bell, Plus, Loader2, AlertCircle, ToggleLeft, ToggleRight, Activity, Calendar } from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import { usePush } from "@/hooks/use-push"
import { cn } from "@/lib/cn"

const TRIGGER_LABELS: Record<string, string> = {
  daily: "每日简报",
  high_score: "高价值推送",
  reminder: "提醒",
  system_alert: "系统告警",
}

const STATUS_COLORS: Record<string, string> = {
  pending: "text-yellow-600 bg-yellow-50",
  sent: "text-green-600 bg-green-50",
  failed: "text-red-600 bg-red-50",
  skipped: "text-gray-600 bg-gray-50",
}

export function PushPage() {
  const {
    policies,
    events,
    status,
    loading,
    saving,
    error,
    createPolicy,
    togglePolicy,
  } = usePush()

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [formData, setFormData] = useState({
    id: "",
    name: "",
    trigger_type: "high_score",
    threshold: "0.85",
    max_per_day: "5",
  })

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    await createPolicy({
      id: formData.id,
      name: formData.name,
      trigger_type: formData.trigger_type,
      threshold: formData.threshold ? parseFloat(formData.threshold) : undefined,
      max_per_day: formData.max_per_day ? parseInt(formData.max_per_day) : undefined,
    })
    setShowCreateForm(false)
    setFormData({ id: "", name: "", trigger_type: "high_score", threshold: "0.85", max_per_day: "5" })
  }

  if (loading && policies.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="推送管理"
        description="配置推送策略，查看推送历史"
      />

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {status && (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Activity className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">今日推送</p>
                <p className="text-2xl font-semibold">{status.today_pushes}</p>
              </div>
            </div>
          </div>
          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Bell className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">活跃策略</p>
                <p className="text-2xl font-semibold">{policies.filter((p) => p.enabled).length}</p>
              </div>
            </div>
          </div>
          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Calendar className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">今日上限</p>
                <p className="text-2xl font-semibold">{status.max_per_day_default}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Bell className="h-5 w-5 text-primary" />
            </div>
            <h2 className="text-lg font-semibold">推送策略</h2>
          </div>
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            新建策略
          </button>
        </div>

        {showCreateForm && (
          <form onSubmit={handleCreate} className="mb-6 rounded-xl border border-border bg-background p-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">策略 ID</label>
                <input
                  type="text"
                  value={formData.id}
                  onChange={(e) => setFormData((prev) => ({ ...prev, id: e.target.value }))}
                  placeholder="如: high_score_push"
                  required
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">策略名称</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="如: 高价值推送"
                  required
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">触发类型</label>
                <select
                  value={formData.trigger_type}
                  onChange={(e) => setFormData((prev) => ({ ...prev, trigger_type: e.target.value }))}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="daily">每日简报</option>
                  <option value="high_score">高价值推送</option>
                  <option value="reminder">提醒</option>
                  <option value="system_alert">系统告警</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">分数阈值</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  value={formData.threshold}
                  onChange={(e) => setFormData((prev) => ({ ...prev, threshold: e.target.value }))}
                  placeholder="0.0-1.0"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <label className="text-sm font-medium">每日最大推送次数</label>
                <input
                  type="number"
                  min="1"
                  value={formData.max_per_day}
                  onChange={(e) => setFormData((prev) => ({ ...prev, max_per_day: e.target.value }))}
                  placeholder="5"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <button
                type="submit"
                disabled={saving}
                className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                创建
              </button>
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-accent"
              >
                取消
              </button>
            </div>
          </form>
        )}

        {policies.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground">
            <Bell className="mx-auto mb-3 h-10 w-10 opacity-50" />
            <p>暂无推送策略</p>
            <p className="mt-1 text-sm">点击"新建策略"创建第一个推送规则</p>
          </div>
        ) : (
          <div className="space-y-3">
            {policies.map((policy) => (
              <div
                key={policy.id}
                className="flex items-center justify-between rounded-xl border border-border bg-background p-4"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="font-medium">{policy.name}</h3>
                    <span className="rounded-md bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
                      {TRIGGER_LABELS[policy.trigger_type] || policy.trigger_type}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    ID: {policy.id}
                    {policy.threshold !== null && policy.threshold !== undefined && (
                      <> · 阈值: {policy.threshold}</>
                    )}
                    {policy.max_per_day > 0 && (
                      <> · 每日上限: {policy.max_per_day}</>
                    )}
                  </p>
                </div>
                <button
                  onClick={() => togglePolicy(policy.id, !policy.enabled)}
                  className={cn(
                    "flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    policy.enabled
                      ? "text-green-700 hover:bg-green-50"
                      : "text-gray-500 hover:bg-gray-50"
                  )}
                >
                  {policy.enabled ? (
                    <>
                      <ToggleRight className="h-5 w-5" />
                      已启用
                    </>
                  ) : (
                    <>
                      <ToggleLeft className="h-5 w-5" />
                      已禁用
                    </>
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Activity className="h-5 w-5 text-primary" />
          </div>
          <h2 className="text-lg font-semibold">最近推送记录</h2>
        </div>

        {events.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground">
            <Activity className="mx-auto mb-3 h-10 w-10 opacity-50" />
            <p>暂无推送记录</p>
          </div>
        ) : (
          <div className="space-y-2">
            {events.map((event) => (
              <div
                key={event.id}
                className="flex items-start justify-between rounded-lg border border-border bg-background p-3"
              >
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{event.title}</p>
                  <p className="mt-0.5 text-sm text-muted-foreground truncate">
                    {event.content}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    策略: {event.policy_id} · 渠道: {event.channel} ·{" "}
                    {new Date(event.created_at).toLocaleString("zh-CN")}
                  </p>
                </div>
                <span
                  className={cn(
                    "ml-3 shrink-0 rounded-md px-2 py-0.5 text-xs font-medium",
                    STATUS_COLORS[event.status] || "text-gray-600 bg-gray-50"
                  )}
                >
                  {event.status === "pending" && "待发送"}
                  {event.status === "sent" && "已发送"}
                  {event.status === "failed" && "失败"}
                  {event.status === "skipped" && "已跳过"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
