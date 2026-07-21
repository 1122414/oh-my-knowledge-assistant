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
    <div>
      <PageHeader
        eyebrow="Reading Queue"
        title="稍后阅读"
        description="为需要更完整时间与注意力的内容保留一个安静队列。"
      />

      {error && (
        <div className="alert-panel mb-6 border-destructive/15 bg-destructive/[0.055] text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="space-y-4">
        {items.length === 0 ? (
          <div className="empty-state">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary">
              <Clock className="h-6 w-6 text-muted-foreground" strokeWidth={1.6} />
            </div>
            <h2 className="mt-5 text-xl font-semibold tracking-[-0.03em]">阅读队列是空的</h2>
            <p className="mt-2 text-sm text-muted-foreground">在今日精选中标记“稍后阅读”的内容会来到这里。</p>
          </div>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className="apple-surface flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6"
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
                  className="primary-button min-h-9 px-3 py-1.5"
                >
                  <Bookmark className="h-3.5 w-3.5" />
                  收藏
                </button>
                <button
                  onClick={() => handleAction(item.id, "ignore")}
                  disabled={actionLoading === item.id}
                  className="inline-flex min-h-9 items-center gap-1 rounded-full px-3 py-1.5 text-sm font-medium text-destructive hover:bg-destructive/[0.07] disabled:opacity-50"
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
