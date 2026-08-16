// Single source of truth for the ports/paths the Playwright config, global
// setup, and webServer commands all need to agree on. Imported by both
// playwright.config.ts and e2e/global-setup.ts, which run in the same Node
// process, so the temp dir created here is created exactly once per run.
import { mkdtempSync, copyFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Dedicated, non-default ports so this suite never collides with (or
// silently reuses) a developer's already-running `./dev.sh` servers.
export const BACKEND_PORT = 8010;
export const FRONTEND_PORT = 5183;
export const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
export const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;

const tmpDir = mkdtempSync(join(tmpdir(), 'tilora-e2e-'));
const dashboardConfigPath = join(tmpDir, 'dashboard.yaml');
copyFileSync(join(__dirname, 'fixtures', 'dashboard.yaml'), dashboardConfigPath);

// Isolates the e2e backend from a developer's real backend/storage.db,
// backend/config/dashboard.yaml, and backend/secret.key — none of the real
// dev data is ever touched by this suite.
export const BACKEND_ENV = {
	DB_PATH: join(tmpDir, 'test.db'),
	DASHBOARD_CONFIG_PATH: dashboardConfigPath,
	SECRET_KEY_PATH: join(tmpDir, 'secret.key'),
	CORS_ORIGIN: FRONTEND_URL,
	TIMEZONE: 'UTC',
};

export const AUTH_STATE_PATH = join(__dirname, '.auth', 'state.json');
