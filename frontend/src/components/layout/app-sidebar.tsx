import { useState } from "react"
import { Link, useLocation } from "react-router-dom"
import {
  LayoutDashboard,
  Settings,
  BookOpen,
  FolderGit2,
  Newspaper,
  Brain,
  Clock,
  Bell,
  ScrollText,
  FileBox,
  Menu,
  X,
} from "lucide-react"
import { cn } from "@/lib/cn"

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/sources", label: "Sources", icon: FolderGit2 },
  { path: "/digest", label: "Digest", icon: Newspaper },
  { path: "/knowledge", label: "Knowledge", icon: Brain },
  { path: "/read-later", label: "Read Later", icon: Clock },
  { path: "/push", label: "Push", icon: Bell },
  { path: "/assets", label: "Assets", icon: FileBox },
  { path: "/memory", label: "Memory", icon: Brain },
  { path: "/job-logs", label: "Job Logs", icon: ScrollText },
  { path: "/settings", label: "Settings", icon: Settings },
]

export function AppSidebar() {
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <>
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="fixed left-4 top-4 z-50 flex h-10 w-10 items-center justify-center rounded-lg bg-card border border-border md:hidden"
      >
        {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      <aside
        className={cn(
          "fixed left-0 top-0 z-40 h-screen w-64 border-r border-border bg-card transition-transform md:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-full flex-col">
          <div className="flex h-16 items-center gap-2 border-b border-border px-6">
            <BookOpen className="h-6 w-6 text-primary" />
            <span className="text-lg font-semibold tracking-tight">OMKA</span>
          </div>
          <nav className="flex-1 space-y-1 px-3 py-4">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              )
            })}
          </nav>
        </div>
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}
    </>
  )
}
