import { api } from "./client"

export interface KnowledgeItem {
  id: string
  title: string
  url: string
  item_type: string
  tags: string[]
  created_at: string
}

export interface KnowledgeDetail extends KnowledgeItem {
  content: string
  summary: string | null
  item_metadata: Record<string, unknown>
}

export const knowledgeApi = {
  getAll: () => api.get<KnowledgeItem[]>("/knowledge"),
  getById: (id: string) => api.get<KnowledgeDetail>(`/knowledge/${id}`),
  delete: (id: string) => api.delete<{ id: string; message: string }>(`/knowledge/${id}`),
}
