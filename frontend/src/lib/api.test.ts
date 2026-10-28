import { describe, expect, it } from 'vitest'
import { ApiError, api } from './api'
import { errorResponse, jsonResponse, stubFetch } from '../test/helpers'

describe('api client', () => {
  it('parses successful JSON responses', async () => {
    stubFetch({ '/health': () => jsonResponse({ status: 'ok', version: '0.1.0' }) })
    await expect(api.health()).resolves.toEqual({ status: 'ok', version: '0.1.0' })
  })

  it('maps the backend error envelope onto ApiError', async () => {
    stubFetch({
      '/solutions/generate': () =>
        errorResponse('rate_limited', 'Too many requests, slow down.', 429, 'req-abc-123'),
    })

    const err = await api
      .generate({
        request: 'sum column A',
        platform: 'excel',
        task_type: 'formula',
        skill_level: 'beginner',
        explanation_language: 'English',
        context: {},
        guided: {},
        use_fallback: true,
        include_file_context: false,
      })
      .catch((e: unknown) => e)

    expect(err).toBeInstanceOf(ApiError)
    const apiErr = err as ApiError
    expect(apiErr.code).toBe('rate_limited')
    expect(apiErr.status).toBe(429)
    expect(apiErr.message).toContain('Too many requests')
    expect(apiErr.requestId).toBe('req-abc-123')
  })

  it('falls back to a generic message for non-JSON error bodies', async () => {
    stubFetch({
      '/health': () =>
        Promise.resolve(
          new Response('<html>502 Bad Gateway</html>', {
            status: 502,
            headers: { 'Content-Type': 'text/html' },
          }),
        ),
    })

    const err = await api.health().catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(502)
    expect((err as ApiError).code).toBe('http_error')
    expect((err as ApiError).message).toContain('HTTP 502')
  })

  it('sends provider config updates as JSON PUT with the key exactly once', async () => {
    const fetchMock = stubFetch({
      '/settings/providers/groq': () => jsonResponse({ name: 'groq' }, 200),
    })

    await api.updateProvider('groq', { api_key: 'gsk_secret_key' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [unknown, RequestInit]
    expect(String(url)).toContain('/settings/providers/groq')
    expect(init.method).toBe('PUT')
    expect(init.body).toBe(JSON.stringify({ api_key: 'gsk_secret_key' }))
    // Only a JSON content type — no accidental auth headers carrying the key.
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json')
  })

  it('never sends an api key on provider test calls', async () => {
    const fetchMock = stubFetch({
      '/providers/groq/test': () =>
        jsonResponse({ provider: 'groq', ok: true, message: 'ok', models_count: 3, latency_ms: 12, tested_at: new Date().toISOString() }),
    })

    await api.testProvider('groq')
    const [, init] = fetchMock.mock.calls[0] as [unknown, RequestInit]
    expect(init.body).toBeUndefined()
    expect(JSON.stringify(init.headers ?? {})).not.toContain('key')
  })
})
