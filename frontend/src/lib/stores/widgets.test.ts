import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { WidgetSummaryMeta } from '$lib/api';

const { listWidgets } = vi.hoisted(() => ({ listWidgets: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { listWidgets } }));

beforeEach(() => {
	vi.resetModules();
	listWidgets.mockReset();
});

describe('widgets store', () => {
	it('populates from api.listWidgets once loaded', async () => {
		const data = [
			{
				id: 'weather',
				type: 'weather',
				name: 'Weather',
				layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 },
				tab: 'default',
			},
		];
		listWidgets.mockResolvedValue(data);

		const { widgets } = await import('./widgets');
		let value: unknown[] = [];
		const unsubscribe = widgets.subscribe((v) => (value = v));

		await vi.waitFor(() => expect(value).toEqual(data));
		unsubscribe();
	});

	it('falls back to an empty array when the request fails', async () => {
		listWidgets.mockRejectedValue(new Error('network error'));

		const { widgets } = await import('./widgets');
		let value: unknown[] | undefined;
		const unsubscribe = widgets.subscribe((v) => (value = v));

		await vi.waitFor(() => expect(value).toEqual([]));
		unsubscribe();
	});

	it('applyLayoutUpdates patches matching widgets in place without a refetch', async () => {
		const layout = { col: 1, row: 1, colSpan: 1, rowSpan: 1 };
		listWidgets.mockResolvedValue([
			{ id: 'a', type: 'weather', name: 'Weather', layout, tab: 'default' },
			{ id: 'b', type: 'clock', name: 'Clock', layout, tab: 'default' },
		]);

		const { widgets, applyLayoutUpdates } = await import('./widgets');
		let value: WidgetSummaryMeta[] = [];
		const unsubscribe = widgets.subscribe((v) => (value = v));
		await vi.waitFor(() => expect(value).toHaveLength(2));

		applyLayoutUpdates([{ id: 'b', layout: { col: 2, row: 1, colSpan: 1, rowSpan: 1 } }]);

		expect(listWidgets).toHaveBeenCalledTimes(1);
		expect(value.find((w) => w.id === 'a')?.layout).toEqual(layout);
		expect(value.find((w) => w.id === 'b')?.layout).toEqual({ col: 2, row: 1, colSpan: 1, rowSpan: 1 });
		unsubscribe();
	});

	it('addWidgetLocal appends a widget without a refetch', async () => {
		listWidgets.mockResolvedValue([]);

		const { widgets, addWidgetLocal } = await import('./widgets');
		let value: WidgetSummaryMeta[] = [];
		const unsubscribe = widgets.subscribe((v) => (value = v));
		await vi.waitFor(() => expect(value).toEqual([]));

		const layout = { col: 1, row: 1, colSpan: 1, rowSpan: 1 };
		addWidgetLocal({
			id: 'new',
			type: 'weather',
			name: 'Weather',
			layout,
			tab: 'default',
			refresh_interval_seconds: 600,
		});

		expect(listWidgets).toHaveBeenCalledTimes(1);
		expect(value).toEqual([
			{ id: 'new', type: 'weather', name: 'Weather', layout, tab: 'default', refresh_interval_seconds: 600 },
		]);
		unsubscribe();
	});

	it('addWidgetLocal is idempotent when a widget with the same id already exists', async () => {
		const layout = { col: 1, row: 1, colSpan: 1, rowSpan: 1 };
		const widget: WidgetSummaryMeta = {
			id: 'new',
			type: 'weather',
			name: 'Weather',
			layout,
			tab: 'default',
			refresh_interval_seconds: 600,
		};
		// Simulates a reload (e.g. a breakpoint change) racing ahead of the
		// addWidget response and already picking up the server-persisted widget.
		listWidgets.mockResolvedValue([widget]);

		const { widgets, addWidgetLocal } = await import('./widgets');
		let value: WidgetSummaryMeta[] = [];
		const unsubscribe = widgets.subscribe((v) => (value = v));
		await vi.waitFor(() => expect(value).toEqual([widget]));

		addWidgetLocal(widget);

		expect(value).toEqual([widget]);
		unsubscribe();
	});

	it('removeWidgetLocal filters a widget out without a refetch', async () => {
		const layout = { col: 1, row: 1, colSpan: 1, rowSpan: 1 };
		listWidgets.mockResolvedValue([
			{ id: 'a', type: 'weather', name: 'Weather', layout, tab: 'default' },
			{ id: 'b', type: 'clock', name: 'Clock', layout, tab: 'default' },
		]);

		const { widgets, removeWidgetLocal } = await import('./widgets');
		let value: WidgetSummaryMeta[] = [];
		const unsubscribe = widgets.subscribe((v) => (value = v));
		await vi.waitFor(() => expect(value).toHaveLength(2));

		removeWidgetLocal('a');

		expect(listWidgets).toHaveBeenCalledTimes(1);
		expect(value).toEqual([{ id: 'b', type: 'clock', name: 'Clock', layout, tab: 'default' }]);
		unsubscribe();
	});
});
