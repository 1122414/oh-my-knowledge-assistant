import { useState } from "react"
import { Check, AlertCircle, Loader2, Globe, Bot, MessageSquare, Clock, Save, Brain, Zap, Bell, FolderOpen, TrendingUp, Shield } from "lucide-react"
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
  const isMasked = isSecret && value && value.includes("****")
  const [showPlain, setShowPlain] = useState(false)

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">{label}</label>
      <div className="relative">
        <input
          type={isSecret && !showPlain ? "password" : type}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(keyName, e.target.value)}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 pr-20 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
        {isSecret && (
          <button
            type="button"
            onClick={() => setShowPlain(!showPlain)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground"
          >
            {showPlain ? "隐藏" : "显示"}
          </button>
        )}
      </div>
      {isMasked && (
        <p className="text-xs text-muted-foreground">已有配置，留空则保持原值</p>
      )}
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
        title="权限管理"
        icon={Shield}
        keys={["feishu_admin_open_ids", "feishu_operator_open_ids"]}
        saving={saving}
        onSave={handleSave}
      >
        <div className="space-y-4">
          <Field
            label="管理员 open_id 列表"
            keyName="feishu_admin_open_ids"
            placeholder="ou_xxxx,ou_yyyy"
            help="admin 权限可执行所有操作，包括删除和修改敏感配置。多个用逗号分隔"
            value={getValue("feishu_admin_open_ids")}
            onChange={handleChange}
          />
          <Field
            label="操作员 open_id 列表"
            keyName="feishu_operator_open_ids"
            placeholder="ou_xxxx,ou_yyyy"
            help="operator 权限可添加信息源、管理候选、修改非敏感配置。多个用逗号分隔"
            value={getValue("feishu_operator_open_ids")}
            onChange={handleChange}
          />
        </div>
      </Section>

      <Section
        title="飞书文档/表格"
        icon={FolderOpen}
        keys={["feishu_doc_folder_token", "feishu_base_folder_token", "feishu_sheet_folder_token", "feishu_default_calendar_id"]}
        saving={saving}
        onSave={handleSave}
      >
        <div className="space-y-4">
          <Field
            label="文档默认文件夹 Token"
            keyName="feishu_doc_folder_token"
            placeholder="留空则创建在根目录"
            help="创建的飞书云文档将默认存放在此文件夹（需先在飞书中创建文件夹）"
            value={getValue("feishu_doc_folder_token")}
            onChange={handleChange}
          />
          <Field
            label="多维表格默认文件夹 Token"
            keyName="feishu_base_folder_token"
            placeholder="留空则创建在根目录"
            help="创建的多维表格将默认存放在此文件夹"
            value={getValue("feishu_base_folder_token")}
            onChange={handleChange}
          />
          <Field
            label="电子表格默认文件夹 Token"
            keyName="feishu_sheet_folder_token"
            placeholder="留空则创建在根目录"
            help="创建的电子表格将默认存放在此文件夹"
            value={getValue("feishu_sheet_folder_token")}
            onChange={handleChange}
          />
          <Field
            label="默认日历 ID"
            keyName="feishu_default_calendar_id"
            placeholder="留空则使用主日历"
            help="日历事件将默认创建到此日历。可通过飞书消息 /omka calendar list 查看可用日历"
            value={getValue("feishu_default_calendar_id")}
            onChange={handleChange}
          />
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
            help="Cron 表达式或自然语言: 每天 9:30 / 每周一 18:00 / 0 9 * * *"
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

      <Section
        title="Agent"
        icon={Bot}
        keys={[
          "omka_agent_chat_enabled",
          "omka_agent_provider",
          "omka_agent_model",
          "omka_agent_temperature",
          "omka_agent_timeout_seconds",
          "omka_agent_max_recent_messages",
          "omka_agent_max_digest_items",
          "omka_agent_max_knowledge_items",
          "omka_agent_max_candidate_items",
          "omka_agent_max_context_chars",
        ]}
        saving={saving}
        onSave={handleSave}
      >
        <div className="space-y-4">
          <Field
            label="启用 Agent 对话"
            keyName="omka_agent_chat_enabled"
            placeholder="true / false"
            value={getValue("omka_agent_chat_enabled")}
            onChange={handleChange}
          />
          <Field
            label="Agent Provider"
            keyName="omka_agent_provider"
            placeholder="openai / qwen / ollama"
            help="留空则使用全局 LLM Provider"
            value={getValue("omka_agent_provider")}
            onChange={handleChange}
          />
          <Field
            label="Agent Model"
            keyName="omka_agent_model"
            placeholder="gpt-4o-mini"
            help="留空则使用全局 LLM Model"
            value={getValue("omka_agent_model")}
            onChange={handleChange}
          />
          <Field
            label="Temperature"
            keyName="omka_agent_temperature"
            type="number"
            placeholder="0.2"
            value={getValue("omka_agent_temperature")}
            onChange={handleChange}
          />
          <Field
            label="超时（秒）"
            keyName="omka_agent_timeout_seconds"
            type="number"
            placeholder="60"
            value={getValue("omka_agent_timeout_seconds")}
            onChange={handleChange}
          />
          <Field
            label="最大最近消息数"
            keyName="omka_agent_max_recent_messages"
            type="number"
            placeholder="6"
            value={getValue("omka_agent_max_recent_messages")}
            onChange={handleChange}
          />
          <Field
            label="最大 Digest 上下文"
            keyName="omka_agent_max_digest_items"
            type="number"
            placeholder="5"
            value={getValue("omka_agent_max_digest_items")}
            onChange={handleChange}
          />
          <Field
            label="最大 Knowledge 上下文"
            keyName="omka_agent_max_knowledge_items"
            type="number"
            placeholder="5"
            value={getValue("omka_agent_max_knowledge_items")}
            onChange={handleChange}
          />
          <Field
            label="最大 Candidate 上下文"
            keyName="omka_agent_max_candidate_items"
            type="number"
            placeholder="5"
            value={getValue("omka_agent_max_candidate_items")}
            onChange={handleChange}
          />
          <Field
            label="最大上下文字数"
            keyName="omka_agent_max_context_chars"
            type="number"
            placeholder="12000"
            value={getValue("omka_agent_max_context_chars")}
            onChange={handleChange}
          />
        </div>
      </Section>

      <Section
        title="排序权重"
        icon={TrendingUp}
        keys={[
          "score_weight_interest",
          "score_weight_project",
          "score_weight_freshness",
          "score_weight_popularity",
          "freshness_decay_days",
        ]}
        saving={saving}
        onSave={handleSave}
      >
        <div className="space-y-4">
          <Field
            label="兴趣匹配权重"
            keyName="score_weight_interest"
            type="number"
            placeholder="0.40"
            help="0.0-1.0"
            value={getValue("score_weight_interest")}
            onChange={handleChange}
          />
          <Field
            label="项目相关权重"
            keyName="score_weight_project"
            type="number"
            placeholder="0.30"
            help="0.0-1.0"
            value={getValue("score_weight_project")}
            onChange={handleChange}
          />
          <Field
            label="新鲜度权重"
            keyName="score_weight_freshness"
            type="number"
            placeholder="0.15"
            help="0.0-1.0"
            value={getValue("score_weight_freshness")}
            onChange={handleChange}
          />
          <Field
            label="热度权重"
            keyName="score_weight_popularity"
            type="number"
            placeholder="0.15"
            help="0.0-1.0"
            value={getValue("score_weight_popularity")}
            onChange={handleChange}
          />
          <Field
            label="新鲜度衰减天数"
            keyName="freshness_decay_days"
            type="number"
            placeholder="7"
            value={getValue("freshness_decay_days")}
            onChange={handleChange}
          />
        </div>
      </Section>

      <Section
        title="推荐系统"
        icon={Zap}
        keys={[
          "recommendation_enabled",
          "recommendation_explanation_enabled",
          "recommendation_feedback_learning_enabled",
        ]}
        saving={saving}
        onSave={handleSave}
      >
        <div className="space-y-4">
          <Field
            label="启用推荐系统"
            keyName="recommendation_enabled"
            placeholder="true / false"
            value={getValue("recommendation_enabled")}
            onChange={handleChange}
          />
          <Field
            label="启用推荐解释"
            keyName="recommendation_explanation_enabled"
            placeholder="true / false"
            help="为每条推荐生成解释说明"
            value={getValue("recommendation_explanation_enabled")}
            onChange={handleChange}
          />
          <Field
            label="启用反馈学习"
            keyName="recommendation_feedback_learning_enabled"
            placeholder="true / false"
            help="用户反馈会影响后续推荐"
            value={getValue("recommendation_feedback_learning_enabled")}
            onChange={handleChange}
          />
        </div>
      </Section>

      <Section
        title="推送策略"
        icon={Bell}
        keys={[
          "push_high_score_threshold",
          "push_max_per_day",
          "push_quiet_hours_start",
          "push_quiet_hours_end",
        ]}
        saving={saving}
        onSave={handleSave}
      >
        <div className="space-y-4">
          <Field
            label="高价值推送阈值"
            keyName="push_high_score_threshold"
            type="number"
            placeholder="0.85"
            help="超过此分数的候选会触发即时推送"
            value={getValue("push_high_score_threshold")}
            onChange={handleChange}
          />
          <Field
            label="每日最大推送次数"
            keyName="push_max_per_day"
            type="number"
            placeholder="5"
            value={getValue("push_max_per_day")}
            onChange={handleChange}
          />
          <Field
            label="安静时间开始"
            keyName="push_quiet_hours_start"
            type="number"
            placeholder="22"
            help="小时（0-23）"
            value={getValue("push_quiet_hours_start")}
            onChange={handleChange}
          />
          <Field
            label="安静时间结束"
            keyName="push_quiet_hours_end"
            type="number"
            placeholder="8"
            help="小时（0-23）"
            value={getValue("push_quiet_hours_end")}
            onChange={handleChange}
          />
        </div>
      </Section>

      <Section
        title="记忆系统"
        icon={Brain}
        keys={[
          "memory_extraction_enabled",
          "memory_extraction_confidence_threshold",
          "memory_max_active_items",
        ]}
        saving={saving}
        onSave={handleSave}
      >
        <div className="space-y-4">
          <Field
            label="启用记忆抽取"
            keyName="memory_extraction_enabled"
            placeholder="true / false"
            help="从对话中自动抽取记忆"
            value={getValue("memory_extraction_enabled")}
            onChange={handleChange}
          />
          <Field
            label="记忆抽取置信度阈值"
            keyName="memory_extraction_confidence_threshold"
            type="number"
            placeholder="0.8"
            help="0.0-1.0"
            value={getValue("memory_extraction_confidence_threshold")}
            onChange={handleChange}
          />
          <Field
            label="最大活跃记忆数"
            keyName="memory_max_active_items"
            type="number"
            placeholder="20"
            help="Agent 上下文包含的最大记忆数"
            value={getValue("memory_max_active_items")}
            onChange={handleChange}
          />
        </div>
      </Section>

      <Section
        title="多模态资产"
        icon={FolderOpen}
        keys={[
          "asset_max_file_size_mb",
          "asset_allowed_image_types",
          "asset_allowed_document_types",
        ]}
        saving={saving}
        onSave={handleSave}
      >
        <div className="space-y-4">
          <Field
            label="最大文件大小（MB）"
            keyName="asset_max_file_size_mb"
            type="number"
            placeholder="10"
            value={getValue("asset_max_file_size_mb")}
            onChange={handleChange}
          />
          <Field
            label="允许的图片类型"
            keyName="asset_allowed_image_types"
            placeholder="jpg,jpeg,png,webp"
            value={getValue("asset_allowed_image_types")}
            onChange={handleChange}
          />
          <Field
            label="允许的文档类型"
            keyName="asset_allowed_document_types"
            placeholder="pdf,md,txt"
            value={getValue("asset_allowed_document_types")}
            onChange={handleChange}
          />
        </div>
      </Section>
    </div>
  )
}
