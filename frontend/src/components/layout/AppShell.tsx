import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useTheme } from '../../hooks/useTheme'
import { APP_NAME, AUTHOR } from '../../lib/credits'
import { cn } from '../../lib/utils'
import { Button } from '../ui/Button'

const NAV_ITEMS = [
  { to: '/', label: 'Home', end: true },
  { to: '/generate/formula', label: 'Workspace', end: false },
  { to: '/analyzer', label: 'File Analyzer', end: false },
  { to: '/history', label: 'History', end: false },
  { to: '/settings', label: 'Settings', end: false },
  { to: '/about', label: 'About', end: false },
]

function navLinkClass({ isActive }: { isActive: boolean }) {
  return cn(
    'rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-primary',
    isActive ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
  )
}

export function AppShell() {
  const { theme, toggle } = useTheme()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-4 focus:py-2 focus:text-sm focus:shadow-lg"
      >
        Skip to main content
      </a>

      <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between gap-3 px-4">
          <div className="flex items-center gap-3">
            <Link
              to="/"
              className="flex items-center gap-2 rounded-md text-sm font-semibold focus-visible:outline-2 focus-visible:outline-primary"
              onClick={() => setMenuOpen(false)}
            >
              <span
                aria-hidden="true"
                className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground"
              >
                SJ
              </span>
              <span>{APP_NAME}</span>
            </Link>
          </div>

          <nav aria-label="Main navigation" className="hidden items-center gap-1 md:flex">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navLinkClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={toggle}
              aria-pressed={theme === 'dark'}
              data-testid="theme-toggle"
              title="Toggle colour theme"
            >
              {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="md:hidden"
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              onClick={() => setMenuOpen((o) => !o)}
              data-testid="mobile-menu-toggle"
            >
              {menuOpen ? 'Close' : 'Menu'}
            </Button>
          </div>
        </div>

        {menuOpen && (
          <nav
            id="mobile-nav"
            aria-label="Mobile navigation"
            className="border-t border-border bg-background px-4 py-2 md:hidden"
          >
            <ul className="flex flex-col gap-1">
              {NAV_ITEMS.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    className={navLinkClass}
                    onClick={() => setMenuOpen(false)}
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </header>

      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-border bg-card">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-2 px-4 py-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>
            {APP_NAME} — built by{' '}
            <a className="font-medium text-foreground underline-offset-2 hover:underline" href={AUTHOR.portfolio}>
              {AUTHOR.name}
            </a>
          </p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <a className="hover:text-foreground" href={`mailto:${AUTHOR.email}`}>
              {AUTHOR.email}
            </a>
            <a className="hover:text-foreground" href={AUTHOR.linkedin} target="_blank" rel="noreferrer">
              LinkedIn
            </a>
            <a className="hover:text-foreground" href={AUTHOR.github} target="_blank" rel="noreferrer">
              GitHub
            </a>
            <a className="hover:text-foreground" href={AUTHOR.portfolio} target="_blank" rel="noreferrer">
              Portfolio
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}
