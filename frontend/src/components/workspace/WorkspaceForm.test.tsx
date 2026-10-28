import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { GenerationRequest } from '../../lib/types'
import { APP_SETTINGS_FIXTURE, renderWithProviders, stubFetch } from '../../test/helpers'
import { WorkspaceForm } from './WorkspaceForm'

function setupFetch() {
  return stubFetch({
    '/settings/app': () =>
      Promise.resolve(
        new Response(JSON.stringify(APP_SETTINGS_FIXTURE), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    '/providers': () =>
      Promise.resolve(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
  })
}

describe('WorkspaceForm', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows task-specific guided fields that change with the task type', async () => {
    setupFetch()
    const user = userEvent.setup()
    renderWithProviders(<WorkspaceForm preset={null} loading={false} error={null} onSubmitRequest={() => {}} />)

    // Formula task shows lookup-oriented guided fields.
    expect(await screen.findByLabelText(/lookup column/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/return column/i)).toBeInTheDocument()

    // Switch to VBA → VBA-specific fields replace the formula ones.
    await user.selectOptions(screen.getByLabelText(/task type/i), 'vba_macro')
    expect(await screen.findByLabelText(/target range/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/trigger/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/return column/i)).not.toBeInTheDocument()
  })

  it('fills the request from an example chip including guided values', async () => {
    setupFetch()
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderWithProviders(
      <WorkspaceForm preset={null} loading={false} error={null} onSubmitRequest={onSubmit} />,
    )

    await user.click(await screen.findByRole('button', { name: 'XLOOKUP across sheets' }))

    const textarea = screen.getByLabelText(/your request/i)
    await waitFor(() => {
      expect((textarea as HTMLTextAreaElement).value).toContain('matching the SKU')
    })

    // Guided values from the example are present.
    expect(screen.getByLabelText(/lookup column/i)).toHaveValue('Orders!A:A (SKU)')

    await user.click(screen.getByRole('button', { name: 'Generate solution' }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
    const body = onSubmit.mock.calls[0][0] as GenerationRequest
    expect(body.platform).toBe('excel')
    expect(body.task_type).toBe('formula')
    expect(body.guided.lookup_column).toBe('Orders!A:A (SKU)')
    expect(body.guided.return_column).toBe('Products!A:B (Name)')
    expect(body.request).toContain('product name from the Products sheet')
    expect(body.include_file_context).toBe(false)
    expect(body.file_id).toBeNull()
  })

  it('validates short requests instead of submitting', async () => {
    setupFetch()
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderWithProviders(
      <WorkspaceForm preset={null} loading={false} error={null} onSubmitRequest={onSubmit} />,
    )

    await user.click(await screen.findByRole('button', { name: 'Generate solution' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/at least 3 characters/i)
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits spreadsheet context and skill settings', async () => {
    setupFetch()
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderWithProviders(
      <WorkspaceForm preset={null} loading={false} error={null} onSubmitRequest={onSubmit} />,
    )

    const textarea = await screen.findByLabelText(/your request/i)
    await user.clear(textarea)
    await user.type(textarea, 'Total revenue by region for Q1 only')
    await user.selectOptions(screen.getByLabelText(/explanation depth/i), 'advanced')
    await user.click(screen.getByRole('button', { name: 'Generate solution' }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
    const body = onSubmit.mock.calls[0][0] as GenerationRequest
    expect(body.skill_level).toBe('advanced')
    expect(body.context.input_data_description ?? '').toBe('')
    expect(body.request).toBe('Total revenue by region for Q1 only')

    // Optional context field flows through when filled.
    // (Re-run with context expanded.)
    const details = screen.getByText(/more spreadsheet context/i).closest('details')
    if (details) details.open = true
    const ctxInput = screen.getByLabelText(/worksheet names/i)
    await user.type(ctxInput, 'Orders, Summary')
    await user.click(screen.getByRole('button', { name: 'Generate solution' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(2))
    const body2 = onSubmit.mock.calls[1][0] as GenerationRequest
    expect(body2.context.worksheet_names).toBe('Orders, Summary')
  })
})
