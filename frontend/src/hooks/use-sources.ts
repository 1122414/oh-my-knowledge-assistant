import { useState, useEffect, useCallback } from "react"
import { sourcesApi, type Source, type CreateSourceRequest } from "@/api/sources"

export function useSources() {
  const [sources, setSources] = useState<Source[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [runningId, setRunningId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchSources = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await sourcesApi.getAll()
      setSources(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSources()
  }, [fetchSources])

  const createSource = useCallback(async (data: CreateSourceRequest) => {
    setSaving(true)
    setError(null)
    try {
      await sourcesApi.create(data)
      await fetchSources()
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败")
    } finally {
      setSaving(false)
    }
  }, [fetchSources])

  const deleteSource = useCallback(async (id: string) => {
    setError(null)
    try {
      await sourcesApi.delete(id)
      await fetchSources()
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败")
    }
  }, [fetchSources])

  const runSource = useCallback(async (id: string) => {
    setRunningId(id)
    setError(null)
    try {
      const result = await sourcesApi.run(id)
      await fetchSources()
      return result
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行失败")
      return null
    } finally {
      setRunningId(null)
    }
  }, [fetchSources])

  return {
    sources,
    loading,
    saving,
    runningId,
    error,
    createSource,
    deleteSource,
    runSource,
    fetchSources,
  }
}
