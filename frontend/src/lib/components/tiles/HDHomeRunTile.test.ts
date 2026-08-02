import { render, screen } from '@testing-library/svelte';
import { fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import HDHomeRunTile from './HDHomeRunTile.svelte';

describe('HDHomeRunTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(HDHomeRunTile, { props: { widgetId: 'hdhr' } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('shows a not-connected state', async () => {
		widgetSummary.mockResolvedValue({
			tuner_connected: false,
			dvr_connected: false,
			channel_count: 0,
			guide_available: false,
			now_playing: [],
			active_recordings_count: 0,
		});

		render(HDHomeRunTile, { props: { widgetId: 'hdhr' } });

		expect(await screen.findByText('Not connected')).toBeInTheDocument();
	});

	it('renders the channel count and now-playing guide, and shows a recording badge', async () => {
		widgetSummary.mockResolvedValue({
			tuner_connected: true,
			dvr_connected: true,
			channel_count: 42,
			guide_available: true,
			now_playing: [{ channel_number: '4.1', channel_name: 'KDFW', title: 'Evening News', episode_title: null }],
			active_recordings_count: 1,
		});

		render(HDHomeRunTile, { props: { widgetId: 'hdhr' } });

		expect(await screen.findByText('42 channels')).toBeInTheDocument();
		expect(screen.getByText('● Recording')).toBeInTheDocument();
		expect(screen.getByText('Evening News')).toBeInTheDocument();
	});

	it('navigates to the watch view for a now-playing entry without maximizing the tile', async () => {
		widgetSummary.mockResolvedValue({
			tuner_connected: true,
			dvr_connected: false,
			channel_count: 10,
			guide_available: true,
			now_playing: [{ channel_number: '4.1', channel_name: 'KDFW', title: 'Evening News', episode_title: null }],
			active_recordings_count: 0,
		});

		render(HDHomeRunTile, { props: { widgetId: 'hdhr' } });
		const entry = await screen.findByText('Evening News');

		await fireEvent.click(entry.closest('button')!);

		expect(goto).toHaveBeenCalledWith('/widget/hdhr?watch=4.1');
	});
});
