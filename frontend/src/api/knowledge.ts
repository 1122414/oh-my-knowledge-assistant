import { api } from "./client"

export interface KnowledgeItem {
  id: string
  title: string
  url: string
  item_type: string
  tags: string[]
  created_at: string
}

export const knowledgeApi = {
  getAll: () => api.get<KnowledgeItem[]>("/knowledge"),
  delete: (id: string) => api.delete<{ id: string; message: string }>(`/knowledge/${id}`),
}
