// Completes first-run setup against the isolated e2e backend once per test
// run: registers a device, creates a PIN-less admin (allowed by
// POST /api/setup/admin — see backend/app/api/setup.py), and saves the
// resulting cookies as Playwright storage state so every test starts
// already logged in, without driving the login UI.
import { request } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { AUTH_STATE_PATH, BACKEND_URL } from './env';

export default async function globalSetup() {
	const context = await request.newContext({ baseURL: BACKEND_URL });

	await context.post('/api/devices/register');

	const status = await context.get('/api/setup/status');
	const { needs_setup } = await status.json();
	if (needs_setup) {
		const res = await context.post('/api/setup/admin', {
			data: { name: 'E2E Admin', pin: null },
		});
		if (!res.ok()) {
			throw new Error(`e2e global-setup: failed to create admin (${res.status()}): ${await res.text()}`);
		}
	}

	mkdirSync(dirname(AUTH_STATE_PATH), { recursive: true });
	await context.storageState({ path: AUTH_STATE_PATH });
	await context.dispose();
}
