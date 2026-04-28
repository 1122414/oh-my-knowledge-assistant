import { useState } from "react"
import { Check, AlertCircle, Loader2, Globe, Bot, MessageSquare, Clock, Save } from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import { useSettings } from "@/hooks/use-settings"
import { cn } from "@/lib/cn"

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

  const Section = ({
    title,
    icon: Icon,
    children,
    keys,
  }: {
    title: string
    icon: React.ElementType
    children: React.ReactNode
    keys: string[]
  }) => (
    <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Icon className="h-5 w-5 text-primary" />
          </div>
          <h2 className="text-lg font-semibold">{title}</h2>
        </div>
        <button
          onClick={() => handleSave(keys)}
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

  const Field = ({
    label,
    keyName,
    type = "text",
    placeholder,
    help,
  }: {
    label: string
    keyName: string
    type?: string
    placeholder?: string
    help?: string
  }) => {
    const value = getValue(keyName)
    const isSecret = keyName.includes("token") || keyName.includes("key") || keyName.includes("secret")
    const displayValue = isSecret && value && !value.includes("****") ? "已配置" : value

    return (
      <div className="space-y-2">
        <label className="text-sm font-medium">{label}</label>
        <input
          type={isSecret ? "password" : type}
          value={displayValue}
          placeholder={placeholder}
          onChange={(e) => handleChange(keyName, e.target.value)}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
        {help && <p className="text-xs text-muted-foreground">{help}</p>}
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
      >
        <div className="space-y-4">
          <Field
            label="GitHub Token"
            keyName="github_token"
            placeholder="ghp_xxxxxxxxxxxx"
            help="Personal Access Token，用于访问 GitHub API"
          />
          <Field
            label="GitHub API Base URL"
            keyName="github_api_base_url"
            placeholder="https://api.github.com"
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
      >
        <div className="space-y-4">
          <Field
            label="Provider"
            keyName="llm_provider"
            placeholder="openai / qwen / ollama"
          />
          <Field
            label="API Key"
            keyName="llm_api_key"
            placeholder="sk-xxxxxxxx"
          />
          <Field
            label="Base URL"
            keyName="llm_base_url"
            placeholder="https://api.openai.com/v1"
          />
          <Field
            label="Model"
            keyName="llm_model"
            placeholder="gpt-4o-mini"
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
        title="Feishu"
        icon={MessageSquare}
        keys={[
          "feishu_webhook_enabled",
          "feishu_webhook_url",
          "feishu_webhook_secret",
          "feishu_push_digest_top_n",
        ]}
      >
        <div className="space-y-4">
          <Field
            label="启用飞书推送"
            keyName="feishu_webhook_enabled"
            placeholder="true / false"
          />
          <Field
            label="Webhook URL"
            keyName="feishu_webhook_url"
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
          />
          <Field
            label="Secret"
            keyName="feishu_webhook_secret"
            placeholder="可选"
          />
          <Field
            label="推送 Top N"
            keyName="feishu_push_digest_top_n"
            type="number"
            placeholder="6"
          />
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
            测试推送
          </button>
        </div>
      </Section>

      <Section
        title="Scheduler"
        icon={Clock}
        keys={["scheduler_daily_cron", "digest_top_n"]}
      >
        <div className="space-y-4">
          <Field
            label="每日任务 Cron"
            keyName="scheduler_daily_cron"
            placeholder="0 9 * * *"
            help="Cron 表达式，默认每天早上 9:00"
          />
          <Field
            label="Digest Top N"
            keyName="digest_top_n"
            type="number"
            placeholder="10"
          />
        </div>
      </Section>
    </div>
  )
}
