import { useState, useEffect, useCallback } from "react"
import { assetsApi, type KnowledgeAsset } from "@/api/assets"

export function useAssets() {
  const [assets, setAssets] = useState<KnowledgeAsset[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchAssets = useCallback(async (asset_type?: string, status?: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await assetsApi.getAll(asset_type, status)
      setAssets(data.assets)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败")
    } finally {
      setLoading(false)
    }
  }, [])

  const uploadAsset = useCallback(async (file: File) => {
    setUploading(true)
    setError(null)
    try {
      await assetsApi.upload(file)
      await fetchAssets()
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败")
    } finally {
      setUploading(false)
    }
  }, [fetchAssets])

  const deleteAsset = useCallback(async (asset_id: string) => {
    setError(null)
    try {
      await assetsApi.delete(asset_id)
      await fetchAssets()
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败")
    }
  }, [fetchAssets])

  useEffect(() => {
    fetchAssets()
  }, [fetchAssets])

  return {
    assets,
    loading,
    uploading,
    error,
    fetchAssets,
    uploadAsset,
    deleteAsset,
  }
}
