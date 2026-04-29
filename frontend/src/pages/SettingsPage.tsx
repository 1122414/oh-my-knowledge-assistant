import { useState } from "react"
import { Check, AlertCircle, Loader2, Globe, Bot, MessageSquare, Clock, Save } from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import { useSettings } from "@/hooks/use-settings"
import { cn } from "@/lib/cn"

interface FieldProps {
  label: string
  keyName: string
  type?: string
  placeholder?: string
  help?: string
  value: string
  onChange: (key: string, value: string) => void
}

function Field({ label, keyName, type = "text", placeholder, help, value, onChange }: FieldProps) {
  const isSecret = keyName.includes("token") || keyName.includes("key") || keyName.includes("secret")
  const displayValue = isSecret && value && !value.includes("****") ? "已配置" : value

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">{label}</label>
      <input
        type={isSecret ? "password" : type}
        value={displayValue}
        placeholder={placeholder}
        onChange={(e) => onChange(keyName, e.target.value)}
        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
      />
      {help && <p className="text-xs text-muted-foreground">{help}</p>}
    </div>
  )
}

interface SectionProps {
  title: string
  icon: React.ElementType
  children: React.ReactNode
  keys: string[]
  saving: boolean
  onSave: (keys: string[]) => void
}

function Section({ title, icon: Icon, children, keys, saving, onSave }: SectionProps) {
  return (
    <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Icon className="h-5 w-5 text-primary" />
          </div>
          <h2 className="text-lg font-semibold">{title}</h2>
        </div>
        <button
          onClick={() => onSave(keys)}
          disabled={saving}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          保存
        </button>
      </div>
      {children}
    </div>
  )
}

export function SettingsPage() {
  const {
    settings,
    loading,
    saving,
    testing,
    error,
    testResult,
    updateSettings,
    testConnection,
  } = useSettings()

  const [formData, setFormData] = useState<Record<string, string>>({})

  const handleChange = (key: string, value: string) => {
    setFormData((prev) => ({ ...prev, [key]: value }))
  }

  const handleSave = async (keys: string[]) => {
    const data: Record<string, string> = {}
    keys.forEach((key) => {
      data[key] = formData[key] ?? settings[key]?.toString() ?? ""
    })
    await updateSettings(data)
  }

  const getValue = (key: string) => formData[key] ?? settings[key]?.toString() ?? ""

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="管理应用配置和集成" />

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {testResult && (
        <div
          className={cn(
            "flex items-center gap-2 rounded-lg border p-4 text-sm",
            testResult.success
              ? "border-success/20 bg-success/10 text-success"
              : "border-destructive/20 bg-destructive/10 text-destructive"
          )}
        >
          {testResult.success ? (
            <Check className="h-4 w-4" />
          ) : (
            <AlertCircle className="h-4 w-4" />
          )}
          {testResult.message}
        </div>
      )}

      <Section
        title="GitHub"
        icon={Globe}
        keys={["github_token", "github_api_base_url"]}
        saving={saving}
        onSave={handleSave}
      >
        <div className="space-y-4">
          <Field
            label="GitHub Token"
            keyName="github_token"
            placeholder="ghp_xxxxxxxxxxxx"
            help="Personal Access Token，用于访问 GitHub API"
            value={getValue("github_token")}
            onChange={handleChange}
          />
          <Field
            label="GitHub API Base URL"
            keyName="github_api_base_url"
            placeholder="https://api.github.com"
            value={getValue("github_api_base_url")}
            onChange={handleChange}
          />
          <button
            onClick={() => testConnection("github")}
            disabled={testing === "github"}
            className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50"
          >
            {testing === "github" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Check className="h-4 w-4" />
            )}
            测试连接
          </button>
        </div>
      </Section>

      <Section
        title="LLM"
        icon={Bot}
        keys={["llm_provider", "llm_api_key", "llm_base_url", "llm_model"]}
        saving={saving}
        onSave={handleSave}
      >
        <div className="space-y-4">
          <Field
            label="Provider"
            keyName="llm_provider"
            placeholder="openai / qwen / ollama"
            value={getValue("llm_provider")}
            onChange={handleChange}
          />
          <Field
            label="API Key"
            keyName="llm_api_key"
            placeholder="sk-xxxxxxxx"
            value={getValue("llm_api_key")}
            onChange={handleChange}
          />
          <Field
            label="Base URL"
            keyName="llm_base_url"
            placeholder="https://api.openai.com/v1"
            value={getValue("llm_base_url")}
            onChange={handleChange}
          />
          <Field
            label="Model"
            keyName="llm_model"
            placeholder="gpt-4o-mini"
            value={getValue("llm_model")}
            onChange={handleChange}
          />
          <button
            onClick={() => testConnection("llm")}
            disabled={testing === "llm"}
            className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50"
          >
            {testing === "llm" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Check className="h-4 w-4" />
            )}
            测试连接
          </button>
        </div>
      </Section>

      <Section
        title="Feishu App Bot"
        icon={MessageSquare}
        keys={[
          "feishu_enabled",
          "feishu_app_id",
          "feishu_app_secret",
          "feishu_verification_token",
          "feishu_encrypt_key",
          "feishu_default_receive_id_type",
          "feishu_default_chat_id",
          "feishu_command_prefix",
          "feishu_require_mention",
          "feishu_push_digest_enabled",
          "feishu_push_digest_top_n",
          "feishu_agent_conversation_enabled",
        ]}
        saving={saving}
        onSave={handleSave}
      >
        <div className="space-y-4">
          <Field
            label="启用飞书机器人"
            keyName="feishu_enabled"
            placeholder="true / false"
            value={getValue("feishu_enabled")}
            onChange={handleChange}
          />
          <Field
            label="App ID"
            keyName="feishu_app_id"
            placeholder="cli_xxxxxxxxxxxxxxxx"
            help="飞书开放平台应用的 App ID"
            value={getValue("feishu_app_id")}
            onChange={handleChange}
          />
          <Field
            label="App Secret"
            keyName="feishu_app_secret"
            placeholder="xxxxxxxxxxxxxxxxxxxxxxxx"
            help="飞书开放平台应用的 App Secret"
            value={getValue("feishu_app_secret")}
            onChange={handleChange}
          />
          <Field
            label="Verification Token"
            keyName="feishu_verification_token"
            placeholder="可选"
            help="事件订阅验证 Token"
            value={getValue("feishu_verification_token")}
            onChange={handleChange}
          />
          <Field
            label="Encrypt Key"
            keyName="feishu_encrypt_key"
            placeholder="可选"
            help="事件订阅加密 Key"
            value={getValue("feishu_encrypt_key")}
            onChange={handleChange}
          />
          <Field
            label="默认接收者类型"
            keyName="feishu_default_receive_id_type"
            placeholder="chat_id / open_id / user_id / email"
            value={getValue("feishu_default_receive_id_type")}
            onChange={handleChange}
          />
          <Field
            label="默认群聊 ID"
            keyName="feishu_default_chat_id"
            placeholder="oc_xxxxxxxxxxxxxxxx"
            help="接收消息的默认群聊 ID"
            value={getValue("feishu_default_chat_id")}
            onChange={handleChange}
          />
          <Field
            label="命令前缀"
            keyName="feishu_command_prefix"
            placeholder="/omka"
            value={getValue("feishu_command_prefix")}
            onChange={handleChange}
          />
          <Field
            label="需要 @ 机器人"
            keyName="feishu_require_mention"
            placeholder="true / false"
            help="群聊中是否需要 @ 机器人才响应"
            value={getValue("feishu_require_mention")}
            onChange={handleChange}
          />
          <Field
            label="推送简报"
            keyName="feishu_push_digest_enabled"
            placeholder="true / false"
            value={getValue("feishu_push_digest_enabled")}
            onChange={handleChange}
          />
          <Field
            label="推送条目数"
            keyName="feishu_push_digest_top_n"
            type="number"
            placeholder="6"
            value={getValue("feishu_push_digest_top_n")}
            onChange={handleChange}
          />
          <Field
            label="启用 Agent 对话"
            keyName="feishu_agent_conversation_enabled"
            placeholder="true / false"
            help="是否启用飞书内 Agent 对话（实验功能）"
            value={getValue("feishu_agent_conversation_enabled")}
            onChange={handleChange}
          />
          <div className="flex gap-2">
            <button
              onClick={() => testConnection("feishu")}
              disabled={testing === "feishu"}
              className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50"
            >
              {testing === "feishu" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              测试连接
            </button>
          </div>
        </div>
      </Section>

      <Section
        title="Scheduler"
        icon={Clock}
        keys={["scheduler_daily_cron", "digest_top_n"]}
        saving={saving}
        onSave={handleSave}
      >
        <div className="space-y-4">
          <Field
            label="每日任务 Cron"
            keyName="scheduler_daily_cron"
            placeholder="0 9 * * *"
            help="Cron 表达式，默认每天早上 9:00"
            value={getValue("scheduler_daily_cron")}
            onChange={handleChange}
          />
          <Field
            label="Digest Top N"
            keyName="digest_top_n"
            type="number"
            placeholder="10"
            value={getValue("digest_top_n")}
            onChange={handleChange}
          />
        </div>
      </Section>
    </div>
  )
}
