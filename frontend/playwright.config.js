import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const root = path.dirname(fileURLToPath(import.meta.url))
const python = process.env.DATAPULSE_PYTHON || 'python'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:18771',
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: [
    {
      command: `"${python}" -m tests.e2e_server`,
      cwd: path.join(root, '..', 'backend'),
      url: 'http://127.0.0.1:18770/health',
      reuseExistingServer: false,
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5000 },
      timeout: 60000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 18771 --strictPort',
      env: { VITE_API_URL: 'http://127.0.0.1:18770/api/v1' },
      url: 'http://127.0.0.1:18771',
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
})
