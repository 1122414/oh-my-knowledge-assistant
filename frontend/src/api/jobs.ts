import { api } from "./client"

export interface DashboardData {
  today_run: {
    status: string
    started_at: string | null
    fetched_count: number
    candidate_count: number
  }
  pending_candidates: number
  knowledge_count: number
  latest_notification: {
    status: string
    channel: string | null
  }
}

export interface JobRun {
  id: number
  job_type: string
  status: string
  started_at: string
  finished_at: string | null
  fetched_count: number
  candidate_count: number
  error_message: string | null
}

export interface ScheduleInfo {
  cron: string
  timezone: string
  next_run_time: string | null
  running: boolean
}

export const jobsApi = {
  getDashboard: () => api.get<DashboardData>("/jobs/dashboard"),
  getRuns: () => api.get<JobRun[]>("/jobs/runs"),
  runNow: () => api.post<unknown>("/jobs/run-now"),
  getSchedule: () => api.get<ScheduleInfo>("/jobs/schedule"),
}
