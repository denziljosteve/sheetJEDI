import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/helpers'
import type { GenerationResponse, SolutionResponse } from '../../lib/types'
import { SolutionView } from './SolutionView'

const solution: SolutionResponse = {
  title: 'Look up product price by SKU',
  summary: 'Uses XLOOKUP with an exact match and a friendly fallback text.',
  platform: 'excel',
  task_type: 'formula',
  task_category: 'formula',
  formula: '=XLOOKUP(A2,Products!A:A,Products!D:D,"Not found")',
  code: null,
  code_language: null,
  required_version: 'Microsoft 365 / Excel 2021+',
  assumptions: ['SKUs are unique in the Products sheet'],
  prerequisites: ['Two sheets: Orders and Products'],
  explanation: 'XLOOKUP scans the lookup column and returns the corresponding value.',
  implementation_steps: [
    {
      title: 'Enter the formula',
      instructions: 'Paste the formula into cell C2 of the Orders sheet.',
      cell_references: ['Orders!C2'],
      code_location: null,
    },
  ],
  example_input: 'SKU-1001',
  expected_output: '12.50',
  alternative_solutions: [
    {
      title: 'INDEX/MATCH',
      description: 'Works in every Excel version.',
      formula: '=INDEX(Products!D:D,MATCH(A2,Products!A:A,0))',
      code: null,
      when_to_use: 'Older Excel builds without XLOOKUP.',
    },
  ],
  common_errors: [
    { error: '#N/A', cause: 'SKU does not exist in Products.', solution: 'Use the not-found argument.' },
  ],
  troubleshooting: ['Check for trailing spaces in SKUs'],
  warnings: ['Ranges must stay the same size or Excel will repair the formula.'],
  confidence_notes: 'High confidence for Microsoft 365.',
}

function meta(overrides: Partial<GenerationResponse> = {}): GenerationResponse {
  return {
    solution,
    solution_id: 'abc12345-1111-2222-3333-444455556666',
    provider: 'groq',
    model: 'llama-3.3-70b-versatile',
    fallback_used: false,
    degraded: false,
    degraded_notice: null,
    usage: { prompt_tokens: 100, completion_tokens: 50 },
    generated_at: '2026-10-28T10:00:00Z',
    ...overrides,
  }
}

describe('SolutionView', () => {
  it('renders title, formula, steps, warnings and safety note', () => {
    renderWithProviders(<SolutionView solution={solution} meta={meta()} />)

    expect(screen.getByTestId('solution-title')).toHaveTextContent('Look up product price by SKU')
    expect(screen.getByTestId('solution-formula')).toHaveTextContent('XLOOKUP(A2')
    expect(screen.getByTestId('solution-steps')).toHaveTextContent('Paste the formula into cell C2')
    expect(screen.getByTestId('solution-warnings-list')).toHaveTextContent(
      'Ranges must stay the same size',
    )
    expect(screen.getByText(/groq/)).toBeInTheDocument()
    expect(screen.getByText(/llama-3.3-70b-versatile/)).toBeInTheDocument()
    // No code block for pure-formula solutions.
    expect(screen.queryByTestId('solution-code')).not.toBeInTheDocument()
  })

  it('copies the formula to the clipboard', async () => {
    const user = userEvent.setup()
    const writeText = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockResolvedValue(undefined as never)

    renderWithProviders(<SolutionView solution={solution} meta={meta()} />)
    await user.click(screen.getByRole('button', { name: 'Copy formula' }))

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(
        '=XLOOKUP(A2,Products!A:A,Products!D:D,"Not found")',
      )
    })
    expect(await screen.findByRole('button', { name: 'Copied ✓' })).toBeInTheDocument()
    expect(await screen.findByTestId('toast')).toHaveTextContent('Copied to clipboard')
    writeText.mockRestore()
  })

  it('discloses fallback usage and degraded output', () => {
    const degradedSolution: SolutionResponse = {
      ...solution,
      code: 'RAW MODEL OUTPUT NOT VALIDATED',
      code_language: 'unvalidated_output',
      formula: null,
    }

    renderWithProviders(
      <SolutionView
        solution={degradedSolution}
        meta={meta({ fallback_used: true, degraded: true, degraded_notice: 'Repair round-trip failed.' })}
      />,
    )

    const notice = screen.getByTestId('solution-notice')
    expect(notice).toHaveTextContent('primary provider was unavailable')
    expect(notice).toHaveTextContent('Repair round-trip failed.')
    expect(notice).toHaveTextContent('unvalidated_output')
    expect(screen.getByText('Fallback used')).toBeInTheDocument()
    expect(screen.getByText('Degraded')).toBeInTheDocument()
  })
})
