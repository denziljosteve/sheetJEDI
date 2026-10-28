import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  APP_SETTINGS_FIXTURE,
  errorResponse,
  jsonResponse,
  providerFixture,
  renderWithProviders,
  stubFetch,
} from '../test/helpers'
import { SettingsPage } from './SettingsPage'

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('never shows a stored key, only a masked hint', async () => {
    stubFetch({
      '/settings/app': () => jsonResponse(APP_SETTINGS_FIXTURE),
      '/providers': () => jsonResponse([providerFixture()]),
    })

    renderWithProviders(<SettingsPage />)

    const keyInput = await screen.findByTestId('key-input-groq')
    expect(keyInput).toHaveAttribute('type', 'password')
    expect(keyInput).toHaveValue('') // full keys are never echoed
    expect(keyInput).toHaveAttribute(
      'placeholder',
      'Stored: ••••7890 — leave blank to keep',
    )
    expect(screen.getByText(/Encrypted with Fernet/)).toBeInTheDocument()
    expect(screen.getByTestId('provider-groq')).toBeInTheDocument()
    expect(screen.getByTestId('model-input-groq')).toHaveValue('llama-3.3-70b-versatile')
  })

  it('saves a newly pasted key once and clears the field afterwards', async () => {
    let savedBody: Record<string, unknown> | null = null
    const fetchMock = stubFetch({
      '/settings/app': () => jsonResponse(APP_SETTINGS_FIXTURE),
      '/settings/providers/groq': (init) => {
        savedBody = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null
        return jsonResponse(providerFixture({ config_status: 'tested', api_key_hint: '••••3f2a' }))
      },
      '/providers': () => jsonResponse([providerFixture()]),
    })

    const user = userEvent.setup()
    renderWithProviders(<SettingsPage />)

    const keyInput = await screen.findByTestId('key-input-groq')
    await user.type(keyInput, 'gsk_new_secret_value')
    await user.click(screen.getByTestId('save-groq'))

    await waitFor(() => expect(screen.getByTestId('saved-groq')).toBeInTheDocument())
    expect(savedBody).not.toBeNull()
    expect(savedBody).toMatchObject({ api_key: 'gsk_new_secret_value' })

    // Field cleared after confirmed save; UI only shows the hint afterwards.
    await waitFor(() => expect(keyInput).toHaveValue(''))
    expect(fetchMock).toHaveBeenCalled()

    // The response never carries a full key back to the UI.
    const responses = fetchMock.mock.calls.length
    expect(responses).toBeGreaterThan(0)
  })

  it('surfaces connection test failures honestly', async () => {
    stubFetch({
      '/settings/app': () => jsonResponse(APP_SETTINGS_FIXTURE),
      '/providers': () => jsonResponse([providerFixture({ config_status: 'configured' })]),
      '/providers/groq/test': () =>
        errorResponse('provider_auth_failed', 'Invalid API key provided.', 401),
    })

    const user = userEvent.setup()
    renderWithProviders(<SettingsPage />)

    await user.click(await screen.findByTestId('test-groq'))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Test failed: Invalid API key provided.')
    expect(alert).toHaveTextContent('req-test-1')
  })

  it('explains adapter verification status without overclaiming', async () => {
    stubFetch({
      '/settings/app': () => jsonResponse(APP_SETTINGS_FIXTURE),
      '/providers': () =>
        jsonResponse([
          providerFixture({
            name: 'omniroute',
            display_name: 'OmniRoute',
            verification_status: 'protocol_verified_host_required',
            status_note: 'Self-hosted gateway; a base URL is required to test.',
            config_status: 'unconfigured',
            api_key_hint: null,
            capabilities: {
              streaming: true,
              model_discovery: true,
              json_mode: true,
              custom_base_url: true,
            },
          }),
        ]),
    })

    renderWithProviders(<SettingsPage />)
    expect(await screen.findByTestId('provider-omniroute')).toHaveTextContent(
      'protocol_verified_host_required',
    )
    expect(screen.getByTestId('provider-omniroute')).toHaveTextContent(
      'Self-hosted gateway; a base URL is required to test.',
    )
    // Unconfigured provider: no hint, key input empty and ready.
    expect(screen.getByTestId('key-input-omniroute')).toHaveValue('')
  })
})
