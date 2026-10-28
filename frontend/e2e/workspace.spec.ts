import { expect, test, type Page } from '@playwright/test'

/**
 * E2E flows with the entire /api/v1 surface mocked in the browser.
 * No backend process, no provider keys, no paid calls — safe for CI.
 */

const APP_SETTINGS = {
  default_provider: null,
  default_model: null,
  fallback_provider: null,
  fallback_model: null,
  history_enabled: true,
  default_platform: 'excel',
  default_skill_level: 'beginner',
  default_explanation_language: 'English',
}

const SOLUTION = {
  title: 'E2E test solution',
  summary: 'A mocked structured solution.',
  platform: 'excel',
  task_type: 'formula',
  task_category: 'formula',
  formula: '=SUM(A1:A10)',
  code: null,
  code_language: null,
  required_version: null,
  assumptions: [],
  prerequisites: [],
  explanation: 'Adds up the range A1:A10.',
  implementation_steps: [
    {
      title: 'Paste into C2',
      instructions: 'Enter the formula in cell C2.',
      cell_references: ['C2'],
      code_location: null,
    },
  ],
  example_input: null,
  expected_output: '55',
  alternative_solutions: [],
  common_errors: [],
  troubleshooting: [],
  warnings: ['The range must stay the same size.'],
  confidence_notes: null,
}

const GENERATION_RESPONSE = {
  solution: SOLUTION,
  solution_id: 'e2e-1234-5678',
  provider: 'groq',
  model: 'mock-model',
  fallback_used: false,
  degraded: false,
  degraded_notice: null,
  usage: { prompt_tokens: 10, completion_tokens: 5 },
  generated_at: '2026-10-28T12:00:00Z',
}

async function mockReadApis(page: Page) {
  await page.route('**/api/v1/settings/app', (route) =>
    route.fulfill({ json: APP_SETTINGS }),
  )
  await page.route('**/api/v1/providers', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/v1/history**', (route) =>
    route.fulfill({ json: { items: [], total: 0, limit: 20, offset: 0 } }),
  )
}

test('generates a structured solution end-to-end (mocked API)', async ({ page }) => {
  await mockReadApis(page)

  let posted: Record<string, unknown> | null = null
  await page.route('**/api/v1/solutions/generate', async (route) => {
    posted = route.request().postDataJSON() as Record<string, unknown>
    await route.fulfill({ json: GENERATION_RESPONSE })
  })

  await page.goto('/generate/formula')
  await expect(page.getByRole('heading', { name: 'Formula', level: 1 })).toBeVisible()

  await page.getByLabel(/your request/i).fill('Total revenue by region for Q1')
  await page.getByTestId('generate-button').click()

  const view = page.getByTestId('solution-view')
  await expect(view).toBeVisible()
  await expect(page.getByTestId('solution-title')).toHaveText('E2E test solution')
  await expect(page.getByTestId('solution-formula')).toContainText('=SUM(A1:A10)')
  await expect(page.getByTestId('solution-steps')).toContainText('Paste into C2')
  await expect(page.getByTestId('solution-warnings-list')).toContainText(
    'same size',
  )
  await expect(view).toContainText('groq')
  await expect(view).toContainText('mock-model')

  // The request payload matched the API contract.
  expect(posted).not.toBeNull()
  expect(posted).toMatchObject({
    platform: 'excel',
    task_type: 'formula',
    skill_level: 'beginner',
    use_fallback: true,
    include_file_context: false,
  })
  expect(String(posted?.request)).toContain('Total revenue by region for Q1')
})

test('surfaces structured provider errors with the request id', async ({ page }) => {
  await mockReadApis(page)
  await page.route('**/api/v1/solutions/generate', (route) =>
    route.fulfill({
      status: 400,
      json: {
        error: {
          code: 'provider_not_configured',
          message: 'No AI provider is selected. Configure one in Settings first.',
          request_id: 'req-e2e-42',
        },
      },
    }),
  )

  await page.goto('/generate/formula')
  await page.getByLabel(/your request/i).fill('Something simple')
  await page.getByTestId('generate-button').click()

  const alert = page.getByTestId('submit-error')
  await expect(alert).toBeVisible()
  await expect(alert).toContainText('Configure one in Settings first')
  await expect(alert).toContainText('req-e2e-42')
  // No solution view on error.
  await expect(page.getByTestId('solution-view')).toHaveCount(0)
})

test('file analyzer gates upload behind consent', async ({ page }) => {
  await mockReadApis(page)

  let consented = true
  await page.route('**/api/v1/files/analyze', async (route) => {
    // Multipart parts look like: Content-Disposition: form-data; name="consent"
    // <blank line> true
    const body = route.request().postData() ?? ''
    consented = /name="consent"\r?\n\r?\ntrue/.test(body)
    await route.fulfill({
      json: {
        file_id: 'f-123',
        filename: 'demo.csv',
        file_type: 'csv',
        size_bytes: 42,
        sheet_count: 1,
        sheets: [
          {
            name: 'demo',
            total_rows_estimate: 2,
            total_columns: 2,
            scanned_rows: 2,
            truncated: false,
            headers: ['a', 'b'],
            columns: [],
            sample_rows: [],
            duplicate_rows_scanned: 0,
          },
        ],
        recommendations: [],
        notes: ['ok'],
        analyzed_at: '2026-10-28T12:00:00Z',
      },
    })
  })

  await page.goto('/analyzer')
  const analyzeBtn = page.getByTestId('analyzer-analyze')
  await expect(analyzeBtn).toBeDisabled()

  await page.getByTestId('analyzer-file-input').setInputFiles({
    name: 'demo.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('a,b\n1,2\n'),
  })
  await expect(analyzeBtn).toBeDisabled() // consent still missing

  await page.locator('[data-testid="analyzer-consent"] input').check()
  await expect(analyzeBtn).toBeEnabled()
  await analyzeBtn.click()

  await expect(page.getByTestId('analysis-result')).toBeVisible()
  await expect(page.getByTestId('analysis-result')).toContainText('demo.csv')
  expect(consented).toBe(true)
})

test('dark theme toggle applies and persists across reload', async ({ page }) => {
  await mockReadApis(page)
  await page.goto('/')

  const html = page.locator('html')
  await expect(html).not.toHaveClass(/dark/)

  await page.getByTestId('theme-toggle').click()
  await expect(html).toHaveClass(/dark/)
  await expect(page.getByTestId('theme-toggle')).toHaveAttribute('aria-pressed', 'true')

  await page.reload()
  await expect(html).toHaveClass(/dark/) // persisted via localStorage
})
