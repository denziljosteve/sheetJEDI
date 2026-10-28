import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import {
  APP_SETTINGS_FIXTURE,
  jsonResponse,
  providerFixture,
  renderWithProviders,
  stubFetch,
} from './test/helpers'

// App renders its own BrowserRouter (backed by jsdom's history API).
function renderApp() {
  const { container } = renderWithProviders(<App />)
  return container
}

describe('app shell & navigation', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    window.history.pushState({}, '', '/')
    stubFetch({
      '/settings/app': () => jsonResponse(APP_SETTINGS_FIXTURE),
      '/providers': () =>
        jsonResponse([
          providerFixture(),
          providerFixture({ name: 'openrouter', display_name: 'OpenRouter', config_status: 'unconfigured', api_key_hint: null }),
        ]),
    })
  })

  it('renders the home page with presets and honest provider status', async () => {
    renderApp()

    expect(await screen.findByTestId('home-hero')).toBeInTheDocument()
    expect(screen.getByTestId('preset-formula')).toBeInTheDocument()
    expect(screen.getByTestId('preset-office-script')).toBeInTheDocument()

    // Provider strip shows configured + unconfigured honestly.
    expect(await screen.findByText('configured')).toBeInTheDocument()
    expect(screen.getByText('unconfigured')).toBeInTheDocument()
    expect(screen.getByText(/protocol_verified/)).toBeInTheDocument()
  })

  it('navigates from hero to the formula workspace', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.click(await screen.findByTestId('hero-open-workspace'))
    expect(await screen.findByTestId('workspace-page')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/generate/formula')
    expect(screen.getByTestId('workspace-form')).toBeInTheDocument()
    // Clean URL on reload: preset inferred from the URL.
    expect(screen.getByRole('heading', { name: 'Formula', level: 1 })).toBeInTheDocument()
  })

  it('toggles the dark theme and persists the choice', async () => {
    const user = userEvent.setup()
    renderApp()

    const toggle = await screen.findByTestId('theme-toggle')
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    expect(document.documentElement.classList.contains('dark')).toBe(false)

    await user.click(toggle)
    await waitFor(() => {
      expect(document.documentElement.classList.contains('dark')).toBe(true)
    })
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(window.localStorage.getItem('sheetjedi-theme')).toBe('dark')

    await user.click(toggle)
    await waitFor(() => {
      expect(document.documentElement.classList.contains('dark')).toBe(false)
    })
  })

  it('exposes the mobile navigation on small screens', async () => {
    const user = userEvent.setup()
    renderApp()

    const menuToggle = await screen.findByTestId('mobile-menu-toggle')
    expect(menuToggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(menuToggle)
    expect(menuToggle).toHaveAttribute('aria-expanded', 'true')
    const mobileNav = screen.getByLabelText('Mobile navigation')
    expect(mobileNav).toBeInTheDocument()
    expect(within(mobileNav).getByText('File Analyzer')).toBeInTheDocument()
  })

  it('shows the not-found page for unknown routes', async () => {
    window.history.pushState({}, '', '/definitely-not-a-page')
    renderApp()
    expect(await screen.findByTestId('not-found')).toBeInTheDocument()
  })
})
