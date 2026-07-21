import { useState } from "react"
import { Link, useLocation } from "react-router-dom"
import {
  LayoutDashboard,
  Settings,
  FolderGit2,
  Newspaper,
  Brain,
  Clock3,
  Bell,
  ScrollText,
  FileBox,
  Menu,
  X,
  Library,
  Sparkles,
  Bot,
} from "lucide-react"
import { cn } from "@/lib/cn"

const navSections = [
  {
    label: "知识流",
    items: [
      { path: "/", label: "概览", icon: LayoutDashboard },
      { path: "/digest", label: "今日精选", icon: Newspaper },
      { path: "/knowledge", label: "知识库", icon: Library },
      { path: "/read-later", label: "稍后阅读", icon: Clock3 },
      { path: "/memory", label: "记忆", icon: Brain },
      { path: "/assets", label: "知识资产", icon: FileBox },
    ],
  },
  {
    label: "自动化",
    items: [
      { path: "/agent", label: "Agent 中心", icon: Bot },
      { path: "/sources", label: "信息源", icon: FolderGit2 },
      { path: "/push", label: "推送策略", icon: Bell },
      { path: "/job-logs", label: "运行记录", icon: ScrollText },
      { path: "/settings", label: "设置", icon: Settings },
    ],
  },
]

export function AppSidebar() {
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <>
      <div className="fixed inset-x-0 top-0 z-30 flex h-16 items-center border-b border-black/[0.05] bg-white/75 px-4 backdrop-blur-xl md:hidden">
        <button
          onClick={() => setMobileOpen((open) => !open)}
          className="icon-button"
          aria-label={mobileOpen ? "关闭导航" : "打开导航"}
          aria-expanded={mobileOpen}
        >
          {mobileOpen ? <X className="h-4.5 w-4.5" /> : <Menu className="h-4.5 w-4.5" />}
        </button>
        <div className="ml-3 flex items-center gap-2.5">
          <BrandMark />
          <span className="text-[15px] font-semibold tracking-[-0.02em]">OMKA</span>
        </div>
      </div>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-[252px] border-r border-black/[0.055] bg-white/72 px-3.5 py-4 backdrop-blur-2xl transition-transform duration-300 md:translate-x-0",
          mobileOpen ? "visible translate-x-0" : "invisible -translate-x-full md:visible"
        )}
      >
        <div className="flex h-full flex-col">
          <div className="flex h-12 items-center gap-3 px-2.5">
            <BrandMark />
            <div>
              <p className="text-[15px] font-semibold tracking-[-0.025em]">OMKA</p>
              <p className="text-[10px] font-medium uppercase tracking-[0.13em] text-muted-foreground">
                Knowledge Agent
              </p>
            </div>
          </div>

          <nav className="mt-7 flex-1 space-y-6 overflow-y-auto px-0.5">
            {navSections.map((section) => (
              <div key={section.label}>
                <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/75">
                  {section.label}
                </p>
                <div className="space-y-1">
                  {section.items.map((item) => {
                    const Icon = item.icon
                    const isActive = location.pathname === item.path
                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        onClick={() => setMobileOpen(false)}
                        className={cn(
                          "group flex h-10 items-center gap-3 rounded-xl px-3 text-[13px] font-medium transition-all",
                          isActive
                            ? "bg-white text-foreground shadow-[0_1px_2px_rgba(0,0,0,0.06),0_5px_16px_rgba(0,0,0,0.05)] ring-1 ring-black/[0.045]"
                            : "text-muted-foreground hover:bg-white/65 hover:text-foreground"
                        )}
                      >
                        <Icon
                          className={cn(
                            "h-[17px] w-[17px] transition-colors",
                            isActive ? "text-primary" : "text-muted-foreground/80 group-hover:text-foreground"
                          )}
                          strokeWidth={1.8}
                        />
                        {item.label}
                        {isActive && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" />}
                      </Link>
                    )
                  })}
                </div>
              </div>
            ))}
          </nav>

          <div className="mt-4 rounded-2xl border border-black/[0.05] bg-white/58 p-3.5">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-30" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
              </span>
              <span className="text-xs font-medium">Agent 已就绪</span>
              <Sparkles className="ml-auto h-3.5 w-3.5 text-primary" />
            </div>
            <p className="mt-1.5 text-[11px] leading-4 text-muted-foreground">
              知识采集、记忆与推荐正在持续协同。
            </p>
          </div>
        </div>
      </aside>

      {mobileOpen && (
        <button
          className="fixed inset-0 z-30 bg-black/20 backdrop-blur-[2px] md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label="关闭导航遮罩"
        />
      )}
    </>
  )
}

function BrandMark() {
  return (
    <div className="relative h-8 w-8 overflow-hidden rounded-[10px] bg-foreground shadow-sm" aria-hidden="true">
      <span className="absolute left-[7px] top-[7px] h-[13px] w-[13px] rounded-[4px] border border-white/80" />
      <span className="absolute bottom-[6px] right-[6px] h-[11px] w-[11px] rounded-full bg-primary ring-2 ring-foreground" />
    </div>
  )
}
