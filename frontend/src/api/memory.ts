import { api } from "./client"

export interface MemoryItem {
  id: string
  memory_type: string
  subject: string
  content: string
  scope: string
  summary: string | null
  source_type: string
  source_ref: string | null
  confidence: number
  importance: number
  status: string
  tags: string[]
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface MemoryCreateRequest {
  memory_type: string
  subject: string
  content: string
  scope?: string
  summary?: string
  source_type?: string
  source_ref?: string
  confidence?: number
  importance?: number
  status?: string
  tags?: string[]
}

export interface MemoryUpdateRequest {
  content?: string
  summary?: string
  importance?: number
  status?: string
  tags?: string[]
}

export interface MemoryListResponse {
  items: MemoryItem[]
  total: number
}

export interface MemoryProfileSummary {
  user_memories: number
  conversation_memories: number
  system_memories: number
  candidate_memories: number
}

export const memoryApi = {
  getAll: (memory_type?: string, status?: string, scope?: string, limit = 50, offset = 0) => {
    const params = new URLSearchParams()
    if (memory_type) params.append("memory_type", memory_type)
    if (status) params.append("status", status)
    if (scope) params.append("scope", scope)
    params.append("limit", String(limit))
    params.append("offset", String(offset))
    return api.get<MemoryListResponse>(`/memories?${params.toString()}`)
  },
  create: (data: MemoryCreateRequest) =>
    api.post<{ id: string; message: string }>("/memories", data),
  get: (memory_id: string) =>
    api.get<MemoryItem>(`/memories/${memory_id}`),
  update: (memory_id: string, data: MemoryUpdateRequest) =>
    api.put<{ id: string; message: string }>(`/memories/${memory_id}`, data),
  delete: (memory_id: string) =>
    api.delete<{ id: string; message: string }>(`/memories/${memory_id}`),
  confirm: (memory_id: string) =>
    api.post<{ id: string; status: string; message: string }>(`/memories/${memory_id}/confirm`),
  reject: (memory_id: string) =>
    api.post<{ id: string; status: string; message: string }>(`/memories/${memory_id}/reject`),
  getProfileSummary: () =>
    api.get<MemoryProfileSummary>("/memories/profile/summary"),
  importProfile: () =>
    api.post<{ message: string; imported: unknown }>("/memories/import-profile"),
}
