import { beforeEach, describe, expect, it, vi } from 'vitest';

const { tabs: tabsApi } = vi.hoisted(() => ({ tabs: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { tabs: tabsApi } }));

beforeEach(() => {
	vi.resetModules();
	tabsApi.mockReset();
});

describe('tabs store', () => {
	it('populates from api.tabs once loaded', async () => {
		const data = [
			{ id: 'home', name: 'Home' },
			{ id: 'media', name: 'Media' },
		];
		tabsApi.mockResolvedValue(data);

		const { tabs } = await import('./tabs');
		let value: unknown[] = [];
		const unsubscribe = tabs.subscribe((v) => (value = v));

		await vi.waitFor(() => expect(value).toEqual(data));
		unsubscribe();
	});

	it('falls back to a single default tab when the request fails', async () => {
		tabsApi.mockRejectedValue(new Error('network error'));

		const { tabs } = await import('./tabs');
		let value: unknown[] | undefined;
		const unsubscribe = tabs.subscribe((v) => (value = v));

		await vi.waitFor(() => expect(value).toEqual([{ id: 'default', name: 'Dashboard' }]));
		unsubscribe();
	});
});
