import { useState, useEffect } from "react"
import { Clock, Bookmark, Trash2, Loader2, AlertCircle } from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import { candidatesApi, type Candidate } from "@/api/candidates"

export function ReadLaterPage() {
  const [items, setItems] = useState<Candidate[]>([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchItems = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await candidatesApi.getAll("read_later")
      setItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchItems()
  }, [])

  const handleAction = async (id: string, action: "save" | "ignore") => {
    setActionLoading(id)
    setError(null)
    try {
      if (action === "save") {
        await candidatesApi.save(id)
      } else {
        await candidatesApi.ignore(id)
      }
      await fetchItems()
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败")
    } finally {
      setActionLoading(null)
    }
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
      <PageHeader title="Read Later" description="稍后阅读列表" />

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="space-y-3">
        {items.length === 0 ? (
          <div className="rounded-2xl border border-border bg-card p-12 text-center shadow-sm">
            <Clock className="mx-auto h-12 w-12 text-muted-foreground" />
            <p className="mt-4 text-muted-foreground">暂无稍后阅读内容，在 Digest 页面标记后会显示在这里</p>
          </div>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between rounded-2xl border border-border bg-card p-5 shadow-sm"
            >
              <div>
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium hover:text-primary"
                >
                  {item.title}
                </a>
                {item.summary && (
                  <p className="mt-1 text-sm text-muted-foreground">{item.summary}</p>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleAction(item.id, "save")}
                  disabled={actionLoading === item.id}
                  className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
                >
                  <Bookmark className="h-3.5 w-3.5" />
                  收藏
                </button>
                <button
                  onClick={() => handleAction(item.id, "ignore")}
                  disabled={actionLoading === item.id}
                  className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 disabled:opacity-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
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
