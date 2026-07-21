import { api } from "./client"

export type AgentRunStatus =
  | "running"
  | "success"
  | "completed"
  | "degraded"
  | "needs_confirm"
  | "failed"
  | "error"

export interface AgentRunSummary {
  id: number
  conversation_id: string
  user_external_id: string
  channel: string
  user_message: string
  answer_preview: string
  model: string
  status: AgentRunStatus | string
  latency_ms: number
  created_at: string
}

export interface AgentStep {
  id: number
  step_index: number
  step_type: string
  tool_name: string | null
  input_json: Record<string, unknown>
  output_json: Record<string, unknown>
  status: string
  latency_ms: number
  error_message: string | null
  created_at: string
}

export interface AgentRunDetail extends AgentRunSummary {
  answer: string
  used_context_json: Record<string, unknown>
  error_message: string | null
  steps: AgentStep[]
}

export interface AgentRunStartResult {
  run_id: number
  status: string
}

export interface AgentEvaluation {
  run_id: number
  score: number
  passed: boolean
  step_count: number
  tool_call_count: number
  failed_tool_count: number
  denied_tool_count: number
  has_grounding_citation: boolean
  has_task_brief: boolean
  trace_complete: boolean
  findings: string[]
}

export type AgentTaskIntent =
  | "retrieve"
  | "compare"
  | "summarize"
  | "organize"
  | "monitor"
  | "act"
  | "configure"
  | "converse"

export interface AgentTaskBrief {
  intent: AgentTaskIntent
  goal: string
  entities: string[]
  constraints: string[]
  required_context: string[]
  expected_output: string
  risk: "safe" | "sensitive" | "destructive"
  confidence: number
  needs_clarification: boolean
  clarification_question: string | null
  success_criteria: string[]
}

export interface AgentHarnessScenario {
  name: string
  passed: boolean
  findings: string[]
}

export interface AgentHarnessSummary {
  health_score: number
  sample_size: number
  scenario_count: number
  scenario_pass_rate: number
  completion_rate: number
  trace_coverage: number
  understanding_coverage: number
  grounding_rate: number
  degraded_rate: number
  p50_latency_ms: number
  p95_latency_ms: number
  findings: string[]
  scenario_results: AgentHarnessScenario[]
  generated_at: string
}

export interface AgentTestResult {
  answer: string
  used_context: Array<Record<string, unknown>>
  suggested_actions: string[]
  status: string
  run_id: number | null
}

export interface AgentGoal {
  id: string
  owner_external_id: string
  conversation_id: string
  objective: string
  status: string
  schedule_cron: string | null
  allowed_tools: string[]
  max_steps: number
  last_run_id: number | null
  last_result_preview: string
  last_error: string | null
  last_run_at: string | null
  created_at: string
  updated_at: string
}

export interface AgentGoalCreate {
  owner_external_id: string
  conversation_id: string
  objective: string
  schedule_cron?: string | null
  allowed_tools?: string[]
  max_steps?: number
}

export const agentApi = {
  understand: (message: string) =>
    api.post<AgentTaskBrief>("/agent/understand", { message }),
  getHarnessSummary: (limit = 50) =>
    api.get<AgentHarnessSummary>(`/agent/harness/summary?limit=${limit}`),
  test: (message: string) =>
    api.post<AgentTestResult>("/agent/test", { message }),
  startRun: (
    message: string,
    conversationId: string,
    userExternalId: string
  ) =>
    api.post<AgentRunStartResult>("/agent/runs", {
      message,
      conversation_id: conversationId,
      user_external_id: userExternalId,
    }),
  getRuns: (limit = 50) =>
    api.get<AgentRunSummary[]>(`/agent/runs?limit=${limit}`),
  getRun: (runId: number) =>
    api.get<AgentRunDetail>(`/agent/runs/${runId}`),
  replayRun: (runId: number) =>
    api.post<AgentRunStartResult>(`/agent/runs/${runId}/replay`),
  evaluateRun: (runId: number) =>
    api.get<AgentEvaluation>(`/agent/runs/${runId}/evaluation`),
  getGoals: (ownerExternalId?: string) =>
    api.get<AgentGoal[]>(
      `/agent-goals${ownerExternalId ? `?owner_external_id=${encodeURIComponent(ownerExternalId)}` : ""}`
    ),
  createGoal: (data: AgentGoalCreate) =>
    api.post<AgentGoal>("/agent-goals", data),
  runGoal: (goalId: string) =>
    api.post<AgentGoal>(`/agent-goals/${goalId}/run`),
  updateGoalStatus: (goalId: string, status: "active" | "paused") =>
    api.put<AgentGoal>(`/agent-goals/${goalId}/status`, { status }),
  deleteGoal: (goalId: string) =>
    api.delete<{ deleted: boolean; id: string }>(`/agent-goals/${goalId}`),
}
