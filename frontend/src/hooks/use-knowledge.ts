import { useState, useEffect, useCallback } from "react"
import { knowledgeApi, type KnowledgeItem } from "@/api/knowledge"

export function useKnowledge() {
  const [items, setItems] = useState<KnowledgeItem[]>([])
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchItems = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await knowledgeApi.getAll()
      setItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchItems()
  }, [fetchItems])

  const deleteItem = useCallback(async (id: string) => {
    setDeleting(id)
    setError(null)
    try {
      await knowledgeApi.delete(id)
      await fetchItems()
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败")
    } finally {
      setDeleting(null)
    }
  }, [fetchItems])

  return {
    items,
    loading,
    deleting,
    error,
    fetchItems,
    deleteItem,
  }
}
