import { defineConfig, devices } from '@playwright/test';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { AUTH_STATE_PATH, BACKEND_ENV, BACKEND_PORT, BACKEND_URL, FRONTEND_PORT, FRONTEND_URL } from './e2e/env';

const __dirname = dirname(fileURLToPath(import.meta.url));
const backendRoot = join(__dirname, '..', 'backend');

export default defineConfig({
	testDir: './e2e',
	// The two projects below share one backend instance (and one sqlite
	// fixture db) so they can't safely run concurrently — see
	// e2e/dashboard-tiles.spec.ts for how each test stays order-independent
	// despite that.
	fullyParallel: false,
	workers: 1,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 1 : 0,
	reporter: process.env.CI ? 'github' : 'html',
	globalSetup: './e2e/global-setup.ts',
	use: {
		baseURL: FRONTEND_URL,
		storageState: AUTH_STATE_PATH,
		trace: 'retain-on-failure',
		video: 'retain-on-failure',
	},
	projects: [
		{
			name: 'desktop-chromium',
			use: { ...devices['Desktop Chrome'] },
		},
		{
			// The project that exists specifically to catch touch/WebKit-only
			// regressions (see CONTRIBUTING.md) — real iPhone viewport + touch
			// input on the actual WebKit engine, not a synthetic jsdom event.
			name: 'mobile-safari',
			use: { ...devices['iPhone 14'] },
		},
	],
	webServer: [
		{
			command: `uv run uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT}`,
			cwd: backendRoot,
			url: `${BACKEND_URL}/api/setup/status`,
			reuseExistingServer: false,
			env: BACKEND_ENV,
			stdout: 'pipe',
			stderr: 'pipe',
			timeout: 60_000,
		},
		{
			command: `npm run dev -- --host 127.0.0.1 --port ${FRONTEND_PORT} --strictPort`,
			cwd: __dirname,
			url: FRONTEND_URL,
			reuseExistingServer: false,
			env: { PUBLIC_API_BASE_URL: BACKEND_URL },
			stdout: 'pipe',
			stderr: 'pipe',
			timeout: 60_000,
		},
	],
});
