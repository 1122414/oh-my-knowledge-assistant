import { AppSidebar } from "./app-sidebar"

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen">
      <AppSidebar />
      <main className="min-h-screen pt-16 md:pl-[252px] md:pt-0">
        <div className="page-enter mx-auto w-full max-w-[1400px] px-4 pb-16 pt-6 sm:px-6 md:px-8 md:pt-10 lg:px-12 lg:pb-24">
          {children}
        </div>
      </main>
    </div>
  )
}
