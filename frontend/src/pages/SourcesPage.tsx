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
    <div>
      <PageHeader
        eyebrow="Ingestion"
        title="信息源"
        description="决定哪些仓库与搜索主题值得持续进入你的知识流。"
      >
        <button
          onClick={() => setShowAdd(true)}
          className="primary-button"
        >
          <Plus className="h-4 w-4" />
          添加
        </button>
      </PageHeader>

      {error && (
        <div className="alert-panel mb-6 border-destructive/15 bg-destructive/[0.055] text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {showAdd && (
        <div className="apple-surface mb-6 p-6 sm:p-8">
          <p className="eyebrow">New Source</p>
          <h3 className="mb-6 mt-2 text-2xl font-semibold tracking-[-0.03em]">添加信息源</h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">名称</label>
                <input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="例如: React 官方仓库"
                  className="field-control"
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">模式</label>
                <select
                  value={formData.mode}
                  onChange={(e) => setFormData({ ...formData, mode: e.target.value })}
                  className="field-control"
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
                  className="field-control"
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
                    className="field-control"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">结果数量限制</label>
                  <input
                    type="number"
                    value={formData.limit}
                    onChange={(e) => setFormData({ ...formData, limit: parseInt(e.target.value) })}
                    className="field-control"
                  />
                </div>
              </div>
            )}

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={saving}
                className="primary-button"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                添加
              </button>
              <button
                type="button"
                onClick={() => setShowAdd(false)}
                className="secondary-button"
              >
                取消
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="space-y-4">
        {sources.length === 0 ? (
          <div className="empty-state">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary">
              <GitBranch className="h-6 w-6 text-muted-foreground" strokeWidth={1.6} />
            </div>
            <h2 className="mt-5 text-xl font-semibold tracking-[-0.03em]">还没有信息源</h2>
            <p className="mt-2 text-sm text-muted-foreground">添加一个仓库或搜索主题，开始构建你的知识流。</p>
          </div>
        ) : (
          sources.map((source) => (
            <div
              key={source.id}
              className="apple-surface flex flex-col gap-4 p-5 transition-transform hover:-translate-y-0.5 sm:flex-row sm:items-center sm:justify-between sm:p-6"
            >
              <div className="flex items-center gap-4">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-secondary">
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
                  className="secondary-button min-h-9 px-3 py-1.5"
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
                  className="inline-flex min-h-9 items-center gap-1 rounded-full px-3 py-1.5 text-sm font-medium text-destructive hover:bg-destructive/[0.07]"
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
