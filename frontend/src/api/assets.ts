import { api } from "./client"

export interface KnowledgeAsset {
  id: string
  asset_type: string
  title: string
  source_type: string
  source_ref: string | null
  file_path: string | null
  original_filename: string | null
  mime_type: string | null
  size_bytes: number | null
  content_hash: string
  status: string
  extracted_text: string | null
  summary: string | null
  created_at: string
}

export const assetsApi = {
  getAll: (asset_type?: string, status?: string) => {
    const params = new URLSearchParams()
    if (asset_type) params.append("asset_type", asset_type)
    if (status) params.append("status", status)
    const query = params.toString()
    return api.get<{ assets: KnowledgeAsset[] }>(`/assets${query ? `?${query}` : ""}`)
  },
  upload: (file: File) => {
    const formData = new FormData()
    formData.append("file", file)
    return api.postFormData<{ id: string; status: string; asset_type: string }>("/assets/upload", formData)
  },
  delete: (asset_id: string) =>
    api.delete<{ id: string; message: string }>(`/assets/${asset_id}`),
}
