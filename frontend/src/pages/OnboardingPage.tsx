import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { BookOpen, GitBranch, MessageSquare, Check, ChevronRight, ChevronLeft, Play } from "lucide-react"
import { useSettings } from "@/hooks/use-settings"
import { useSources } from "@/hooks/use-sources"

export function OnboardingPage() {
  const navigate = useNavigate()
  const { updateSettings } = useSettings()
  const { createSource } = useSources()
  const [step, setStep] = useState(0)
  const [githubToken, setGithubToken] = useState("")
  const [repoName, setRepoName] = useState("")
  const [repoFullName, setRepoFullName] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [feishuUrl, setFeishuUrl] = useState("")
  const [isComplete, setIsComplete] = useState(false)

  const steps = [
    { title: "欢迎", icon: BookOpen },
    { title: "GitHub", icon: GitBranch },
    { title: "仓库", icon: GitBranch },
    { title: "搜索", icon: GitBranch },
    { title: "飞书", icon: MessageSquare },
    { title: "完成", icon: Check },
  ]

  const handleNext = () => {
    if (step < steps.length - 1) {
      setStep(step + 1)
    }
  }

  const handleBack = () => {
    if (step > 0) {
      setStep(step - 1)
    }
  }

  const handleComplete = async () => {
    if (githubToken) {
      await updateSettings({ github_token: githubToken })
    }
    if (repoName && repoFullName) {
      await createSource({
        id: `repo_${Date.now()}`,
        name: repoName,
        mode: "repo",
        repo_full_name: repoFullName,
      })
    }
    if (searchQuery) {
      await createSource({
        id: `search_${Date.now()}`,
        name: `搜索: ${searchQuery}`,
        mode: "search",
        query: searchQuery,
      })
    }
    if (feishuUrl) {
      await updateSettings({
        feishu_webhook_enabled: true,
        feishu_webhook_url: feishuUrl,
      })
    }
    setIsComplete(true)
  }

  if (isComplete) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6 py-12">
        <div className="apple-surface max-w-lg p-10 text-center">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-success/10">
            <Check className="h-10 w-10 text-success" />
          </div>
          <h1 className="mt-6 text-3xl font-semibold tracking-[-0.04em]">配置完成</h1>
          <p className="mt-2 text-muted-foreground">
            您已完成 OMKA 的初始配置，现在可以开始使用了。
          </p>
          <button
            onClick={() => navigate("/")}
            className="primary-button mt-6"
          >
            进入 OMKA
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10 sm:p-8">
      <img
        src="/images/knowledge-flow-hero.png"
        alt=""
        className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-25"
        aria-hidden="true"
      />
      <div className="absolute inset-0 bg-white/65 backdrop-blur-[2px]" />
      <div className="relative w-full max-w-2xl">
        <div className="mb-8 flex items-center justify-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[13px] bg-foreground text-white shadow-lg">
            <BookOpen className="h-5 w-5" strokeWidth={1.8} />
          </div>
          <div>
            <span className="text-lg font-semibold tracking-[-0.03em]">OMKA</span>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Knowledge Agent</p>
          </div>
        </div>

        <div className="mb-6 flex items-center justify-between px-2 sm:px-8">
          {steps.map((s, i) => {
            const Icon = s.icon
            return (
              <div key={i} className="flex flex-col items-center gap-2">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full border text-xs transition-all sm:h-10 sm:w-10 ${
                    i <= step
                      ? "border-primary bg-primary text-primary-foreground shadow-[0_5px_16px_rgba(0,113,227,0.2)]"
                      : "border-black/[0.06] bg-white/65 text-muted-foreground"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <span className="hidden text-[10px] font-medium text-muted-foreground sm:block">{s.title}</span>
              </div>
            )
          })}
        </div>

        <div className="apple-surface min-h-[390px] p-6 sm:p-10">
          {step === 0 && (
            <div className="text-center">
              <p className="eyebrow">Welcome</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em]">欢迎使用 OMKA</h2>
              <p className="mx-auto mt-3 max-w-md leading-7 text-muted-foreground">
                OMKA 是您的个人知识助手，帮助您自动发现、筛选和收藏 GitHub 上的优质内容。
              </p>
              <p className="mt-4 text-sm text-muted-foreground">
                接下来，我们将引导您完成初始配置，大约需要 2 分钟。
              </p>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">配置 GitHub</h2>
              <p className="text-sm text-muted-foreground">
                需要 GitHub Personal Access Token 来访问 API。
              </p>
              <div className="space-y-2">
                <label className="text-sm font-medium">GitHub Token</label>
                <input
                  type="password"
                  value={githubToken}
                  onChange={(e) => setGithubToken(e.target.value)}
                  placeholder="ghp_xxxxxxxxxxxx"
                  className="field-control"
                />
                <p className="text-xs text-muted-foreground">
                  在 GitHub Settings - Developer settings - Personal access tokens 中生成
                </p>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">添加关注仓库</h2>
              <p className="text-sm text-muted-foreground">添加您关注的 GitHub 仓库（可选）。</p>
              <div className="space-y-2">
                <label className="text-sm font-medium">仓库名称</label>
                <input
                  value={repoName}
                  onChange={(e) => setRepoName(e.target.value)}
                  placeholder="例如: React"
                  className="field-control"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">仓库全名</label>
                <input
                  value={repoFullName}
                  onChange={(e) => setRepoFullName(e.target.value)}
                  placeholder="owner/repo"
                  className="field-control"
                />
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">添加搜索关键词</h2>
              <p className="text-sm text-muted-foreground">添加您感兴趣的关键词（可选）。</p>
              <div className="space-y-2">
                <label className="text-sm font-medium">搜索关键词</label>
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="例如: react state management"
                  className="field-control"
                />
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">配置飞书推送（可选）</h2>
              <p className="text-sm text-muted-foreground">
                配置飞书机器人 Webhook，接收每日简报推送。
              </p>
              <div className="space-y-2">
                <label className="text-sm font-medium">Webhook URL</label>
                <input
                  value={feishuUrl}
                  onChange={(e) => setFeishuUrl(e.target.value)}
                  placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
                  className="field-control"
                />
              </div>
            </div>
          )}

          {step === 5 && (
            <div className="text-center">
              <Play className="mx-auto h-12 w-12 text-primary" />
              <h2 className="mt-4 text-xl font-semibold">准备就绪</h2>
              <p className="mt-2 text-muted-foreground">
                点击完成，保存配置并进入应用。
              </p>
            </div>
          )}

          <div className="mt-8 flex justify-between">
            <button
              onClick={handleBack}
              disabled={step === 0}
              className="secondary-button"
            >
              <ChevronLeft className="h-4 w-4" />
              上一步
            </button>

            {step < steps.length - 1 ? (
              <button
                onClick={handleNext}
                className="primary-button"
              >
                下一步
                <ChevronRight className="h-4 w-4" />
              </button>
            ) : (
              <button
                onClick={handleComplete}
                className="primary-button"
              >
                <Check className="h-4 w-4" />
                完成
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
