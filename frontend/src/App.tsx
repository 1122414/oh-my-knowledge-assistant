import { BrowserRouter, Routes, Route } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { DashboardPage } from "@/pages/DashboardPage"
import { SourcesPage } from "@/pages/SourcesPage"
import { DigestPage } from "@/pages/DigestPage"
import { KnowledgePage } from "@/pages/KnowledgePage"
import { ReadLaterPage } from "@/pages/ReadLaterPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { JobLogsPage } from "@/pages/JobLogsPage"

function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/digest" element={<DigestPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/read-later" element={<ReadLaterPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/job-logs" element={<JobLogsPage />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  )
}

export default App
