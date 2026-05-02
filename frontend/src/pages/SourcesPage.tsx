import { useState } from "react"
import { Plus, Trash2, Play, Loader2, AlertCircle, GitBranch, Search } from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import { useSources } from "@/hooks/use-sources"

export function SourcesPage() {
  const { sources, loading, saving, runningId, error, createSource, deleteSource, runSource } = useSources()
  const [showAdd, setShowAdd] = useState(false)
  const [formData, setFormData] = useState({
    id: "",
    name: "",
    mode: "repo",
    repo_full_name: "",
    query: "",
    limit: 5,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const data = {
      id: formData.id || `${formData.mode}_${Date.now()}`,
      name: formData.name,
      mode: formData.mode,
      ...(formData.mode === "repo"
        ? { repo_full_name: formData.repo_full_name }
        : { query: formData.query, limit: formData.limit }),
    }
    await createSource(data)
    setShowAdd(false)
    setFormData({ id: "", name: "", mode: "repo", repo_full_name: "", query: "", limit: 5 })
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Sources" description="管理 GitHub 信息源">
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          添加
        </button>
      </PageHeader>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {showAdd && (
        <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
          <h3 className="mb-4 text-lg font-semibold">添加信息源</h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">名称</label>
                <input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="例如: React 官方仓库"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">模式</label>
                <select
                  value={formData.mode}
                  onChange={(e) => setFormData({ ...formData, mode: e.target.value })}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="repo">仓库</option>
                  <option value="search">搜索</option>
                </select>
              </div>
            </div>

            {formData.mode === "repo" ? (
              <div className="space-y-2">
                <label className="text-sm font-medium">仓库全名</label>
                <input
                  value={formData.repo_full_name}
                  onChange={(e) => setFormData({ ...formData, repo_full_name: e.target.value })}
                  placeholder="owner/repo"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                  required
                />
              </div>
            ) : (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">搜索关键词</label>
                  <input
                    value={formData.query}
                    onChange={(e) => setFormData({ ...formData, query: e.target.value })}
                    placeholder="例如: react state management"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">结果数量限制</label>
                  <input
                    type="number"
                    value={formData.limit}
                    onChange={(e) => setFormData({ ...formData, limit: parseInt(e.target.value) })}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              </div>
            )}

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={saving}
                className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                添加
              </button>
              <button
                type="button"
                onClick={() => setShowAdd(false)}
                className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-accent"
              >
                取消
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="space-y-3">
        {sources.length === 0 ? (
          <div className="rounded-2xl border border-border bg-card p-12 text-center shadow-sm">
            <GitBranch className="mx-auto h-12 w-12 text-muted-foreground" />
            <p className="mt-4 text-muted-foreground">暂无信息源，点击上方按钮添加</p>
          </div>
        ) : (
          sources.map((source) => (
            <div
              key={source.id}
              className="flex items-center justify-between rounded-2xl border border-border bg-card p-5 shadow-sm"
            >
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  {source.mode === "repo" ? (
                    <GitBranch className="h-5 w-5 text-primary" />
                  ) : (
                    <Search className="h-5 w-5 text-primary" />
                  )}
                </div>
                <div>
                  <h3 className="font-medium">{source.name}</h3>
                  <p className="text-sm text-muted-foreground">
                    {source.mode === "repo"
                      ? source.repo_full_name
                      : `搜索: ${source.query}`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => runSource(source.id)}
                  disabled={runningId === source.id}
                  className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
                >
                  {runningId === source.id ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Play className="h-3 w-3" />
                  )}
                  {runningId === source.id ? "运行中..." : "运行"}
                </button>
                <button
                  onClick={() => deleteSource(source.id)}
                  className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10"
                >
                  <Trash2 className="h-3 w-3" />
                  删除
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
