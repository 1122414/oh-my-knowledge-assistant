import { useState, useEffect, useCallback } from "react"
import { settingsApi, type SettingsData } from "@/api/settings"

export function useSettings() {
  const [settings, setSettings] = useState<SettingsData>({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{ type: string; success: boolean; message: string } | null>(null)

  const fetchSettings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await settingsApi.getAll()
      setSettings(data.settings)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载配置失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  const updateSettings = useCallback(async (newSettings: SettingsData) => {
    setSaving(true)
    setError(null)
    try {
      await settingsApi.update(newSettings)
      await fetchSettings()
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存配置失败")
    } finally {
      setSaving(false)
    }
  }, [fetchSettings])

  const testConnection = useCallback(async (type: "github" | "llm" | "feishu") => {
    setTesting(type)
    setTestResult(null)
    setError(null)
    try {
      let result
      switch (type) {
        case "github":
          result = await settingsApi.testGithub()
          break
        case "llm":
          result = await settingsApi.testLlm()
          break
        case "feishu":
          result = await settingsApi.testFeishu()
          break
      }
      setTestResult({ type, success: result.success, message: result.message })
    } catch (err) {
      setError(err instanceof Error ? err.message : "测试失败")
    } finally {
      setTesting(null)
    }
  }, [])

  return {
    settings,
    loading,
    saving,
    testing,
    error,
    testResult,
    updateSettings,
    testConnection,
    fetchSettings,
  }
}
