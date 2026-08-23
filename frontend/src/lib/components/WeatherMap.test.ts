import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

vi.mock('$env/dynamic/public', () => ({ env: { PUBLIC_API_BASE_URL: 'http://api.test' } }));

import WeatherMap from './WeatherMap.svelte';

const FRAME_1 = { time: 1700000000, path: '/v2/radar/1700000000' };
const FRAME_2 = { time: 1700000600, path: '/v2/radar/1700000600' };

const RAINVIEWER_RESPONSE = {
	host: 'https://tilecache.rainviewer.com',
	radar: { past: [FRAME_1, FRAME_2], nowcast: [] },
};

// Matches WeatherMap's own formatting so assertions aren't tied to a
// hardcoded timezone-dependent string.
function timeLabel(frame: { time: number }): string {
	return new Date(frame.time * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

describe('WeatherMap', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.unstubAllGlobals();
		vi.useRealTimers();
	});

	it('renders only the latest static frame on load, with no auto-play', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => RAINVIEWER_RESPONSE }));
		render(WeatherMap, { props: { latitude: 32.7555, longitude: -97.3308 } });

		const playButton = await vi.waitFor(() => screen.getByLabelText('Play'));
		expect(playButton).toBeInTheDocument();
		expect(screen.queryByLabelText('Pause')).not.toBeInTheDocument();
		expect(screen.getByText(timeLabel(FRAME_2))).toBeInTheDocument();
	});

	it('play button starts advancing frames on a timer', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => RAINVIEWER_RESPONSE }));
		render(WeatherMap, { props: { latitude: 32.7555, longitude: -97.3308 } });

		await vi.waitFor(() => screen.getByLabelText('Play'));
		await fireEvent.click(screen.getByLabelText('Play'));
		expect(screen.getByLabelText('Pause')).toBeInTheDocument();

		// Only two frames: the loop wraps from the latest back to the first.
		await vi.advanceTimersByTimeAsync(700);
		expect(screen.getByText(timeLabel(FRAME_1))).toBeInTheDocument();
	});

	it('pause stops the timer from advancing further', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => RAINVIEWER_RESPONSE }));
		render(WeatherMap, { props: { latitude: 32.7555, longitude: -97.3308 } });

		await vi.waitFor(() => screen.getByLabelText('Play'));
		await fireEvent.click(screen.getByLabelText('Play'));
		await vi.advanceTimersByTimeAsync(700);
		expect(screen.getByText(timeLabel(FRAME_1))).toBeInTheDocument();

		await fireEvent.click(screen.getByLabelText('Pause'));
		expect(screen.getByLabelText('Play')).toBeInTheDocument();

		await vi.advanceTimersByTimeAsync(2000);
		expect(screen.getByLabelText('Play')).toBeInTheDocument();
		expect(screen.getByText(timeLabel(FRAME_1))).toBeInTheDocument();
	});

	it('step forward and back work while paused', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => RAINVIEWER_RESPONSE }));
		render(WeatherMap, { props: { latitude: 32.7555, longitude: -97.3308 } });

		await vi.waitFor(() => screen.getByLabelText('Play'));
		expect(screen.getByText(timeLabel(FRAME_2))).toBeInTheDocument();

		await fireEvent.click(screen.getByLabelText('Previous frame'));
		expect(screen.getByText(timeLabel(FRAME_1))).toBeInTheDocument();

		await fireEvent.click(screen.getByLabelText('Next frame'));
		expect(screen.getByText(timeLabel(FRAME_2))).toBeInTheDocument();
	});

	it('does not crash and still renders the base map when the RainViewer fetch fails', async () => {
		vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network error')));
		render(WeatherMap, { props: { latitude: 32.7555, longitude: -97.3308 } });

		expect(screen.getByRole('region', { name: 'Precipitation radar' })).toBeInTheDocument();
		await vi.waitFor(() => expect(screen.queryByLabelText('Play')).not.toBeInTheDocument());
	});
});
