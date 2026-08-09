import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

// mpegts.js drives an MSE pipeline that jsdom has no implementation for, so
// the player itself is stubbed down to the one thing this component's error
// handling depends on: the ERROR event and its type argument.
const { createPlayer, listeners } = vi.hoisted(() => {
	const listeners = new Map<string, (...args: unknown[]) => void>();
	return {
		listeners,
		createPlayer: vi.fn(() => ({
			on: (event: string, handler: (...args: unknown[]) => void) => listeners.set(event, handler),
			attachMediaElement: vi.fn(),
			load: vi.fn(),
			play: vi.fn(),
			pause: vi.fn(),
			unload: vi.fn(),
			detachMediaElement: vi.fn(),
			destroy: vi.fn(),
		})),
	};
});
vi.mock('mpegts.js', () => ({
	default: {
		createPlayer,
		Events: { ERROR: 'error' },
		ErrorTypes: { NETWORK_ERROR: 'NetworkError', MEDIA_ERROR: 'MediaError' },
	},
}));

import HDHomeRunPlayer from './HDHomeRunPlayer.svelte';

const props = { src: 'https://example.com/stream/4.1', title: '4.1 KDFW', onClose: () => {} };

async function raiseError(errorType: string) {
	// Let the component's dynamic import('mpegts.js') resolve and register.
	await vi.waitFor(() => expect(listeners.has('error')).toBe(true));
	listeners.get('error')!(errorType);
}

describe('HDHomeRunPlayer', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		listeners.clear();
		vi.unstubAllGlobals();
	});

	it("shows the backend's failure detail on a network error", async () => {
		// mpegts.js discards the response body, so the component re-requests
		// the stream to read the 502's detail — the only place the real
		// ffmpeg failure is reported.
		const fetchMock = vi.fn().mockResolvedValue({
			ok: false,
			json: async () => ({ detail: 'ffmpeg exited with code 1: No VA display found for device' }),
		});
		vi.stubGlobal('fetch', fetchMock);

		render(HDHomeRunPlayer, { props });
		await raiseError('NetworkError');

		expect(await screen.findByText(/No VA display found for device/)).toBeInTheDocument();
		expect(fetchMock).toHaveBeenCalledWith(props.src, { credentials: 'include' });
	});

	it('falls back to the generic hint when the retry succeeds', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, body: { cancel: vi.fn() } }));

		render(HDHomeRunPlayer, { props });
		await raiseError('NetworkError');

		expect(await screen.findByText(/Playback failed/)).toBeInTheDocument();
		expect(screen.queryByText(/ffmpeg/)).not.toBeInTheDocument();
	});

	it('does not re-request the stream for a non-network error', async () => {
		const fetchMock = vi.fn();
		vi.stubGlobal('fetch', fetchMock);

		render(HDHomeRunPlayer, { props });
		await raiseError('MediaError');

		expect(await screen.findByText(/Playback failed/)).toBeInTheDocument();
		expect(fetchMock).not.toHaveBeenCalled();
	});
});
