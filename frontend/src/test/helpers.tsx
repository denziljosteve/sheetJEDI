// Shared test helpers (not matched by the vitest include pattern).
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { vi } from 'vitest'
import { ToastProvider } from '../components/ui/Toast'
import type { ProviderStatus } from '../lib/types'

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false, staleTime: Infinity },
      mutations: { retry: false },
    },
  })
}

export function renderWithProviders(ui: ReactElement): RenderResult {
  const client = makeQueryClient()
  const tree: ReactNode = (
    <QueryClientProvider client={client}>
      <ToastProvider>{ui}</ToastProvider>
    </QueryClientProvider>
  )
  return render(tree)
}

export function jsonResponse(data: unknown, status = 200): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(data), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

export function errorResponse(code: string, message: string, status: number, requestId = 'req-test-1'): Promise<Response> {
  return jsonResponse({ error: { code, message, request_id: requestId } }, status)
}

export const APP_SETTINGS_FIXTURE = {
  default_provider: null,
  default_model: null,
  fallback_provider: null,
  fallback_model: null,
  history_enabled: true,
  default_platform: 'excel',
  default_skill_level: 'beginner',
  default_explanation_language: 'English',
} as const

export function providerFixture(overrides: Partial<ProviderStatus> = {}): ProviderStatus {
  return {
    name: 'groq',
    display_name: 'Groq',
    protocol: 'openai_compatible',
    default_base_url: 'https://api.groq.com/openai/v1',
    capabilities: { streaming: true, model_discovery: true, json_mode: true, custom_base_url: false },
    status_note: null,
    verification_status: 'protocol_verified',
    docs_url: 'https://console.groq.com/docs',
    config_status: 'configured',
    api_key_hint: '••••7890',
    base_url_override: null,
    default_model: 'llama-3.3-70b-versatile',
    timeout_seconds: 60,
    last_tested_at: null,
    last_test_message: null,
    ...overrides,
  }
}

/**
 * Route-based fetch stub. `routes` maps a substring of the URL to a handler
 * (method-aware). Unmatched calls reject loudly so tests fail fast.
 */
export function stubFetch(
  routes: Record<string, (init?: RequestInit) => Promise<Response>>,
): ReturnType<typeof vi.fn> {
  // Longest pattern first so '/providers/groq/test' wins over '/providers'.
  const ordered = Object.entries(routes).sort((a, b) => b[0].length - a[0].length)
  const fn = vi.fn((input: RequestInitInfo | string, init?: RequestInit) => {
    const url = String(input)
    for (const [pattern, handler] of ordered) {
      if (url.includes(pattern)) return handler(init)
    }
    return Promise.reject(new Error(`Unexpected fetch in test: ${url}`))
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

type RequestInitInfo = { url?: string }
