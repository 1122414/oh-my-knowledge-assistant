import { useState, useEffect, useCallback } from "react"
import { candidatesApi, type Candidate } from "@/api/candidates"

export function useCandidates() {
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchCandidates = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await candidatesApi.getPending()
      setCandidates(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCandidates()
  }, [fetchCandidates])

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

  return {
    candidates,
    loading,
    actionLoading,
    error,
    fetchCandidates,
    handleAction,
  }
}
