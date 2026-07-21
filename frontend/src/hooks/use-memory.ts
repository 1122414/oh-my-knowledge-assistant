import { useState, useEffect, useCallback } from "react"
import {
  memoryApi,
  type MemoryItem,
  type MemoryProfileSummary,
  type UserProfileSnapshot,
} from "@/api/memory"

export function useMemory() {
  const [memories, setMemories] = useState<MemoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [profile, setProfile] = useState<MemoryProfileSummary | null>(null)
  const [profileSnapshot, setProfileSnapshot] = useState<UserProfileSnapshot | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchMemories = useCallback(async (filters?: { memory_type?: string; status?: string; scope?: string }) => {
    setLoading(true)
    setError(null)
    try {
      const data = await memoryApi.getAll(
        filters?.memory_type,
        filters?.status,
        filters?.scope,
        50,
        0
      )
      setMemories(data.items)
      setTotal(data.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败")
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchProfile = useCallback(async () => {
    try {
      const [summary, snapshot] = await Promise.all([
        memoryApi.getProfileSummary(),
        memoryApi.getProfileSnapshot(),
      ])
      setProfile(summary)
      setProfileSnapshot(snapshot)
    } catch (err) {
      console.error("加载记忆画像失败:", err)
    }
  }, [])

  const createMemory = useCallback(async (data: {
    memory_type: string
    subject: string
    content: string
    scope?: string
    importance?: number
    tags?: string[]
  }) => {
    setSaving(true)
    setError(null)
    try {
      await memoryApi.create(data)
      await fetchMemories()
      await fetchProfile()
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败")
    } finally {
      setSaving(false)
    }
  }, [fetchMemories, fetchProfile])

  const confirmMemory = useCallback(async (memory_id: string) => {
    setError(null)
    try {
      await memoryApi.confirm(memory_id)
      await fetchMemories()
      await fetchProfile()
    } catch (err) {
      setError(err instanceof Error ? err.message : "确认失败")
    }
  }, [fetchMemories, fetchProfile])

  const rejectMemory = useCallback(async (memory_id: string) => {
    setError(null)
    try {
      await memoryApi.reject(memory_id)
      await fetchMemories()
      await fetchProfile()
    } catch (err) {
      setError(err instanceof Error ? err.message : "拒绝失败")
    }
  }, [fetchMemories, fetchProfile])

  const deleteMemory = useCallback(async (memory_id: string) => {
    setError(null)
    try {
      await memoryApi.delete(memory_id)
      await fetchMemories()
      await fetchProfile()
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败")
    }
  }, [fetchMemories, fetchProfile])

  const updateMemory = useCallback(async (
    memory_id: string,
    data: { content?: string; confidence?: number; importance?: number }
  ) => {
    setSaving(true)
    setError(null)
    try {
      await memoryApi.update(memory_id, data)
      await fetchMemories()
      await fetchProfile()
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新失败")
      return false
    } finally {
      setSaving(false)
    }
  }, [fetchMemories, fetchProfile])

  const importProfile = useCallback(async () => {
    setSaving(true)
    setError(null)
    try {
      await memoryApi.importProfile()
      await fetchMemories()
      await fetchProfile()
    } catch (err) {
      setError(err instanceof Error ? err.message : "导入失败")
    } finally {
      setSaving(false)
    }
  }, [fetchMemories, fetchProfile])

  useEffect(() => {
    fetchMemories()
    fetchProfile()
  }, [fetchMemories, fetchProfile])

  return {
    memories,
    total,
    profile,
    profileSnapshot,
    loading,
    saving,
    error,
    createMemory,
    confirmMemory,
    rejectMemory,
    deleteMemory,
    updateMemory,
    importProfile,
    refetch: fetchMemories,
  }
}
