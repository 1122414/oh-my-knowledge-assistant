import { api } from "./client"

export interface SettingsData {
  [key: string]: string | number | boolean | null
}

export const settingsApi = {
  getAll: () => api.get<{ settings: SettingsData }>("/settings"),
  update: (data: SettingsData) => api.put<{ updated: string[]; message: string }>("/settings", data),
  updateOne: (key: string, value: unknown) =>
    api.post<{ key: string; message: string }>(`/settings/${key}`, { value }),
  testGithub: () => api.post<{ success: boolean; message: string }>("/settings/test-github"),
  testLlm: () => api.post<{ success: boolean; message: string }>("/settings/test-llm"),
  testFeishu: () => api.post<{ success: boolean; message: string }>("/integrations/feishu/send-test"),
}
