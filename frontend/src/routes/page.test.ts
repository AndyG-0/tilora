import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { WidgetSummaryMeta, TabMeta, WidgetLayout } from '$lib/api';

const { goto, listWidgets, tabsApi, version, themes, updateWidgetsLayout, removeWidget, widgetTypes, addWidget } =
	vi.hoisted(() => ({
		goto: vi.fn(),
		listWidgets: vi.fn(() => new Promise(() => {})), // never resolves — tests seed the store directly
		tabsApi: vi.fn(() => new Promise(() => {})), // never resolves — tests keep the single default tab
		version: vi.fn().mockResolvedValue({ update_available: false }),
		themes: vi.fn(() => new Promise(() => {})), // never resolves — keeps the fallback theme id list
		updateWidgetsLayout: vi.fn().mockResolvedValue({ status: 'ok' }),
		removeWidget: vi.fn().mockResolvedValue({ status: 'ok' }),
		widgetTypes: vi.fn().mockResolvedValue([]),
		addWidget: vi.fn(),
	}));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({
	api: {
		listWidgets,
		tabs: tabsApi,
		version,
		themes,
		updateWidgetsLayout,
		removeWidget,
		widgetTypes,
		addWidget,
		askAssistant: vi.fn(),
	},
}));
vi.mock('$lib/speech', () => ({
	isSpeechRecognitionSupported: () => false,
	isSpeechSynthesisSupported: () => false,
	speak: vi.fn(),
	listenOnce: vi.fn(),
}));
// Tile content isn't under test here — an empty map means `{#if Tile}` never
// renders anything inside a `.cell`, leaving the grid/drag/resize scaffolding
// (which is what these tests exercise) intact without needing real tiles.
vi.mock('$lib/widgetComponents', () => ({ TILE_COMPONENTS: {} }));

import Page from './+page.svelte';
import { widgets } from '$lib/stores/widgets';
import { activeTabIndex } from '$lib/stores/activeTab';

function widget(id: string, layout: WidgetLayout, tab = 'default'): WidgetSummaryMeta {
	return { id, type: 'message', name: 'Message', layout, tab, refresh_interval_seconds: 60 };
}

function stubCellRect(id: string, width: number, height: number) {
	const cell = document.querySelector(`[data-widget-id="${id}"]`) as HTMLElement;
	vi.spyOn(cell, 'getBoundingClientRect').mockReturnValue({
		width,
		height,
		top: 0,
		left: 0,
		right: width,
		bottom: height,
		x: 0,
		y: 0,
		toJSON() {},
	} as DOMRect);
	return cell;
}

describe('+page.svelte', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		listWidgets.mockReturnValue(new Promise(() => {}));
		tabsApi.mockReturnValue(new Promise(() => {}));
		themes.mockReturnValue(new Promise(() => {}));
		version.mockResolvedValue({ update_available: false });
		updateWidgetsLayout.mockResolvedValue({ status: 'ok' });
		widgets.set([]);
		activeTabIndex.set(0);
		Element.prototype.setPointerCapture = vi.fn();
		document.elementFromPoint = vi.fn().mockReturnValue(null);
	});

	it('toggles edit mode, showing per-widget remove/resize controls and the add-widget tile', async () => {
		widgets.set([widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 })]);
		render(Page);

		expect(screen.queryByRole('button', { name: 'Remove widget' })).not.toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange widgets' }));

		expect(screen.getByRole('button', { name: 'Remove widget' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Resize widget' })).toBeInTheDocument();
		expect(screen.getByText('+ Add widget')).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Done rearranging' }));

		expect(screen.queryByRole('button', { name: 'Remove widget' })).not.toBeInTheDocument();
	});

	it('switches tabs when a tab dot is clicked', async () => {
		tabsApi.mockResolvedValue([
			{ id: 'default', name: 'Dashboard' },
			{ id: 'second', name: 'Second' },
		] satisfies TabMeta[]);
		widgets.set([
			widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 }, 'default'),
			widget('w2', { col: 1, row: 1, colSpan: 1, rowSpan: 1 }, 'second'),
		]);
		render(Page);

		const dots = await screen.findAllByRole('button', { name: /Dashboard|Second/ });
		expect(dots[0]).toHaveClass('active');
		expect(dots[1]).not.toHaveClass('active');

		await fireEvent.click(dots[1]);

		expect(dots[1]).toHaveClass('active');
		expect(dots[0]).not.toHaveClass('active');
	});

	it('switches tabs on a horizontal swipe gesture', async () => {
		tabsApi.mockResolvedValue([
			{ id: 'default', name: 'Dashboard' },
			{ id: 'second', name: 'Second' },
		] satisfies TabMeta[]);
		widgets.set([widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 }, 'default')]);
		render(Page);

		const dots = await screen.findAllByRole('button', { name: /Dashboard|Second/ });
		expect(dots[0]).toHaveClass('active');

		const viewport = document.querySelector('.tabs-viewport') as HTMLElement;
		await fireEvent.touchStart(viewport, { touches: [{ clientX: 300, clientY: 100 }] });
		await fireEvent.touchEnd(viewport, { changedTouches: [{ clientX: 50, clientY: 100 }] });

		expect(dots[1]).toHaveClass('active');
	});

	it('drags one widget onto another to swap their layouts', async () => {
		widgets.set([
			widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 }),
			widget('w2', { col: 2, row: 1, colSpan: 2, rowSpan: 1 }),
		]);
		render(Page);
		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange widgets' }));

		const source = document.querySelector('[data-widget-id="w1"]') as HTMLElement;
		const target = document.querySelector('[data-widget-id="w2"]') as HTMLElement;
		vi.mocked(document.elementFromPoint).mockReturnValue(target);

		await fireEvent.pointerDown(source, { clientX: 0, clientY: 0, pointerId: 1 });
		expect(source).toHaveClass('dragging');

		await fireEvent.pointerMove(window, { clientX: 150, clientY: 0, pointerId: 1 });
		expect(target).toHaveClass('drop-target');

		await fireEvent.pointerUp(window, { clientX: 150, clientY: 0, pointerId: 1 });

		expect(updateWidgetsLayout).toHaveBeenCalledWith(
			[
				{ id: 'w1', layout: { col: 2, row: 1, colSpan: 2, rowSpan: 1 } },
				{ id: 'w2', layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 } },
			],
			'wide',
		);
		expect(source.getAttribute('style')).toContain('grid-column: 2 / span 2');
		expect(target.getAttribute('style')).toContain('grid-column: 1 / span 1');
	});

	it('drags a widget onto empty grid space to move it there', async () => {
		widgets.set([widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 })]);
		render(Page);
		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange widgets' }));

		const source = document.querySelector('[data-widget-id="w1"]') as HTMLElement;
		await fireEvent.pointerDown(source, { clientX: 0, clientY: 0, pointerId: 1 });

		const emptyCell = document.querySelector('[data-empty-cell][data-col="3"][data-row="1"]') as HTMLElement;
		expect(emptyCell).toBeTruthy();
		vi.mocked(document.elementFromPoint).mockReturnValue(emptyCell);

		await fireEvent.pointerMove(window, { clientX: 200, clientY: 0, pointerId: 1 });
		await fireEvent.pointerUp(window, { clientX: 200, clientY: 0, pointerId: 1 });

		expect(updateWidgetsLayout).toHaveBeenCalledWith(
			[{ id: 'w1', layout: { col: 3, row: 1, colSpan: 1, rowSpan: 1 } }],
			'wide',
		);
	});

	it('resizes a widget by dragging its resize handle', async () => {
		widgets.set([widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 })]);
		render(Page);
		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange widgets' }));

		stubCellRect('w1', 100, 100);
		const cell = document.querySelector('[data-widget-id="w1"]') as HTMLElement;
		const handle = screen.getByRole('button', { name: 'Resize widget' });

		await fireEvent.pointerDown(handle, { clientX: 0, clientY: 0, pointerId: 1 });
		await fireEvent.pointerMove(window, { clientX: 100, clientY: 0, pointerId: 1 });

		expect(cell.getAttribute('style')).toContain('grid-column: 1 / span 2');

		await fireEvent.pointerUp(window, { clientX: 100, clientY: 0, pointerId: 1 });

		expect(updateWidgetsLayout).toHaveBeenCalledWith(
			[{ id: 'w1', layout: { col: 1, row: 1, colSpan: 2, rowSpan: 1 } }],
			'wide',
		);
		expect(cell).not.toHaveClass('resizing');
	});
});
