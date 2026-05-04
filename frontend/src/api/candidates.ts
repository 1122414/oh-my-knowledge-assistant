import { api } from "./client"

export interface Candidate {
  id: string
  normalized_item_id: string
  title: string
  url: string
  item_type: string
  score: number
  score_detail: Record<string, number | string[]> | null
  summary: string | null
  recommendation_reason: string | null
  status: string
  matched_interests: string[]
  matched_projects: string[]
  source_name: string
  created_at: string
}

export interface BatchResult {
  confirmed?: number
  ignored?: number
  not_found: number
}

export const candidatesApi = {
  getAll: (status?: string) => {
    const path = status ? `/candidates?status=${status}` : "/candidates"
    return api.get<Candidate[]>(path)
  },
  getPending: () => api.get<Candidate[]>("/candidates?status=pending"),
  save: (id: string) => api.post<{ id: string; status: string }>(`/candidates/${id}/confirm`),
  ignore: (id: string) => api.post<{ id: string; status: string }>(`/candidates/${id}/ignore`),
  dislike: (id: string) => api.post<{ id: string; status: string }>(`/candidates/${id}/dislike`),
  readLater: (id: string) => api.post<{ id: string; status: string }>(`/candidates/${id}/read-later`),
  batchConfirm: (ids: string[]) => api.post<BatchResult>("/candidates/batch/confirm", { ids }),
  batchIgnore: (ids: string[]) => api.post<BatchResult>("/candidates/batch/ignore", { ids }),
}
