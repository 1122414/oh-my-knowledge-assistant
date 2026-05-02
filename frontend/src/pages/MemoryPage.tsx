import { useState } from "react"
import { Brain, Plus, Loader2, AlertCircle, CheckCircle, XCircle, Trash2, Sparkles, Tag, Import } from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import { useMemory } from "@/hooks/use-memory"
import { cn } from "@/lib/cn"

const TYPE_LABELS: Record<string, string> = {
  user: "用户画像",
  conversation: "对话记忆",
  system: "系统知识",
}

const TYPE_COLORS: Record<string, string> = {
  user: "text-blue-600 bg-blue-50",
  conversation: "text-purple-600 bg-purple-50",
  system: "text-green-600 bg-green-50",
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
    loading,
    saving,
    error,
    createMemory,
    confirmMemory,
    rejectMemory,
    deleteMemory,
    importProfile,
  } = useMemory()

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [filterType, setFilterType] = useState("")
  const [filterStatus, setFilterStatus] = useState("")
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
    <div className="space-y-6">
      <PageHeader
        title="记忆管理"
        description="管理系统记忆、用户画像和对话记忆"
      />

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {profile && (
        <div className="grid gap-4 sm:grid-cols-4">
          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <p className="text-sm text-muted-foreground">用户画像</p>
            <p className="mt-1 text-2xl font-semibold">{profile.user_memories}</p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <p className="text-sm text-muted-foreground">对话记忆</p>
            <p className="mt-1 text-2xl font-semibold">{profile.conversation_memories}</p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <p className="text-sm text-muted-foreground">系统知识</p>
            <p className="mt-1 text-2xl font-semibold">{profile.system_memories}</p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <p className="text-sm text-muted-foreground">候选记忆</p>
            <p className="mt-1 text-2xl font-semibold">{profile.candidate_memories}</p>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">所有类型</option>
            <option value="user">用户画像</option>
            <option value="conversation">对话记忆</option>
            <option value="system">系统知识</option>
          </select>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
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
              className="rounded-lg border border-border px-3 py-2 text-sm hover:bg-accent"
            >
              清除筛选
            </button>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => importProfile()}
            disabled={saving}
            className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50"
          >
            <Import className="h-4 w-4" />
            导入画像
          </button>
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            新建记忆
          </button>
        </div>
      </div>

      {showCreateForm && (
        <form onSubmit={handleCreate} className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">类型</label>
              <select
                value={formData.memory_type}
                onChange={(e) => setFormData((prev) => ({ ...prev, memory_type: e.target.value }))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
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
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">作用域</label>
              <input
                type="text"
                value={formData.scope}
                onChange={(e) => setFormData((prev) => ({ ...prev, scope: e.target.value }))}
                placeholder="global"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
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
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
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
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <label className="text-sm font-medium">标签（逗号分隔）</label>
              <input
                type="text"
                value={formData.tags}
                onChange={(e) => setFormData((prev) => ({ ...prev, tags: e.target.value }))}
                placeholder="tag1, tag2, tag3"
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

      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
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
                className="rounded-xl border border-border bg-background p-4"
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
