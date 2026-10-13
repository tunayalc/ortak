import { defineConfig } from '@playwright/test'
import { existsSync } from 'node:fs'

const python = process.env.ORTAK_TEST_PYTHON || (existsSync('../backend/.venv-release/bin/python') ? '../backend/.venv-release/bin/python' : 'python')

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  reporter: [['list'], ['junit', { outputFile: 'test-results/ui.xml' }]],
  use: { baseURL: 'http://127.0.0.1:5190', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'desktop', use: { viewport: { width: 1440, height: 1000 } } }, { name: 'mobile', use: { viewport: { width: 390, height: 844 } } }],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8011 --no-access-log`,
      url: 'http://127.0.0.1:8011/readyz',
      env: { APP_ENVIRONMENT: 'test', GOOGLE_MAPS_API_KEY: '', GOOGLE_MAPS_CALLS_ENABLED: 'false', DATABASE_URL: 'sqlite:///./test-results/ui.sqlite3', OSRM_BASE_URL: 'http://127.0.0.1:9', LLM_PROVIDER: 'disabled' },
      reuseExistingServer: false,
    },
    {
      command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 5190 --strictPort',
      url: 'http://127.0.0.1:5190',
      env: { ORTAK_TEST_BACKEND_URL: 'http://127.0.0.1:8011' },
      reuseExistingServer: false,
    },
  ],
})
