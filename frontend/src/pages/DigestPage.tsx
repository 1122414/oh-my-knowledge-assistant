import { Bookmark, EyeOff, ThumbsDown, Clock, Loader2, AlertCircle, ExternalLink, Newspaper, CheckSquare, Square, X } from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import { useCandidates } from "@/hooks/use-candidates"

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
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Digest" description="每日推荐内容" />

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {candidates.length > 0 && (
        <div className="flex items-center gap-3">
          <button
            onClick={allSelected ? clearSelection : selectAll}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent"
          >
            {allSelected ? (
              <CheckSquare className="h-4 w-4" />
            ) : (
              <Square className="h-4 w-4" />
            )}
            {allSelected ? "取消全选" : "全选"}
          </button>
        </div>
      )}

      <div className="space-y-4">
        {candidates.length === 0 ? (
          <div className="rounded-2xl border border-border bg-card p-12 text-center shadow-sm">
            <Newspaper className="mx-auto h-12 w-12 text-muted-foreground" />
            <p className="mt-4 text-muted-foreground">暂无推荐内容，请先运行一次抓取任务</p>
          </div>
        ) : (
          candidates.map((candidate) => {
            const isSelected = selectedIds.has(candidate.id)
            return (
              <div
                key={candidate.id}
                className={`rounded-2xl border bg-card p-6 shadow-sm transition-colors ${
                  isSelected ? "border-primary/50 bg-primary/5" : "border-border"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3 flex-1">
                    <button
                      onClick={() => toggleSelection(candidate.id)}
                      className="mt-1 flex-shrink-0 text-muted-foreground hover:text-primary"
                    >
                      {isSelected ? (
                        <CheckSquare className="h-5 w-5 text-primary" />
                      ) : (
                        <Square className="h-5 w-5" />
                      )}
                    </button>

                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                          {candidate.item_type}
                        </span>
                        {candidate.source_name && (
                          <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                            {candidate.source_name}
                          </span>
                        )}
                      </div>

                      <a
                        href={candidate.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-2 inline-flex items-center gap-1 text-lg font-semibold hover:text-primary"
                      >
                        {candidate.title}
                        <ExternalLink className="h-4 w-4" />
                      </a>

                      {candidate.summary && (
                        <p className="mt-2 text-sm text-muted-foreground">
                          {candidate.summary}
                        </p>
                      )}

                      {candidate.score_detail && (
                        <div className="mt-3 rounded-lg bg-muted/50 p-3">
                          <p className="text-sm font-medium">
                            评分: {candidate.score.toFixed(2)}
                          </p>
                          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                            {[
                              ["interest_score", "兴趣匹配", 0.30],
                              ["project_score", "项目相关", 0.20],
                              ["source_quality_score", "源头质量", 0.25],
                              ["freshness_score", "新鲜度", 0.15],
                              ["popularity_score", "热度", 0.10],
                            ].map(([key, label, weight]) => {
                              const val = typeof candidate.score_detail?.[key] === "number"
                                ? (candidate.score_detail[key] as number).toFixed(2)
                                : "0.00"
                              const pct = `${(Number(weight) * 100).toFixed(0)}%`
                              return (
                                <div key={key} className="flex items-center gap-1">
                                  <span>{label}</span>
                                  <span className="font-mono font-medium">{val}</span>
                                  <span className="opacity-50">({pct})</span>
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )}

                      {candidate.recommendation_reason && (
                        <div className="mt-3 rounded-lg bg-accent/50 p-3">
                          <p className="text-sm">
                            <span className="font-medium">推荐理由: </span>
                            {candidate.recommendation_reason}
                          </p>
                        </div>
                      )}

                      {(candidate.matched_interests.length > 0 || candidate.matched_projects.length > 0) && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {candidate.matched_interests.map((interest) => (
                            <span
                              key={interest}
                              className="rounded-md bg-secondary px-2 py-0.5 text-xs"
                            >
                              {interest}
                            </span>
                          ))}
                          {candidate.matched_projects.map((project) => (
                            <span
                              key={project}
                              className="rounded-md bg-secondary px-2 py-0.5 text-xs"
                            >
                              {project}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="mt-4 flex gap-2">
                  <button
                    onClick={() => handleAction(candidate.id, "save")}
                    disabled={actionLoading === candidate.id}
                    className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
                  >
                    <Bookmark className="h-3.5 w-3.5" />
                    收藏
                  </button>
                  <button
                    onClick={() => handleAction(candidate.id, "ignore")}
                    disabled={actionLoading === candidate.id}
                    className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
                  >
                    <EyeOff className="h-3.5 w-3.5" />
                    忽略
                  </button>
                  <button
                    onClick={() => handleAction(candidate.id, "dislike")}
                    disabled={actionLoading === candidate.id}
                    className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 disabled:opacity-50"
                  >
                    <ThumbsDown className="h-3.5 w-3.5" />
                    不感兴趣
                  </button>
                  <button
                    onClick={() => handleAction(candidate.id, "readLater")}
                    disabled={actionLoading === candidate.id}
                    className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
                  >
                    <Clock className="h-3.5 w-3.5" />
                    稍后阅读
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>

      {selectedCount > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 rounded-xl border border-primary/30 bg-card px-5 py-3 shadow-lg">
          <span className="text-sm font-medium">
            已选 {selectedCount} 项
          </span>
          <button
            onClick={() => clearSelection()}
            className="rounded-lg p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
          <div className="mx-1 h-5 w-px bg-border" />
          <button
            onClick={() => batchAction("confirm")}
            className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Bookmark className="h-3.5 w-3.5" />
            批量收藏
          </button>
          <button
            onClick={() => batchAction("ignore")}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent"
          >
            <EyeOff className="h-3.5 w-3.5" />
            批量忽略
          </button>
        </div>
      )}
    </div>
  )
}
