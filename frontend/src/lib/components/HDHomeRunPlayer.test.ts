import { render, screen, fireEvent } from '@testing-library/svelte';
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

const {
	hdhomerunRecordingStreamUrl,
	hdhomerunRecordingDetail,
	hdhomerunRecordingCaptionsUrl,
	hdhomerunRecordingThumbnailVttUrl,
	hdhomerunRecordingThumbnailSpriteUrl,
} = vi.hoisted(() => ({
	hdhomerunRecordingStreamUrl: vi.fn(
		(widgetId: string, playUrl: string, options?: { start?: number; audioIndex?: number }) =>
			`https://example.com/${widgetId}/recording-stream?url=${playUrl}&start=${options?.start ?? ''}&audio=${options?.audioIndex ?? ''}`,
	),
	hdhomerunRecordingDetail: vi.fn(),
	hdhomerunRecordingCaptionsUrl: vi.fn(
		(widgetId: string, opts: { recordingId: string }) =>
			`https://example.com/${widgetId}/captions/${opts.recordingId}.vtt`,
	),
	hdhomerunRecordingThumbnailVttUrl: vi.fn(
		(widgetId: string, opts: { recordingId: string }) =>
			`https://example.com/${widgetId}/thumbs/${opts.recordingId}.vtt`,
	),
	hdhomerunRecordingThumbnailSpriteUrl: vi.fn(
		(widgetId: string, opts: { recordingId: string }) =>
			`https://example.com/${widgetId}/thumbs/${opts.recordingId}.jpg`,
	),
}));
vi.mock('$lib/api', () => ({
	api: {
		hdhomerunRecordingStreamUrl,
		hdhomerunRecordingDetail,
		hdhomerunRecordingCaptionsUrl,
		hdhomerunRecordingThumbnailVttUrl,
		hdhomerunRecordingThumbnailSpriteUrl,
	},
}));

// jsdom doesn't implement HTMLMediaElement.addTextTrack or VTTCue, so the
// component's caption-track management is faked out here the same way
// mpegts.js is above.
class FakeVTTCue {
	constructor(
		public startTime: number,
		public endTime: number,
		public text: string,
	) {}
}
(globalThis as unknown as { VTTCue: typeof FakeVTTCue }).VTTCue = FakeVTTCue;

function makeFakeTextTrack() {
	return {
		mode: 'hidden',
		cues: [] as FakeVTTCue[],
		addCue(cue: FakeVTTCue) {
			this.cues.push(cue);
		},
		removeCue(cue: FakeVTTCue) {
			this.cues = this.cues.filter((c) => c !== cue);
		},
	};
}
let fakeTextTrack = makeFakeTextTrack();
(HTMLMediaElement.prototype as unknown as { addTextTrack: () => typeof fakeTextTrack }).addTextTrack = () =>
	fakeTextTrack;

import HDHomeRunPlayer from './HDHomeRunPlayer.svelte';

const props = { src: 'https://example.com/stream/4.1', title: '4.1 KDFW', onClose: () => {} };

const seekableProps = {
	src: 'https://example.com/stream/4.1',
	title: 'Finished Show',
	onClose: () => {},
	widgetId: 'hdhomerun',
	playUrl: '/recorded/rec1',
	recordingId: 'rec1',
	startTimestamp: 1000,
	recordEndTimestamp: 2000,
	seekable: true,
};

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
		fakeTextTrack = makeFakeTextTrack();
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

	it('builds the stream URL from the start of a completed seekable recording', async () => {
		hdhomerunRecordingDetail.mockResolvedValue({
			is_in_progress: false,
			duration_seconds: 120,
			video: null,
			audio: [],
			has_captions: false,
		});
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));

		render(HDHomeRunPlayer, { props: seekableProps });

		await vi.waitFor(() =>
			expect(hdhomerunRecordingStreamUrl).toHaveBeenCalledWith('hdhomerun', '/recorded/rec1', {
				start: 0,
				audioIndex: undefined,
			}),
		);
		expect(createPlayer).toHaveBeenCalledWith(
			expect.objectContaining({
				url: 'https://example.com/hdhomerun/recording-stream?url=/recorded/rec1&start=0&audio=',
			}),
			expect.anything(),
		);
		expect(screen.getByRole('slider')).toBeInTheDocument();
	});

	it('parses the thumbnail VTT manifest and renders a hover preview at the scrubbed position', async () => {
		hdhomerunRecordingDetail.mockResolvedValue({
			is_in_progress: false,
			duration_seconds: 120,
			video: null,
			audio: [],
			has_captions: false,
		});
		const vtt = ['WEBVTT', '', '00:00:10.000 --> 00:00:20.000', 'rec1.jpg#xywh=0,0,160,90', ''].join('\n');
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, text: async () => vtt }));
		vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
			left: 0,
			right: 200,
			top: 0,
			bottom: 20,
			width: 200,
			height: 20,
			x: 0,
			y: 0,
			toJSON: () => {},
		});

		render(HDHomeRunPlayer, { props: seekableProps });

		const scrubBar = await screen.findByRole('slider');
		await vi.waitFor(() => expect(hdhomerunRecordingThumbnailSpriteUrl).toHaveBeenCalled());
		await fireEvent.mouseMove(scrubBar, { clientX: 20 });

		expect(await screen.findByText('0:10')).toBeInTheDocument();
		expect(hdhomerunRecordingThumbnailSpriteUrl).toHaveBeenCalledWith('hdhomerun', {
			url: '/recorded/rec1',
			recordingId: 'rec1',
			recordEnd: 2000,
		});
	});

	it('re-times caption cues to the new playback origin after a seek', async () => {
		// The captions VTT is generated once for the whole recording, so its
		// cue at absolute 00:05:00 stays at absolute 00:05:00 regardless of
		// where playback starts - but each seek resets the video element's
		// own currentTime to 0, so the cue must be re-added shifted by
		// -baseOffsetSeconds every time the playback origin moves, or it
		// drifts out of sync with what's on screen.
		hdhomerunRecordingDetail.mockResolvedValue({
			is_in_progress: false,
			duration_seconds: 1200,
			video: null,
			audio: [],
			has_captions: true,
		});
		const vtt = ['WEBVTT', '', '00:05:00.000 --> 00:05:02.000', 'Hello there', ''].join('\n');
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, text: async () => vtt, json: async () => ({}) }));
		vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
			left: 0,
			right: 1200,
			top: 0,
			bottom: 20,
			width: 1200,
			height: 20,
			x: 0,
			y: 0,
			toJSON: () => {},
		});

		render(HDHomeRunPlayer, { props: seekableProps });
		const scrubBar = await screen.findByRole('slider');

		await vi.waitFor(() => expect(fakeTextTrack.cues).toHaveLength(1));
		expect(fakeTextTrack.cues[0].startTime).toBeCloseTo(300);
		expect(fakeTextTrack.cues[0].endTime).toBeCloseTo(302);

		// Seek to 100s - now before the cue's absolute start, so it should
		// re-appear shifted by -100s instead of staying at its original time.
		await fireEvent.click(scrubBar, { clientX: 100 });

		await vi.waitFor(() => expect(fakeTextTrack.cues).toHaveLength(1));
		expect(fakeTextTrack.cues[0].startTime).toBeCloseTo(200);
		expect(fakeTextTrack.cues[0].endTime).toBeCloseTo(202);
	});

	it('strips ffmpeg\'s literal "\\h" CEA-608 space escape from caption text', async () => {
		hdhomerunRecordingDetail.mockResolvedValue({
			is_in_progress: false,
			duration_seconds: 1200,
			video: null,
			audio: [],
			has_captions: true,
		});
		const vtt = ['WEBVTT', '', '00:00:01.000 --> 00:00:02.000', '\\h\\h\\h\\h- Hello\\hthere', ''].join('\n');
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, text: async () => vtt, json: async () => ({}) }));

		render(HDHomeRunPlayer, { props: seekableProps });

		await vi.waitFor(() => expect(fakeTextTrack.cues).toHaveLength(1));
		expect(fakeTextTrack.cues[0].text).toBe('    - Hello there');
	});
});
