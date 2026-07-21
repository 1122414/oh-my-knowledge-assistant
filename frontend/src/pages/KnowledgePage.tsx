import { Trash2, ExternalLink, Library, Loader2, AlertCircle, ArrowUpRight } from "lucide-react"
import { Link } from "react-router-dom"
import { PageHeader } from "@/components/layout/page-header"
import { useKnowledge } from "@/hooks/use-knowledge"

export function KnowledgePage() {
  const { items, loading, deleting, error, deleteItem } = useKnowledge()

  if (loading) {
    return <ListSkeleton />
  }

  return (
    <div>
      <PageHeader
        eyebrow="Knowledge Library"
        title="知识库"
        description="被你确认过的内容会在这里形成长期、可检索、可引用的知识资产。"
      >
        <Link to="/digest" className="secondary-button">
          发现新内容
          <ArrowUpRight className="h-4 w-4" />
        </Link>
      </PageHeader>

      {error && (
        <div className="alert-panel mb-6 border-destructive/15 bg-destructive/[0.055] text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {items.length === 0 ? (
        <div className="empty-state">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary">
            <Library className="h-6 w-6 text-muted-foreground" strokeWidth={1.6} />
          </div>
          <h2 className="mt-5 text-xl font-semibold tracking-[-0.03em]">知识库还是空的</h2>
          <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
            在今日精选中收藏内容后，它会带着摘要、标签和来源沉淀到这里。
          </p>
          <Link to="/digest" className="primary-button mt-6">浏览今日精选</Link>
        </div>
      ) : (
        <section className="apple-surface overflow-hidden">
          <div className="flex items-center justify-between border-b border-black/[0.055] px-5 py-4 sm:px-7">
            <div>
              <h2 className="text-sm font-semibold">全部知识</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">共 {items.length} 条长期知识</p>
            </div>
            <span className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-muted-foreground">
              按最新收藏排序
            </span>
          </div>

          <div className="divide-y divide-black/[0.055]">
            {items.map((item, index) => (
              <article
                key={item.id}
                className="group flex items-start gap-4 px-5 py-5 transition-colors hover:bg-black/[0.012] sm:px-7 sm:py-6"
              >
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold tabular-nums text-muted-foreground">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div className="min-w-0 flex-1">
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex max-w-full items-start gap-2 text-[15px] font-semibold leading-6 tracking-[-0.015em] hover:text-primary sm:text-base"
                  >
                    <span>{item.title}</span>
                    <ExternalLink className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  </a>
                  {item.tags.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {item.tags.map((tag) => (
                        <span key={tag} className="rounded-full bg-secondary px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => deleteItem(item.id)}
                  disabled={deleting === item.id}
                  className="icon-button h-9 w-9 shrink-0 border-0 bg-transparent text-muted-foreground/65 opacity-70 hover:bg-destructive/[0.07] hover:text-destructive group-hover:opacity-100 disabled:opacity-30"
                  aria-label={`删除 ${item.title}`}
                >
                  {deleting === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                </button>
              </article>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function ListSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-28 animate-pulse rounded-3xl bg-white/50" />
      <div className="apple-surface h-[420px] animate-pulse bg-white/60" />
    </div>
  )
}
