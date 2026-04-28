import { api } from "./client"

export interface Source {
  id: string
  source_type: string
  name: string
  enabled: boolean
  mode: string
  repo_full_name: string | null
  query: string | null
  limit: number
  weight: number
  last_fetched_at: string | null
}

export interface CreateSourceRequest {
  id: string
  source_type?: string
  name: string
  enabled?: boolean
  mode: string
  repo_full_name?: string | null
  query?: string | null
  limit?: number
  weight?: number
}

export const sourcesApi = {
  getAll: () => api.get<Source[]>("/sources"),
  create: (data: CreateSourceRequest) => api.post<{ id: string; message: string }>("/sources", data),
  update: (id: string, data: Partial<CreateSourceRequest>) =>
    api.put<{ id: string; message: string }>(`/sources/${id}`, data),
  delete: (id: string) => api.delete<{ id: string; message: string }>(`/sources/${id}`),
  run: (id: string) => api.post<{ source_id: string; fetched_count: number }>(`/sources/${id}/run`),
}
