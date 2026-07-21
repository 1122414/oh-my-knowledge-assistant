import {
  Bookmark,
  EyeOff,
  ThumbsDown,
  Clock3,
  Loader2,
  AlertCircle,
  ExternalLink,
  Newspaper,
  Check,
  Minus,
  X,
  Sparkles,
} from "lucide-react"
import { Link } from "react-router-dom"
import { PageHeader } from "@/components/layout/page-header"
import { useCandidates } from "@/hooks/use-candidates"
import { cn } from "@/lib/cn"

const scoreDimensions = [
  ["interest_score", "兴趣", 0.3],
  ["project_score", "项目", 0.2],
  ["source_quality_score", "质量", 0.25],
  ["freshness_score", "新鲜", 0.15],
  ["popularity_score", "热度", 0.1],
] as const

export function DigestPage() {
  const {
    candidates,
    loading,
    actionLoading,
    error,
    handleAction,
    selectedIds,
    selectedCount,
    allSelected,
    toggleSelection,
    selectAll,
    clearSelection,
    batchAction,
  } = useCandidates()

  if (loading) {
    return <DigestSkeleton />
  }

  return (
    <div>
      <PageHeader
        eyebrow="Daily Intelligence"
        title="今日精选"
        description="从持续流入的信息中，只留下真正值得你投入注意力的部分。"
      >
        {candidates.length > 0 && (
          <button onClick={allSelected ? clearSelection : selectAll} className="secondary-button">
            {allSelected ? <Minus className="h-4 w-4" /> : <Check className="h-4 w-4" />}
            {allSelected ? "取消全选" : "选择全部"}
          </button>
        )}
      </PageHeader>

      {error && (
        <div className="alert-panel mb-6 border-destructive/15 bg-destructive/[0.055] text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {candidates.length === 0 ? (
        <div className="empty-state">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary">
            <Newspaper className="h-6 w-6 text-muted-foreground" strokeWidth={1.6} />
          </div>
          <h2 className="mt-5 text-xl font-semibold tracking-[-0.03em]">今天还没有精选内容</h2>
          <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
            运行一次知识采集，OMKA 会根据兴趣、项目、新鲜度与源头质量完成筛选。
          </p>
          <Link to="/" className="primary-button mt-6">返回概览</Link>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="apple-surface-subtle flex items-center justify-between px-4 py-3 sm:px-5">
            <div>
              <p className="text-sm font-medium">{candidates.length} 条推荐等待你的判断</p>
              <p className="mt-0.5 text-xs text-muted-foreground">反馈会持续改善后续排序</p>
            </div>
            <p className="text-xs font-medium text-muted-foreground">已选 {selectedCount}</p>
          </div>

          {candidates.map((candidate, index) => {
            const isSelected = selectedIds.has(candidate.id)
            return (
              <article
                key={candidate.id}
                className={cn(
                  "apple-surface overflow-hidden p-5 transition-all duration-300 sm:p-7",
                  isSelected
                    ? "border-primary/30 ring-4 ring-primary/[0.08]"
                    : "hover:-translate-y-0.5 hover:shadow-[0_18px_48px_rgba(0,0,0,0.075)]"
                )}
              >
                <div className="flex items-start gap-4 sm:gap-5">
                  <button
                    onClick={() => toggleSelection(candidate.id)}
                    className={cn(
                      "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border transition-all",
                      isSelected
                        ? "border-primary bg-primary text-white"
                        : "border-black/15 bg-white text-transparent hover:border-primary/50"
                    )}
                    aria-label={isSelected ? "取消选择" : "选择"}
                  >
                    <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
                  </button>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-primary">
                        {candidate.item_type}
                      </span>
                      {candidate.source_name && (
                        <>
                          <span className="h-1 w-1 rounded-full bg-border" />
                          <span className="text-xs text-muted-foreground">{candidate.source_name}</span>
                        </>
                      )}
                      <span className="ml-auto rounded-full bg-secondary px-2.5 py-1 text-xs font-semibold tabular-nums">
                        {candidate.score.toFixed(2)}
                      </span>
                    </div>

                    <a
                      href={candidate.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-3 inline-flex max-w-full items-start gap-2 text-xl font-semibold leading-7 tracking-[-0.03em] transition-colors hover:text-primary sm:text-2xl sm:leading-8"
                    >
                      <span>{candidate.title}</span>
                      <ExternalLink className="mt-1.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    </a>

                    {candidate.summary && (
                      <p className="mt-3 max-w-4xl text-[15px] leading-6 text-muted-foreground">
                        {candidate.summary}
                      </p>
                    )}

                    {candidate.recommendation_reason && (
                      <div className="mt-5 flex items-start gap-2.5 border-l-2 border-primary/45 pl-3.5">
                        <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" strokeWidth={1.8} />
                        <p className="text-sm leading-5">
                          <span className="font-medium">推荐判断：</span>
                          <span className="text-muted-foreground">{candidate.recommendation_reason}</span>
                        </p>
                      </div>
                    )}

                    {candidate.score_detail && (
                      <div className="mt-6 grid gap-3 border-t border-black/[0.055] pt-5 sm:grid-cols-5">
                        {scoreDimensions.map(([key, label, weight]) => {
                          const raw = candidate.score_detail?.[key]
                          const value = typeof raw === "number" ? raw : 0
                          const normalized = Math.max(4, Math.min(100, value * 100))
                          return (
                            <div key={key}>
                              <div className="flex items-center justify-between text-[11px]">
                                <span className="font-medium text-muted-foreground">{label}</span>
                                <span className="tabular-nums text-foreground/70">{value.toFixed(2)}</span>
                              </div>
                              <div className="mt-2 h-1 overflow-hidden rounded-full bg-secondary">
                                <div className="h-full rounded-full bg-foreground/65" style={{ width: `${normalized}%` }} />
                              </div>
                              <p className="mt-1.5 text-[10px] text-muted-foreground/60">权重 {Math.round(weight * 100)}%</p>
                            </div>
                          )
                        })}
                      </div>
                    )}

                    {(candidate.matched_interests.length > 0 || candidate.matched_projects.length > 0) && (
                      <div className="mt-5 flex flex-wrap gap-1.5">
                        {[...candidate.matched_interests, ...candidate.matched_projects].map((tag) => (
                          <span key={tag} className="rounded-full bg-secondary px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}

                    <div className="mt-6 flex flex-wrap gap-2 border-t border-black/[0.055] pt-5">
                      <ActionButton
                        icon={Bookmark}
                        label="收藏"
                        onClick={() => handleAction(candidate.id, "save")}
                        loading={actionLoading === candidate.id}
                        primary={index === 0}
                      />
                      <ActionButton
                        icon={Clock3}
                        label="稍后阅读"
                        onClick={() => handleAction(candidate.id, "readLater")}
                        loading={actionLoading === candidate.id}
                      />
                      <ActionButton
                        icon={EyeOff}
                        label="忽略"
                        onClick={() => handleAction(candidate.id, "ignore")}
                        loading={actionLoading === candidate.id}
                      />
                      <ActionButton
                        icon={ThumbsDown}
                        label="不感兴趣"
                        onClick={() => handleAction(candidate.id, "dislike")}
                        loading={actionLoading === candidate.id}
                        destructive
                      />
                    </div>
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}

      {selectedCount > 0 && (
        <div className="fixed bottom-5 left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 items-center gap-2 rounded-full border border-black/[0.08] bg-white/88 p-2 pl-4 shadow-[0_18px_50px_rgba(0,0,0,0.16)] backdrop-blur-2xl">
          <span className="mr-auto text-sm font-medium">已选 {selectedCount} 项</span>
          <button onClick={() => clearSelection()} className="icon-button h-9 w-9 border-0 bg-secondary">
            <X className="h-4 w-4" />
          </button>
          <button onClick={() => batchAction("ignore")} className="secondary-button min-h-9 px-3 py-1.5">
            批量忽略
          </button>
          <button onClick={() => batchAction("confirm")} className="primary-button min-h-9 px-3 py-1.5">
            <Bookmark className="h-3.5 w-3.5" />
            收藏
          </button>
        </div>
      )}
    </div>
  )
}

function ActionButton({
  icon: Icon,
  label,
  onClick,
  loading,
  primary = false,
  destructive = false,
}: {
  icon: typeof Bookmark
  label: string
  onClick: () => void
  loading: boolean
  primary?: boolean
  destructive?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={cn(
        "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium disabled:opacity-50",
        primary
          ? "border-primary bg-primary text-white shadow-sm hover:bg-primary/90"
          : destructive
            ? "border-transparent text-destructive hover:bg-destructive/[0.07]"
            : "border-black/[0.075] bg-white/65 text-foreground hover:border-black/[0.13] hover:bg-white"
      )}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
      {label}
    </button>
  )
}

function DigestSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-28 animate-pulse rounded-3xl bg-white/50" />
      {[0, 1, 2].map((item) => (
        <div key={item} className="apple-surface h-72 animate-pulse bg-white/60" />
      ))}
    </div>
  )
}
