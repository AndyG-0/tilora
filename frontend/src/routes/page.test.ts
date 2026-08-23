import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { WidgetSummaryMeta, TabMeta, WidgetLayout } from '$lib/api';

const {
	goto,
	listWidgets,
	tabsApi,
	version,
	themes,
	updateWidgetsLayout,
	removeWidget,
	widgetTypes,
	addWidget,
	askAssistant,
	isSpeechRecognitionSupported,
	isSpeechSynthesisSupported,
	speak,
	listenOnce,
	playChime,
	startContinuousListening,
	stopSpeaking,
	ensureMicrophonePermission,
} = vi.hoisted(() => ({
	goto: vi.fn(),
	listWidgets: vi.fn(() => new Promise(() => {})), // never resolves — tests seed the store directly
	tabsApi: vi.fn(() => new Promise(() => {})), // never resolves — tests keep the single default tab
	version: vi.fn().mockResolvedValue({ update_available: false }),
	themes: vi.fn(() => new Promise(() => {})), // never resolves — keeps the fallback theme id list
	updateWidgetsLayout: vi.fn().mockResolvedValue({ status: 'ok' }),
	removeWidget: vi.fn().mockResolvedValue({ status: 'ok' }),
	widgetTypes: vi.fn().mockResolvedValue([]),
	addWidget: vi.fn(),
	askAssistant: vi.fn(),
	isSpeechRecognitionSupported: vi.fn(() => false),
	isSpeechSynthesisSupported: vi.fn(() => false),
	speak: vi.fn(),
	listenOnce: vi.fn(),
	playChime: vi.fn(),
	startContinuousListening: vi.fn<(options?: unknown) => { stop: () => void; pause: () => void; resume: () => void }>(
		() => ({
			stop: vi.fn(),
			pause: vi.fn(),
			resume: vi.fn(),
		}),
	),
	stopSpeaking: vi.fn(),
	ensureMicrophonePermission: vi.fn().mockResolvedValue(true),
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
		askAssistant,
	},
}));
vi.mock('$lib/speech', () => {
	class SpeechError extends Error {
		code: string;
		constructor(message: string, code = 'unknown') {
			super(message);
			this.name = 'SpeechError';
			this.code = code;
		}
	}
	return {
		SpeechError,
		isSpeechRecognitionSupported,
		isSpeechSynthesisSupported,
		speak,
		listenOnce,
		playChime,
		startContinuousListening,
		stopSpeaking,
		ensureMicrophonePermission,
	};
});
// Tile content isn't under test here — an empty map means `{#if Tile}` never
// renders anything inside a `.cell`, leaving the grid/drag/resize scaffolding
// (which is what these tests exercise) intact without needing real tiles.
vi.mock('$lib/widgetComponents', () => ({ TILE_COMPONENTS: {} }));

import Page from './+page.svelte';
import { widgets } from '$lib/stores/widgets';
import { activeTabIndex } from '$lib/stores/activeTab';
import { agentName, alwaysOnMic } from '$lib/stores/assistant';
import { breakpoint } from '$lib/stores/breakpoint';

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
		breakpoint.set('wide');
		Element.prototype.setPointerCapture = vi.fn();
		document.elementFromPoint = vi.fn().mockReturnValue(null);
	});

	it('toggles edit mode, showing per-widget remove/resize controls and per-empty-cell add affordances', async () => {
		widgets.set([widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 })]);
		render(Page);

		expect(screen.queryByRole('button', { name: 'Remove tile' })).not.toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange tiles' }));

		expect(screen.getByRole('button', { name: 'Remove tile' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Resize tile' })).toBeInTheDocument();
		expect(screen.getAllByRole('button', { name: '+ Add tile' }).length).toBeGreaterThan(0);

		await fireEvent.click(screen.getByRole('button', { name: 'Done rearranging' }));

		expect(screen.queryByRole('button', { name: 'Remove tile' })).not.toBeInTheDocument();
		expect(screen.queryByRole('button', { name: '+ Add tile' })).not.toBeInTheDocument();
	});

	it('adds a tile at the empty cell that was clicked', async () => {
		widgets.set([widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 })]);
		widgetTypes.mockResolvedValue([{ type: 'clock', name: 'Clock', default_layout: { colSpan: 1, rowSpan: 1 } }]);
		addWidget.mockResolvedValue(widget('w2', { col: 3, row: 1, colSpan: 1, rowSpan: 1 }));
		render(Page);
		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange tiles' }));

		const targetCell = document.querySelector('[data-empty-cell][data-col="3"][data-row="1"]') as HTMLElement;
		const addButton = targetCell.querySelector('.empty-cell-add') as HTMLElement;
		await fireEvent.click(addButton);

		await fireEvent.click(await screen.findByRole('button', { name: 'Clock' }));

		expect(addWidget).toHaveBeenCalledWith('clock', { col: 3, row: 1, colSpan: 1, rowSpan: 1 }, 'default');
	});

	it('falls back to bottom placement when the chosen type overflows the clicked cell', async () => {
		widgets.set([
			widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 }),
			widget('w2', { col: 4, row: 1, colSpan: 1, rowSpan: 1 }),
		]);
		widgetTypes.mockResolvedValue([{ type: 'clock', name: 'Clock', default_layout: { colSpan: 2, rowSpan: 1 } }]);
		addWidget.mockResolvedValue(widget('w3', { col: 1, row: 2, colSpan: 2, rowSpan: 1 }));
		render(Page);
		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange tiles' }));

		// col 3 is free, but a colSpan-2 type placed there would overflow into
		// col 4, which w2 already occupies.
		const targetCell = document.querySelector('[data-empty-cell][data-col="3"][data-row="1"]') as HTMLElement;
		const addButton = targetCell.querySelector('.empty-cell-add') as HTMLElement;
		await fireEvent.click(addButton);

		await fireEvent.click(await screen.findByRole('button', { name: 'Clock' }));

		expect(addWidget).toHaveBeenCalledWith('clock', { col: 1, row: 2, colSpan: 2, rowSpan: 1 }, 'default');
	});

	it('shows a single trailing add-tile affordance at the narrow breakpoint', async () => {
		breakpoint.set('narrow');
		widgets.set([widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 })]);
		render(Page);
		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange tiles' }));

		expect(screen.getAllByRole('button', { name: '+ Add tile' })).toHaveLength(1);
		expect(document.querySelectorAll('[data-empty-cell]')).toHaveLength(0);
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
		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange tiles' }));

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
		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange tiles' }));

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
		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange tiles' }));

		stubCellRect('w1', 100, 100);
		const cell = document.querySelector('[data-widget-id="w1"]') as HTMLElement;
		const handle = screen.getByRole('button', { name: 'Resize tile' });

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

	it('only shows Auto Arrange in edit mode at the wide breakpoint', async () => {
		widgets.set([widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 })]);
		render(Page);

		expect(screen.queryByRole('button', { name: 'Auto arrange' })).not.toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange tiles' }));
		expect(screen.getByRole('button', { name: 'Auto arrange' })).toBeInTheDocument();

		breakpoint.set('narrow');
		await Promise.resolve();
		expect(screen.queryByRole('button', { name: 'Auto arrange' })).not.toBeInTheDocument();
	});

	it('cancelling the Auto Arrange confirmation leaves the layout untouched', async () => {
		widgets.set([
			widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 }),
			widget('w2', { col: 3, row: 1, colSpan: 1, rowSpan: 1 }),
		]);
		render(Page);
		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange tiles' }));

		await fireEvent.click(screen.getByRole('button', { name: 'Auto arrange' }));
		expect(screen.getByRole('dialog')).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		expect(updateWidgetsLayout).not.toHaveBeenCalled();
	});

	it('confirming Auto Arrange packs the current tab and persists the result', async () => {
		widgets.set([
			widget('w1', { col: 1, row: 1, colSpan: 1, rowSpan: 1 }),
			widget('w2', { col: 3, row: 1, colSpan: 1, rowSpan: 1 }),
		]);
		render(Page);
		await fireEvent.click(screen.getByRole('button', { name: 'Rearrange tiles' }));

		await fireEvent.click(screen.getByRole('button', { name: 'Auto arrange' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Arrange' }));

		expect(updateWidgetsLayout).toHaveBeenCalledWith(
			[
				{ id: 'w1', layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 } },
				{ id: 'w2', layout: { col: 2, row: 1, colSpan: 1, rowSpan: 1 } },
			],
			'wide',
		);
		const w2 = document.querySelector('[data-widget-id="w2"]') as HTMLElement;
		expect(w2.getAttribute('style')).toContain('grid-column: 2 / span 1');
	});

	it('handles manual click on mic button to ask assistant a question', async () => {
		isSpeechRecognitionSupported.mockReturnValue(true);
		alwaysOnMic.set(false);
		listenOnce.mockResolvedValue('what is the weather');
		askAssistant.mockResolvedValue({ text: 'It is sunny and 75 degrees.', action: null });

		render(Page);

		const micButton = screen.getByRole('button', { name: 'Ask a question' });
		expect(micButton).toBeInTheDocument();

		await fireEvent.click(micButton);

		expect(listenOnce).toHaveBeenCalled();
		expect(await screen.findByText('what is the weather')).toBeInTheDocument();
		expect(await screen.findByText('It is sunny and 75 degrees.')).toBeInTheDocument();
		expect(speak).toHaveBeenCalledWith('It is sunny and 75 degrees.', expect.anything());
	});

	it('stops speech when the page unmounts after an answer with no widget action', async () => {
		isSpeechRecognitionSupported.mockReturnValue(true);
		alwaysOnMic.set(false);
		listenOnce.mockResolvedValue('what is the weather');
		askAssistant.mockResolvedValue({ text: 'It is sunny and 75 degrees.', action: null });

		const { unmount } = render(Page);

		await fireEvent.click(screen.getByRole('button', { name: 'Ask a question' }));

		expect(await screen.findByText('It is sunny and 75 degrees.')).toBeInTheDocument();
		expect(goto).not.toHaveBeenCalled();

		unmount();

		expect(stopSpeaking).toHaveBeenCalled();
	});

	it('does not cut off speech when the assistant answer launches a widget', async () => {
		isSpeechRecognitionSupported.mockReturnValue(true);
		alwaysOnMic.set(false);
		listenOnce.mockResolvedValue('what is the weather');
		askAssistant.mockResolvedValue({
			text: 'It is sunny and 75 degrees.',
			action: { widget_id: 'weather', panel: null },
		});

		const { unmount } = render(Page);

		await fireEvent.click(screen.getByRole('button', { name: 'Ask a question' }));

		await waitFor(() => expect(goto).toHaveBeenCalledWith('/widget/weather'));
		expect(speak).toHaveBeenCalledWith('It is sunny and 75 degrees.', expect.anything());

		unmount();

		expect(stopSpeaking).not.toHaveBeenCalled();
	});

	it('starts continuous listening when alwaysOnMic is enabled and triggers on wake word', async () => {
		isSpeechRecognitionSupported.mockReturnValue(true);
		alwaysOnMic.set(true);
		agentName.set('Tilora');
		askAssistant.mockResolvedValue({ text: 'Tomorrow will be rainy.', action: null });

		let capturedCallback: ((query: string) => void) | undefined;
		startContinuousListening.mockImplementation((opts) => {
			const cOpts = opts as { onWakeWordDetected: (query: string) => void };
			capturedCallback = cOpts?.onWakeWordDetected;
			return { stop: vi.fn(), pause: vi.fn(), resume: vi.fn() };
		});

		render(Page);

		expect(startContinuousListening).toHaveBeenCalled();
		expect(
			screen.getByRole('button', { name: 'Always-on microphone active: listening for "Tilora"' }),
		).toBeInTheDocument();

		// Simulate wake word detected with a command
		if (capturedCallback) {
			capturedCallback('what is tomorrow weather');
		}

		await waitFor(() => expect(askAssistant).toHaveBeenCalledWith('what is tomorrow weather'));
		expect(playChime).toHaveBeenCalled();
		expect(await screen.findByText('what is tomorrow weather')).toBeInTheDocument();
		expect(await screen.findByText('Tomorrow will be rainy.')).toBeInTheDocument();
		expect(speak).toHaveBeenCalledWith('Tomorrow will be rainy.', expect.anything());
	});

	it('displays permission denied message when SpeechError code is not-allowed', async () => {
		isSpeechRecognitionSupported.mockReturnValue(true);
		alwaysOnMic.set(false);
		const { SpeechError } = await import('$lib/speech');
		listenOnce.mockRejectedValue(new SpeechError('Permission denied', 'not-allowed'));

		render(Page);

		const micButton = screen.getByRole('button', { name: 'Ask a question' });
		await fireEvent.click(micButton);

		expect(
			await screen.findByText('Microphone permission was denied. Check your browser permissions.'),
		).toBeInTheDocument();
	});

	it('displays service unavailable message when SpeechError code is service-unavailable', async () => {
		isSpeechRecognitionSupported.mockReturnValue(true);
		alwaysOnMic.set(false);
		const { SpeechError } = await import('$lib/speech');
		listenOnce.mockRejectedValue(new SpeechError('Service unavailable', 'service-unavailable'));

		render(Page);

		const micButton = screen.getByRole('button', { name: 'Ask a question' });
		await fireEvent.click(micButton);

		expect(
			await screen.findByText(
				'Speech recognition is unavailable in this browser. Enable OpenAI Whisper in Settings or use Google Chrome / Edge.',
			),
		).toBeInTheDocument();
	});
});
