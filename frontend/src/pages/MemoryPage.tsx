import { useState } from "react"
import {
  AlertCircle,
  Brain,
  CheckCircle,
  Import,
  Loader2,
  Pencil,
  Plus,
  Save,
  ShieldCheck,
  Sparkles,
  Tag,
  Trash2,
  X,
  XCircle,
} from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import { useMemory } from "@/hooks/use-memory"
import type { UserProfileSnapshot } from "@/api/memory"
import { cn } from "@/lib/cn"

const TYPE_LABELS: Record<string, string> = {
  user: "用户画像",
  conversation: "对话记忆",
  system: "系统知识",
}

const TYPE_COLORS: Record<string, string> = {
  user: "text-primary bg-primary/[0.07]",
  conversation: "text-foreground bg-secondary",
  system: "text-success bg-success/[0.07]",
}

const STATUS_LABELS: Record<string, string> = {
  active: "已激活",
  candidate: "候选",
  rejected: "已拒绝",
  archived: "已归档",
}

const STATUS_COLORS: Record<string, string> = {
  active: "text-green-600 bg-green-50",
  candidate: "text-yellow-600 bg-yellow-50",
  rejected: "text-red-600 bg-red-50",
  archived: "text-gray-600 bg-gray-50",
}

export function MemoryPage() {
  const {
    memories,
    total,
    profile,
    profileSnapshot,
    loading,
    saving,
    error,
    createMemory,
    confirmMemory,
    rejectMemory,
    deleteMemory,
    updateMemory,
    importProfile,
  } = useMemory()

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [filterType, setFilterType] = useState("")
  const [filterStatus, setFilterStatus] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editContent, setEditContent] = useState("")
  const [editConfidence, setEditConfidence] = useState("0.8")
  const [formData, setFormData] = useState({
    memory_type: "user",
    subject: "",
    content: "",
    scope: "global",
    importance: "0.5",
    tags: "",
  })

  const filteredMemories = memories.filter((m) => {
    if (filterType && m.memory_type !== filterType) return false
    if (filterStatus && m.status !== filterStatus) return false
    return true
  })

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    await createMemory({
      memory_type: formData.memory_type,
      subject: formData.subject,
      content: formData.content,
      scope: formData.scope,
      importance: parseFloat(formData.importance),
      tags: formData.tags.split(",").map((t) => t.trim()).filter(Boolean),
    })
    setShowCreateForm(false)
    setFormData({ memory_type: "user", subject: "", content: "", scope: "global", importance: "0.5", tags: "" })
  }

  if (loading && memories.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        eyebrow="Evidence-driven Profile"
        title="你的画像与记忆"
        description="每一条长期认知都带来源、置信度与确认状态；你可以随时纠正，Agent 不会把猜测当成事实。"
      >
        <button
          onClick={() => importProfile()}
          disabled={saving}
          className="secondary-button"
        >
          <Import className="h-4 w-4" />
          导入画像
        </button>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="primary-button"
        >
          <Plus className="h-4 w-4" />
          新建记忆
        </button>
      </PageHeader>

      {error && (
        <div className="alert-panel mb-6 border-destructive/15 bg-destructive/[0.055] text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {profileSnapshot && (
        <ProfileSnapshotPanel
          snapshot={profileSnapshot}
          onConfirm={confirmMemory}
          onReject={rejectMemory}
        />
      )}

      {profile && (
        <div className="apple-surface mb-6 grid divide-y divide-black/[0.055] overflow-hidden sm:grid-cols-4 sm:divide-x sm:divide-y-0">
          <div className="p-5 sm:p-6">
            <p className="text-sm text-muted-foreground">用户画像</p>
            <p className="mt-1 text-2xl font-semibold">{profile.user_memories}</p>
          </div>
          <div className="p-5 sm:p-6">
            <p className="text-sm text-muted-foreground">对话记忆</p>
            <p className="mt-1 text-2xl font-semibold">{profile.conversation_memories}</p>
          </div>
          <div className="p-5 sm:p-6">
            <p className="text-sm text-muted-foreground">系统知识</p>
            <p className="mt-1 text-2xl font-semibold">{profile.system_memories}</p>
          </div>
          <div className="p-5 sm:p-6">
            <p className="text-sm text-muted-foreground">候选记忆</p>
            <p className="mt-1 text-2xl font-semibold">{profile.candidate_memories}</p>
          </div>
        </div>
      )}

      <div className="apple-surface-subtle mb-6 flex flex-col gap-4 p-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="field-control w-auto min-w-36"
          >
            <option value="">所有类型</option>
            <option value="user">用户画像</option>
            <option value="conversation">对话记忆</option>
            <option value="system">系统知识</option>
          </select>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="field-control w-auto min-w-36"
          >
            <option value="">所有状态</option>
            <option value="active">已激活</option>
            <option value="candidate">候选</option>
            <option value="rejected">已拒绝</option>
            <option value="archived">已归档</option>
          </select>
          {(filterType || filterStatus) && (
            <button
              onClick={() => { setFilterType(""); setFilterStatus("") }}
              className="secondary-button"
            >
              清除筛选
            </button>
          )}
        </div>
        <p className="px-2 text-xs font-medium text-muted-foreground">
          当前显示 {filteredMemories.length} / {total}
        </p>
      </div>

      {showCreateForm && (
        <form onSubmit={handleCreate} className="apple-surface mb-6 p-6 sm:p-8">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">类型</label>
              <select
                value={formData.memory_type}
                onChange={(e) => setFormData((prev) => ({ ...prev, memory_type: e.target.value }))}
                className="field-control"
              >
                <option value="user">用户画像</option>
                <option value="conversation">对话记忆</option>
                <option value="system">系统知识</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">主题</label>
              <input
                type="text"
                value={formData.subject}
                onChange={(e) => setFormData((prev) => ({ ...prev, subject: e.target.value }))}
                placeholder="记忆主题"
                required
                className="field-control"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">作用域</label>
              <input
                type="text"
                value={formData.scope}
                onChange={(e) => setFormData((prev) => ({ ...prev, scope: e.target.value }))}
                placeholder="global"
                className="field-control"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">重要性 (0-1)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={formData.importance}
                onChange={(e) => setFormData((prev) => ({ ...prev, importance: e.target.value }))}
                className="field-control"
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <label className="text-sm font-medium">内容</label>
              <textarea
                value={formData.content}
                onChange={(e) => setFormData((prev) => ({ ...prev, content: e.target.value }))}
                placeholder="记忆内容..."
                required
                rows={4}
                className="field-control"
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <label className="text-sm font-medium">标签（逗号分隔）</label>
              <input
                type="text"
                value={formData.tags}
                onChange={(e) => setFormData((prev) => ({ ...prev, tags: e.target.value }))}
                placeholder="tag1, tag2, tag3"
                className="field-control"
              />
            </div>
          </div>
          <div className="mt-4 flex gap-2">
            <button
              type="submit"
              disabled={saving}
              className="primary-button"
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
              className="secondary-button"
            >
              取消
            </button>
          </div>
        </form>
      )}

      <div className="apple-surface p-5 sm:p-7">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-secondary">
              <Brain className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">记忆列表</h2>
              <p className="text-sm text-muted-foreground">共 {total} 条记忆</p>
            </div>
          </div>
        </div>

        {filteredMemories.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground">
            <Brain className="mx-auto mb-3 h-10 w-10 opacity-50" />
            <p>暂无记忆</p>
            <p className="mt-1 text-sm">点击"新建记忆"创建第一条记录</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredMemories.map((memory) => (
              <div
                key={memory.id}
                className="rounded-2xl border border-black/[0.055] bg-secondary/35 p-4 transition-colors hover:bg-secondary/55 sm:p-5"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-medium">{memory.subject}</h3>
                      <span
                        className={cn(
                          "rounded-md px-2 py-0.5 text-xs font-medium",
                          TYPE_COLORS[memory.memory_type] || "text-gray-600 bg-gray-50"
                        )}
                      >
                        {TYPE_LABELS[memory.memory_type] || memory.memory_type}
                      </span>
                      <span
                        className={cn(
                          "rounded-md px-2 py-0.5 text-xs font-medium",
                          STATUS_COLORS[memory.status] || "text-gray-600 bg-gray-50"
                        )}
                      >
                        {STATUS_LABELS[memory.status] || memory.status}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">{memory.content}</p>
                    {editingId === memory.id && (
                      <div className="mt-3 rounded-xl border border-primary/15 bg-white p-3">
                        <label className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                          修正 Agent 对你的理解
                        </label>
                        <textarea
                          className="field-control mt-2 min-h-20 resize-y"
                          value={editContent}
                          onChange={(event) => setEditContent(event.target.value)}
                        />
                        <div className="mt-2 flex flex-wrap items-end gap-2">
                          <div>
                            <label className="text-[10px] text-muted-foreground">置信度</label>
                            <input
                              className="field-control mt-1 w-24"
                              type="number"
                              min="0"
                              max="1"
                              step="0.05"
                              value={editConfidence}
                              onChange={(event) => setEditConfidence(event.target.value)}
                            />
                          </div>
                          <button
                            className="primary-button"
                            disabled={!editContent.trim() || saving}
                            onClick={() => {
                              void (async () => {
                                const updated = await updateMemory(memory.id, {
                                  content: editContent.trim(),
                                  confidence: Number(editConfidence),
                                })
                                if (updated) setEditingId(null)
                              })()
                            }}
                          >
                            <Save className="h-3.5 w-3.5" />
                            保存修正
                          </button>
                          <button className="secondary-button" onClick={() => setEditingId(null)}>
                            <X className="h-3.5 w-3.5" />
                            取消
                          </button>
                        </div>
                      </div>
                    )}
                    {memory.summary && (
                      <div className="mt-2 flex items-center gap-2 rounded-lg bg-primary/5 p-2">
                        <Sparkles className="h-3 w-3 text-primary" />
                        <p className="text-xs text-primary">{memory.summary}</p>
                      </div>
                    )}
                    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                      <span>重要性: {memory.importance}</span>
                      <span>置信度: {memory.confidence}</span>
                      <span>作用域: {memory.scope}</span>
                      {memory.tags.length > 0 && (
                        <div className="flex items-center gap-1">
                          <Tag className="h-3 w-3" />
                          {memory.tags.join(", ")}
                        </div>
                      )}
                      <span>
                        {new Date(memory.created_at).toLocaleString("zh-CN")}
                      </span>
                    </div>
                  </div>

                  <div className="ml-4 flex shrink-0 gap-1">
                    {memory.status !== "rejected" && editingId !== memory.id && (
                      <button
                        onClick={() => {
                          setEditingId(memory.id)
                          setEditContent(memory.content)
                          setEditConfidence(String(memory.confidence))
                        }}
                        className="rounded-lg p-2 text-muted-foreground hover:bg-primary/10 hover:text-primary"
                        title="修正"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                    )}
                    {memory.status === "candidate" && (
                      <>
                        <button
                          onClick={() => confirmMemory(memory.id)}
                          className="rounded-lg p-2 text-green-600 hover:bg-green-50"
                          title="确认"
                        >
                          <CheckCircle className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => rejectMemory(memory.id)}
                          className="rounded-lg p-2 text-red-600 hover:bg-red-50"
                          title="拒绝"
                        >
                          <XCircle className="h-4 w-4" />
                        </button>
                      </>
                    )}
                    <button
                      onClick={() => {
                        if (confirm("确定要删除这条记忆吗？")) {
                          deleteMemory(memory.id)
                        }
                      }}
                      className="rounded-lg p-2 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      title="删除"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ProfileSnapshotPanel({
  snapshot,
  onConfirm,
  onReject,
}: {
  snapshot: UserProfileSnapshot
  onConfirm: (memoryId: string) => Promise<void>
  onReject: (memoryId: string) => Promise<void>
}) {
  return (
    <section className="apple-surface mb-6 overflow-hidden">
      <div className="grid lg:grid-cols-[minmax(230px,.55fr)_minmax(0,1.45fr)]">
        <div className="border-b border-black/[0.055] p-5 sm:p-6 lg:border-b-0 lg:border-r">
          <div className="flex items-center gap-2 text-primary">
            <ShieldCheck className="h-4 w-4" />
            <p className="eyebrow">Profile Confidence</p>
          </div>
          <div className="mt-4 flex items-end gap-2">
            <p className="text-4xl font-semibold tracking-[-0.06em]">
              {Math.round(snapshot.confidence * 100)}
            </p>
            <p className="pb-1 text-xs text-muted-foreground">/ 100 平均置信度</p>
          </div>
          <p className="mt-3 text-xs leading-5 text-muted-foreground">
            {snapshot.summary}
          </p>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            <ProfileMetric label="覆盖" value={`${Math.round(snapshot.coverage_score * 100)}%`} />
            <ProfileMetric label="已确认" value={`${Math.round(snapshot.confirmation_rate * 100)}%`} />
            <ProfileMetric label="待校准" value={`${snapshot.candidate_count}`} />
          </div>
          {snapshot.conflict_count > 0 && (
            <p className="mt-3 rounded-xl bg-warning/[0.08] px-3 py-2 text-xs text-warning">
              检测到 {snapshot.conflict_count} 组可能冲突的偏好，请检查右侧证据。
            </p>
          )}
        </div>

        <div className="p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold">Agent 目前如何理解你</p>
              <p className="mt-1 text-xs text-muted-foreground">
                展示置信度最高的画像切面；候选项需你确认后才会成为稳定事实。
              </p>
            </div>
            <span className="rounded-full bg-secondary px-2.5 py-1 text-[10px] font-medium text-muted-foreground">
              {snapshot.facets.length} 个切面
            </span>
          </div>
          {snapshot.facets.length === 0 ? (
            <div className="mt-5 rounded-2xl border border-dashed border-black/10 p-8 text-center text-sm text-muted-foreground">
              尚无画像证据。你可以导入兴趣配置，或告诉 Agent “记住我…”。
            </div>
          ) : (
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {snapshot.facets.slice(0, 8).map((facet) => (
                <article
                  key={facet.key}
                  className={cn(
                    "rounded-2xl border p-3.5",
                    facet.state === "review"
                      ? "border-warning/20 bg-warning/[0.05]"
                      : "border-black/[0.055] bg-secondary/30"
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="rounded-md bg-white px-1.5 py-0.5 text-[9px] font-semibold text-muted-foreground">
                          {profileCategoryLabel(facet.category)}
                        </span>
                        <span className={cn(
                          "rounded-md px-1.5 py-0.5 text-[9px] font-semibold",
                          facet.state === "verified"
                            ? "bg-success/10 text-success"
                            : facet.state === "review"
                              ? "bg-warning/10 text-warning"
                              : "bg-primary/10 text-primary"
                        )}>
                          {profileStateLabel(facet.state)}
                        </span>
                      </div>
                      <p className="mt-2 line-clamp-2 text-xs font-medium leading-5">{facet.value}</p>
                      <p className="mt-2 text-[10px] text-muted-foreground">
                        置信度 {Math.round(facet.confidence * 100)}% · {facet.evidence.length} 条证据
                      </p>
                    </div>
                    {facet.state === "review" && facet.memory_id && (
                      <div className="flex shrink-0 gap-1">
                        <button
                          className="rounded-lg p-1.5 text-success hover:bg-success/10"
                          onClick={() => void onConfirm(facet.memory_id as string)}
                          title="确认画像"
                        >
                          <CheckCircle className="h-3.5 w-3.5" />
                        </button>
                        <button
                          className="rounded-lg p-1.5 text-destructive hover:bg-destructive/10"
                          onClick={() => void onReject(facet.memory_id as string)}
                          title="这不是我"
                        >
                          <XCircle className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

function ProfileMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-secondary/65 px-2 py-2.5">
      <p className="text-sm font-semibold">{value}</p>
      <p className="mt-0.5 text-[9px] text-muted-foreground">{label}</p>
    </div>
  )
}

function profileCategoryLabel(category: string) {
  const labels: Record<string, string> = {
    interest: "兴趣",
    project: "项目",
    preference: "偏好",
    working_style: "工作方式",
    avoidance: "避免事项",
    goal: "目标",
  }
  return labels[category] || category
}

function profileStateLabel(state: string) {
  const labels: Record<string, string> = {
    verified: "已确认",
    inferred: "有证据",
    review: "待校准",
  }
  return labels[state] || state
}
