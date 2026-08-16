import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

// widgetComponents.ts pulls in every real Detail/Screensaver component, including
// PhotoDetail/PhotoScreensaver, which read PUBLIC_API_BASE_URL from this module
// at import time.
vi.mock('$env/dynamic/public', () => ({ env: { PUBLIC_API_BASE_URL: 'http://api.test' } }));

// widgetComponents.ts imports every real Detail component, and $lib/stores/widgets
// calls api.listWidgets() eagerly at module-load time (mirrors +layout.svelte's
// test) — only widgetDetail is actually exercised by Screensaver itself, but
// listWidgets must resolve to something so the store's eager reload doesn't throw.
const { widgetDetail, listWidgets } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	listWidgets: vi.fn().mockResolvedValue([]),
}));
vi.mock('$lib/api', () => ({ api: { widgetDetail, listWidgets } }));

// Stub the dispatcher (with a real, compiled Svelte component) so this file
// stays focused on Screensaver.svelte's own orchestration (id/type selection,
// rotation timing, stale-id skip, empty fallback) rather than any
// visual/wordy component's internal markup.
vi.mock('$lib/components/screensaver/ScreensaverContent.svelte', async () => {
	const stub = await import('./ScreensaverContent.test-stub.svelte');
	return { default: stub.default };
});

import Screensaver from './Screensaver.svelte';
import { widgets } from '$lib/stores/widgets';
import type { ScreensaverSettings } from '$lib/api';

function settings(overrides: Partial<ScreensaverSettings> = {}): ScreensaverSettings {
	return {
		enabled: true,
		idle_timeout_seconds: 300,
		rotation_interval_seconds: 10,
		widget_ids: [],
		text_animation_style: 'marquee',
		led_color: '#ff8a00',
		text_pause_seconds: 8,
		flipboard_pattern: 'top_to_bottom',
		...overrides,
	};
}

const dateWidget = (id: string) => ({
	id,
	type: 'date',
	name: 'Date',
	layout: { col: 0, row: 0, colSpan: 1, rowSpan: 1 },
	tab: 'main',
	refresh_interval_seconds: 60,
});

const jellyfinWidget = (id: string) => ({
	id,
	type: 'jellyfin',
	name: 'Jellyfin',
	layout: { col: 0, row: 0, colSpan: 1, rowSpan: 1 },
	tab: 'main',
	refresh_interval_seconds: 60,
});

describe('Screensaver', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		localStorage.clear();
		widgetDetail.mockReset();
		widgets.set([dateWidget('w1'), dateWidget('w2')]);
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('renders the dispatcher with the current widget id for the first widget id', async () => {
		widgetDetail.mockResolvedValue({ timezone: 'UTC' });

		render(Screensaver, { props: { settings: settings({ widget_ids: ['w1'] }), ondismiss: vi.fn() } });

		await vi.waitFor(() => expect(screen.getByText(/type=date/)).toBeInTheDocument());
	});

	it('rotates to the next widget id once the rotation interval elapses', async () => {
		widgetDetail.mockImplementation((id: string) =>
			Promise.resolve({ timezone: id === 'w1' ? 'UTC' : 'America/New_York' }),
		);

		render(Screensaver, {
			props: { settings: settings({ widget_ids: ['w1', 'w2'], rotation_interval_seconds: 10 }), ondismiss: vi.fn() },
		});
		await vi.waitFor(() => expect(screen.getByText(/UTC/)).toBeInTheDocument());

		await vi.advanceTimersByTimeAsync(10_000);

		await vi.waitFor(() => expect(screen.getByText(/America\/New_York/)).toBeInTheDocument());
	});

	it('skips a widget id that no longer resolves to a real widget', async () => {
		widgetDetail.mockResolvedValue({ timezone: 'UTC' });

		render(Screensaver, {
			props: { settings: settings({ widget_ids: ['stale-id', 'w1'] }), ondismiss: vi.fn() },
		});

		await vi.waitFor(() => expect(widgetDetail).toHaveBeenCalledWith('w1'));
		expect(widgetDetail).not.toHaveBeenCalledWith('stale-id');
	});

	it('skips a widget id whose type is no longer allowed in the screensaver', async () => {
		widgets.set([jellyfinWidget('w-jf'), dateWidget('w1')]);
		widgetDetail.mockResolvedValue({ timezone: 'UTC' });

		render(Screensaver, {
			props: { settings: settings({ widget_ids: ['w-jf', 'w1'] }), ondismiss: vi.fn() },
		});

		await vi.waitFor(() => expect(widgetDetail).toHaveBeenCalledWith('w1'));
		expect(widgetDetail).not.toHaveBeenCalledWith('w-jf');
	});

	it('forwards the configured text animation style to the dispatcher', async () => {
		widgetDetail.mockResolvedValue({ timezone: 'UTC' });

		render(Screensaver, {
			props: {
				settings: settings({ widget_ids: ['w1'], text_animation_style: 'matrix' }),
				ondismiss: vi.fn(),
			},
		});

		await vi.waitFor(() => expect(screen.getByText(/style=matrix/)).toBeInTheDocument());
	});

	it('resumes rotation from a previously stored rotation index', async () => {
		localStorage.setItem('screensaver:rotationIndex', '1');
		widgetDetail.mockImplementation((id: string) =>
			Promise.resolve({ timezone: id === 'w1' ? 'UTC' : 'America/New_York' }),
		);

		render(Screensaver, {
			props: { settings: settings({ widget_ids: ['w1', 'w2'] }), ondismiss: vi.fn() },
		});

		await vi.waitFor(() => expect(screen.getByText(/America\/New_York/)).toBeInTheDocument());
	});

	it('persists the rotation index to localStorage once it advances', async () => {
		widgetDetail.mockImplementation((id: string) =>
			Promise.resolve({ timezone: id === 'w1' ? 'UTC' : 'America/New_York' }),
		);

		render(Screensaver, {
			props: { settings: settings({ widget_ids: ['w1', 'w2'], rotation_interval_seconds: 10 }), ondismiss: vi.fn() },
		});
		await vi.waitFor(() => expect(screen.getByText(/UTC/)).toBeInTheDocument());

		await vi.advanceTimersByTimeAsync(10_000);

		await vi.waitFor(() => expect(localStorage.getItem('screensaver:rotationIndex')).toBe('1'));
	});

	it('shows a fallback when there are no widget ids to rotate through', () => {
		render(Screensaver, { props: { settings: settings({ widget_ids: [] }), ondismiss: vi.fn() } });

		expect(screen.getByText('Screensaver')).toBeInTheDocument();
	});
});
