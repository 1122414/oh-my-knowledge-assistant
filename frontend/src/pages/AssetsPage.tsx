import { useState, useRef } from "react"
import { FolderOpen, Upload, Trash2, Loader2, AlertCircle, FileText, Image, File } from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import { useAssets } from "@/hooks/use-assets"
import { cn } from "@/lib/cn"

const TYPE_ICONS: Record<string, React.ElementType> = {
  image: Image,
  pdf: FileText,
  document: FileText,
}

const TYPE_LABELS: Record<string, string> = {
  image: "图片",
  pdf: "PDF",
  document: "文档",
  sheet: "表格",
  ppt: "演示文稿",
  webpage: "网页",
  text: "文本",
}

const STATUS_LABELS: Record<string, string> = {
  uploaded: "已上传",
  processing: "处理中",
  processed: "已处理",
  failed: "失败",
  archived: "已归档",
}

const STATUS_COLORS: Record<string, string> = {
  uploaded: "text-blue-600 bg-blue-50",
  processing: "text-yellow-600 bg-yellow-50",
  processed: "text-green-600 bg-green-50",
  failed: "text-red-600 bg-red-50",
  archived: "text-gray-600 bg-gray-50",
}

function formatSize(bytes: number | null): string {
  if (bytes === null) return "未知"
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function AssetsPage() {
  const { assets, loading, uploading, error, uploadAsset, deleteAsset } = useAssets()
  const [filterType, setFilterType] = useState("")
  const [filterStatus, setFilterStatus] = useState("")
  const fileInputRef = useRef<HTMLInputElement>(null)

  const filteredAssets = assets.filter((asset) => {
    if (filterType && asset.asset_type !== filterType) return false
    if (filterStatus && asset.status !== filterStatus) return false
    return true
  })

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    await uploadAsset(file)
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  if (loading && assets.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="资产管理"
        description="管理上传的多模态知识资产"
      />

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">所有类型</option>
            <option value="image">图片</option>
            <option value="pdf">PDF</option>
            <option value="document">文档</option>
            <option value="sheet">表格</option>
            <option value="text">文本</option>
          </select>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">所有状态</option>
            <option value="uploaded">已上传</option>
            <option value="processing">处理中</option>
            <option value="processed">已处理</option>
            <option value="failed">失败</option>
            <option value="archived">已归档</option>
          </select>
          {(filterType || filterStatus) && (
            <button
              onClick={() => {
                setFilterType("")
                setFilterStatus("")
              }}
              className="rounded-lg border border-border px-3 py-2 text-sm hover:bg-accent"
            >
              清除筛选
            </button>
          )}
        </div>
        <div>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            上传文件
          </button>
        </div>
      </div>

      {filteredAssets.length === 0 ? (
        <div className="rounded-2xl border border-border bg-card p-12 text-center shadow-sm">
          <FolderOpen className="mx-auto mb-3 h-10 w-10 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">暂无资产</p>
          <p className="mt-1 text-sm text-muted-foreground">上传文件或调整筛选条件</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredAssets.map((asset) => {
            const Icon = TYPE_ICONS[asset.asset_type] || File
            return (
              <div
                key={asset.id}
                className="rounded-2xl border border-border bg-card p-5 shadow-sm transition-shadow hover:shadow-md"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium truncate">{asset.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {TYPE_LABELS[asset.asset_type] || asset.asset_type} · {formatSize(asset.size_bytes)}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      if (confirm(`确定要归档 "${asset.title}" 吗？`)) {
                        deleteAsset(asset.id)
                      }
                    }}
                    className="ml-2 rounded-lg p-2 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                <div className="mt-4 flex items-center justify-between">
                  <span
                    className={cn(
                      "rounded-md px-2 py-0.5 text-xs font-medium",
                      STATUS_COLORS[asset.status] || "text-gray-600 bg-gray-50"
                    )}
                  >
                    {STATUS_LABELS[asset.status] || asset.status}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {new Date(asset.created_at).toLocaleDateString("zh-CN")}
                  </span>
                </div>

                {asset.extracted_text && (
                  <div className="mt-3 rounded-lg bg-muted p-3">
                    <p className="text-xs text-muted-foreground line-clamp-3">{asset.extracted_text}</p>
                  </div>
                )}

                {asset.summary && (
                  <div className="mt-2 rounded-lg bg-primary/5 p-3">
                    <p className="text-xs text-primary">{asset.summary}</p>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
