import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end tests with a fully mocked /api/v1 surface (no backend, no
 * provider keys, no paid calls). The Vite dev server is reused when already
 * running, otherwise started by Playwright.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: true,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
