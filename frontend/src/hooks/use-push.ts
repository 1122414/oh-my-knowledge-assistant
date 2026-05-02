import { useState, useEffect, useCallback } from "react"
import { pushApi, type PushPolicy, type PushEvent, type PushStatus } from "@/api/push"

export function usePush() {
  const [policies, setPolicies] = useState<PushPolicy[]>([])
  const [events, setEvents] = useState<PushEvent[]>([])
  const [status, setStatus] = useState<PushStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchPolicies = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await pushApi.getPolicies(true)
      setPolicies(data.policies)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载策略失败")
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchEvents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await pushApi.getEvents(20)
      setEvents(data.events)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载事件失败")
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchStatus = useCallback(async () => {
    try {
      const data = await pushApi.getStatus()
      setStatus(data)
    } catch (err) {
      console.error("加载推送状态失败:", err)
    }
  }, [])

  const createPolicy = useCallback(async (data: { id: string; name: string; trigger_type: string; threshold?: number; max_per_day?: number }) => {
    setSaving(true)
    setError(null)
    try {
      await pushApi.createPolicy(data)
      await fetchPolicies()
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建策略失败")
    } finally {
      setSaving(false)
    }
  }, [fetchPolicies])

  const togglePolicy = useCallback(async (policy_id: string, enabled: boolean) => {
    setError(null)
    try {
      await pushApi.updatePolicy(policy_id, { enabled })
      await fetchPolicies()
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新策略失败")
    }
  }, [fetchPolicies])

  const updatePolicy = useCallback(async (policy_id: string, data: { threshold?: number; max_per_day?: number }) => {
    setSaving(true)
    setError(null)
    try {
      await pushApi.updatePolicy(policy_id, data)
      await fetchPolicies()
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新策略失败")
    } finally {
      setSaving(false)
    }
  }, [fetchPolicies])

  useEffect(() => {
    fetchPolicies()
    fetchEvents()
    fetchStatus()
  }, [fetchPolicies, fetchEvents, fetchStatus])

  return {
    policies,
    events,
    status,
    loading,
    saving,
    error,
    createPolicy,
    togglePolicy,
    updatePolicy,
    refetchPolicies: fetchPolicies,
    refetchEvents: fetchEvents,
    refetchStatus: fetchStatus,
  }
}
