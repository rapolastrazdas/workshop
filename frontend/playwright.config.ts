import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  use: {
    baseURL: process.env.BASE_URL || 'http://127.0.0.1:5173',
    headless: true,
    screenshot: 'off',
    trace: 'off',
    launchOptions: process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {},
  },
})
