import { describe, expect, it, vi, beforeEach } from 'vitest';

vi.mock('$service-worker', () => ({
	base: '',
	build: ['/_app/immutable/entry/app.js', '/_app/immutable/assets/app.css'],
	files: ['/favicon.svg', '/manifest.webmanifest', '/icons/icon-192.png'],
	prerendered: [],
	version: 'test-v1',
}));

interface GlobalServiceWorkerScope {
	self: {
		addEventListener: ReturnType<typeof vi.fn>;
		skipWaiting: ReturnType<typeof vi.fn>;
		clients: {
			claim: ReturnType<typeof vi.fn>;
		};
	};
	caches: {
		open: ReturnType<typeof vi.fn>;
		keys: ReturnType<typeof vi.fn>;
		delete: ReturnType<typeof vi.fn>;
		match: ReturnType<typeof vi.fn>;
	};
}

describe('service worker', () => {
	let cachesMock: {
		open: ReturnType<typeof vi.fn>;
		keys: ReturnType<typeof vi.fn>;
		delete: ReturnType<typeof vi.fn>;
		match: ReturnType<typeof vi.fn>;
	};
	let cacheMock: {
		addAll: ReturnType<typeof vi.fn>;
		put: ReturnType<typeof vi.fn>;
	};
	let globalScope: GlobalServiceWorkerScope;

	beforeEach(() => {
		cacheMock = {
			addAll: vi.fn().mockResolvedValue(undefined),
			put: vi.fn().mockResolvedValue(undefined),
		};

		cachesMock = {
			open: vi.fn().mockResolvedValue(cacheMock),
			keys: vi.fn().mockResolvedValue(['tilora-cache-old', 'tilora-cache-test-v1']),
			delete: vi.fn().mockResolvedValue(true),
			match: vi.fn().mockResolvedValue(null),
		};

		globalScope = globalThis as unknown as GlobalServiceWorkerScope;
		globalScope.self = {
			addEventListener: vi.fn(),
			skipWaiting: vi.fn().mockResolvedValue(undefined),
			clients: {
				claim: vi.fn().mockResolvedValue(undefined),
			},
		};

		globalScope.caches = cachesMock;
	});

	it('exports CACHE_NAME and ASSETS array correctly', async () => {
		const { CACHE_NAME, ASSETS } = await import('./service-worker');
		expect(CACHE_NAME).toBe('tilora-cache-test-v1');
		expect(ASSETS).toContain('/_app/immutable/entry/app.js');
		expect(ASSETS).toContain('/favicon.svg');
		expect(ASSETS).toContain('/manifest.webmanifest');
	});

	it('handleInstall precaches assets and calls skipWaiting', async () => {
		const { handleInstall, CACHE_NAME, ASSETS } = await import('./service-worker');
		await handleInstall();

		expect(cachesMock.open).toHaveBeenCalledWith(CACHE_NAME);
		expect(cacheMock.addAll).toHaveBeenCalledWith(ASSETS);
		expect(globalScope.self.skipWaiting).toHaveBeenCalledTimes(1);
	});

	it('handleActivate purges old caches and claims clients', async () => {
		const { handleActivate } = await import('./service-worker');
		await handleActivate();

		expect(cachesMock.keys).toHaveBeenCalled();
		expect(cachesMock.delete).toHaveBeenCalledWith('tilora-cache-old');
		expect(cachesMock.delete).not.toHaveBeenCalledWith('tilora-cache-test-v1');
		expect(globalScope.self.clients.claim).toHaveBeenCalledTimes(1);
	});

	it('handleMessage activates waiting worker on SKIP_WAITING message', async () => {
		const { handleMessage } = await import('./service-worker');
		handleMessage({ data: { type: 'SKIP_WAITING' } });

		expect(globalScope.self.skipWaiting).toHaveBeenCalledTimes(1);
	});

	it('handleMessage ignores messages without SKIP_WAITING', async () => {
		const { handleMessage } = await import('./service-worker');
		handleMessage({ data: { type: 'OTHER_ACTION' } });

		expect(globalScope.self.skipWaiting).not.toHaveBeenCalled();
	});
});
