import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { ToastProvider } from './components/ui/Toast'
import { AboutPage } from './pages/AboutPage'
import { AnalyzerPage } from './pages/AnalyzerPage'
import { HistoryDetailPage } from './pages/HistoryDetailPage'
import { HistoryPage } from './pages/HistoryPage'
import { HomePage } from './pages/HomePage'
import { SettingsPage } from './pages/SettingsPage'
import { WorkspacePage } from './pages/WorkspacePage'

export function NotFoundPage() {
  return (
    <div className="space-y-3 py-12 text-center" data-testid="not-found">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-sm text-muted-foreground">
        The page you asked for does not exist in sheetJEDI.
      </p>
      <a href="/" className="text-sm text-primary underline-offset-2 hover:underline">
        Back to home
      </a>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<HomePage />} />
            <Route path="generate" element={<Navigate to="/generate/formula" replace />} />
            <Route path="generate/:preset" element={<WorkspacePage />} />
            <Route path="analyzer" element={<AnalyzerPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="history/:id" element={<HistoryDetailPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </ToastProvider>
    </BrowserRouter>
  )
}
