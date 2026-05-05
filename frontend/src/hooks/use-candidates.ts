import { useState, useEffect, useCallback } from "react"
import { candidatesApi, type Candidate } from "@/api/candidates"

export function useCandidates() {
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const fetchCandidates = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await candidatesApi.getPending()
      setCandidates(data)
      setSelectedIds(new Set())
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCandidates()
  }, [fetchCandidates])

  const toggleSelection = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(candidates.map((c) => c.id)))
  }, [candidates])

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set())
  }, [])

  const handleAction = useCallback(async (id: string, action: "save" | "ignore" | "dislike" | "readLater") => {
    setActionLoading(id)
    setError(null)
    try {
      switch (action) {
        case "save":
          await candidatesApi.save(id)
          break
        case "ignore":
          await candidatesApi.ignore(id)
          break
        case "dislike":
          await candidatesApi.dislike(id)
          break
        case "readLater":
          await candidatesApi.readLater(id)
          break
      }
      await fetchCandidates()
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败")
    } finally {
      setActionLoading(null)
    }
  }, [fetchCandidates])

  const batchAction = useCallback(async (action: "confirm" | "ignore") => {
    if (selectedIds.size === 0) return
    setError(null)
    try {
      const ids = Array.from(selectedIds)
      if (action === "confirm") {
        await candidatesApi.batchConfirm(ids)
      } else {
        await candidatesApi.batchIgnore(ids)
      }
      await fetchCandidates()
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量操作失败")
    }
  }, [selectedIds, fetchCandidates])

  const selectedCount = selectedIds.size
  const allSelected = candidates.length > 0 && selectedCount === candidates.length

  return {
    candidates,
    loading,
    actionLoading,
    error,
    fetchCandidates,
    handleAction,
    selectedIds,
    selectedCount,
    allSelected,
    toggleSelection,
    selectAll,
    clearSelection,
    batchAction,
  }
}
