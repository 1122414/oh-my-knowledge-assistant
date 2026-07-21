import { BrowserRouter, Navigate, Routes, Route, useLocation } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { DashboardPage } from "@/pages/DashboardPage"
import { OnboardingPage } from "@/pages/OnboardingPage"
import { SourcesPage } from "@/pages/SourcesPage"
import { DigestPage } from "@/pages/DigestPage"
import { KnowledgePage } from "@/pages/KnowledgePage"
import { ReadLaterPage } from "@/pages/ReadLaterPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { JobLogsPage } from "@/pages/JobLogsPage"
import { PushPage } from "@/pages/PushPage"
import { AssetsPage } from "@/pages/AssetsPage"
import { MemoryPage } from "@/pages/MemoryPage"
import { AgentPage } from "@/pages/AgentPage"

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}

function AppRoutes() {
  const location = useLocation()

  if (location.pathname === "/onboarding") {
    return (
      <Routes>
        <Route path="/onboarding" element={<OnboardingPage />} />
      </Routes>
    )
  }

  return (
    <AppShell>
      <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/digest" element={<DigestPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/read-later" element={<ReadLaterPage />} />
          <Route path="/push" element={<PushPage />} />
          <Route path="/assets" element={<AssetsPage />} />
          <Route path="/memory" element={<MemoryPage />} />
          <Route path="/agent" element={<AgentPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/job-logs" element={<JobLogsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}

export default App
