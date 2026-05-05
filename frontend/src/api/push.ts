import { api } from "./client"

export interface PushPolicy {
  id: string
  name: string
  enabled: boolean
  channel: string
  trigger_type: string
  threshold: number | null
  quiet_hours_json: Record<string, unknown>
  max_per_day: number
  metadata_json: Record<string, unknown>
}

export interface PushEvent {
  id: number
  policy_id: string
  channel: string
  target_id: string
  title: string
  content: string
  status: string
  reason: string | null
  related_candidate_id: string | null
  related_memory_id: string | null
  created_at: string
  sent_at: string | null
  response_json: Record<string, unknown>
}

export interface PushStatus {
  today_pushes: number
  max_per_day_default: number
}

export interface CreatePushPolicyRequest {
  id: string
  name: string
  trigger_type: string
  threshold?: number
  max_per_day?: number
}

interface UpdatePushPolicyRequest {
  enabled?: boolean
  threshold?: number
  max_per_day?: number
}

export const pushApi = {
  getPolicies: (enabled_only = false) =>
    api.get<{ policies: PushPolicy[] }>(`/push/policies?enabled_only=${enabled_only}`),
  createPolicy: (data: CreatePushPolicyRequest) =>
    api.post<{ id: string; message: string }>("/push/policies", data),
  updatePolicy: (policy_id: string, data: UpdatePushPolicyRequest) =>
    api.put<{ id: string; message: string }>(`/push/policies/${policy_id}`, data),
  getEvents: (limit = 20) =>
    api.get<{ events: PushEvent[] }>(`/push/events?limit=${limit}`),
  getStatus: () =>
    api.get<PushStatus>("/push/status"),
}
