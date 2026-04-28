import { AppSidebar } from "./app-sidebar"

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-background">
      <AppSidebar />
      <main className="pl-0 md:pl-64">
        <div className="mx-auto max-w-6xl p-4 md:p-8">
          {children}
        </div>
      </main>
    </div>
  )
}
