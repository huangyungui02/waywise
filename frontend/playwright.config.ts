import { defineConfig } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export default defineConfig({
  testDir: './tests',
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5179', browserName: 'chromium' },
  webServer: [
    {
      command: '.venv/bin/python -m uvicorn ui_backend:create_app --app-dir tests --factory --host 127.0.0.1 --port 17933',
      cwd: '..',
      env: { UI_TEST_DATABASE: join(tmpdir(), `travel-agent-ui-${process.pid}.db`) },
      url: 'http://127.0.0.1:17933/api/health',
    },
    {
      command: 'npm run dev -- --port 5179',
      env: { API_PROXY_TARGET: 'http://127.0.0.1:17933' },
      url: 'http://127.0.0.1:5179',
    },
  ],
});
