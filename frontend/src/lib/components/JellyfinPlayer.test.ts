import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

// hls.js drives an MSE pipeline that jsdom has no implementation for, so the
// player itself is stubbed down to the one thing this component's error
// handling depends on: the ERROR event and its `fatal` flag.
const { HlsConstructor, hlsInstances, hlsListeners } = vi.hoisted(() => {
	const hlsListeners = new Map<string, (...args: unknown[]) => void>();
	const hlsInstances: { loadSource: ReturnType<typeof vi.fn>; attachMedia: ReturnType<typeof vi.fn> }[] = [];
	// A plain `function` (not an arrow) so it stays constructible under `new`
	// once wrapped by vi.fn.
	const HlsConstructor = vi.fn(function (this: unknown) {
		const instance = {
			on: (event: string, handler: (...args: unknown[]) => void) => hlsListeners.set(event, handler),
			loadSource: vi.fn(),
			attachMedia: vi.fn(),
			destroy: vi.fn(),
		};
		hlsInstances.push(instance);
		Object.assign(this as object, instance);
	});
	(HlsConstructor as unknown as { isSupported: () => boolean }).isSupported = () => true;
	(HlsConstructor as unknown as { Events: { ERROR: string } }).Events = { ERROR: 'hlsError' };
	return { HlsConstructor, hlsInstances, hlsListeners };
});
vi.mock('hls.js', () => ({ default: HlsConstructor }));

const {
	jellyfinItemDetail,
	jellyfinSubtitleUrl,
	jellyfinStreamUrl,
	jellyfinHlsMasterUrl,
	jellyfinStopPlayback,
	jellyfinReportPlaybackStart,
	jellyfinReportPlaybackProgress,
	updatePreferences,
	getPreferences,
} = vi.hoisted(() => ({
	jellyfinItemDetail: vi.fn(),
	jellyfinSubtitleUrl: vi.fn(
		(wId: string, itemId: string, idx: number) => `https://example.com/${wId}/${itemId}/subtitles/${idx}.vtt`,
	),
	jellyfinStreamUrl: vi.fn((wId: string, itemId: string) => `https://example.com/${wId}/${itemId}/stream`),
	jellyfinHlsMasterUrl: vi.fn(
		(wId: string, itemId: string, opts: { playSessionId: string; audioStreamIndex?: number }) =>
			`https://example.com/${wId}/${itemId}/hls/master.m3u8?play_session_id=${opts.playSessionId}${opts.audioStreamIndex !== undefined ? `&audio_stream_index=${opts.audioStreamIndex}` : ''}`,
	),
	jellyfinStopPlayback: vi.fn().mockResolvedValue({ status: 'ok' }),
	jellyfinReportPlaybackStart: vi.fn().mockResolvedValue({ status: 'ok' }),
	jellyfinReportPlaybackProgress: vi.fn().mockResolvedValue({ status: 'ok' }),
	updatePreferences: vi.fn().mockResolvedValue({}),
	getPreferences: vi.fn().mockResolvedValue({}),
}));

vi.mock('$lib/api', () => ({
	api: {
		jellyfinItemDetail,
		jellyfinSubtitleUrl,
		jellyfinStreamUrl,
		jellyfinHlsMasterUrl,
		jellyfinStopPlayback,
		jellyfinReportPlaybackStart,
		jellyfinReportPlaybackProgress,
		updatePreferences,
		getPreferences,
	},
}));

const { shouldForceTranscode, markDirectPlayFailed } = vi.hoisted(() => ({
	shouldForceTranscode: vi.fn(() => false),
	markDirectPlayFailed: vi.fn(),
}));
vi.mock('$lib/jellyfinPlaybackCache', () => ({ shouldForceTranscode, markDirectPlayFailed }));

import JellyfinPlayer from './JellyfinPlayer.svelte';

const defaultProps = {
	widgetId: 'jf1',
	itemId: 'm1',
	title: 'Inception',
	onClose: vi.fn(),
};

const mp4Detail = {
	id: 'm1',
	name: 'Inception',
	type: 'Movie',
	overview: 'A thief who steals corporate secrets...',
	year: 2010,
	runtime_minutes: 148,
	container: 'mp4',
	video_stream: {
		codec: 'h264',
		width: 1920,
		height: 1080,
		aspect_ratio: '16:9',
		framerate: 23.976,
		bitrate: 8000000,
	},
	audio_streams: [
		{ index: 1, display_title: 'English (AAC Stereo)', language: 'eng', codec: 'aac', channels: 2, is_default: true },
		{ index: 2, display_title: 'Director Commentary', language: 'eng', codec: 'aac', channels: 2, is_default: false },
	],
	subtitle_streams: [
		{ index: 3, display_title: 'English (SDH)', language: 'eng', codec: 'subrip', is_default: false, is_forced: false },
		{ index: 4, display_title: 'Spanish', language: 'spa', codec: 'subrip', is_default: false, is_forced: false },
	],
	chapters: [
		{ name: 'Prologue', start_seconds: 0 },
		{ name: 'The Heist', start_seconds: 300 },
		{ name: 'Dream Level 1', start_seconds: 1200 },
	],
};

const mkvDetail = { ...mp4Detail, container: 'mkv' };

// jsdom has no real media decoder, so canPlayType is stubbed per test to
// drive the component's Direct Play eligibility check and its native-HLS
// detection (`canPlayType('application/vnd.apple.mpegurl')`).
function stubCanPlayType(fn: (type: string) => string) {
	vi.spyOn(HTMLMediaElement.prototype, 'canPlayType').mockImplementation(fn as never);
}

describe('JellyfinPlayer', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		hlsListeners.clear();
		hlsInstances.length = 0;
		jellyfinItemDetail.mockResolvedValue(mp4Detail);
		shouldForceTranscode.mockReturnValue(false);
		updatePreferences.mockResolvedValue({});
		getPreferences.mockResolvedValue({});
		// Default: nothing natively playable, forcing HLS via hls.js unless a
		// test overrides this to exercise Direct Play or native HLS.
		stubCanPlayType(() => '');
	});

	it('renders media title and calls onClose when close button clicked', async () => {
		render(JellyfinPlayer, { props: defaultProps });

		expect(screen.getByRole('dialog', { name: 'Inception' })).toBeInTheDocument();

		const closeBtn = screen.getByRole('button', { name: 'Close player' });
		await fireEvent.click(closeBtn);

		expect(defaultProps.onClose).toHaveBeenCalled();
	});

	it('fetches item detail and displays chapter, audio, and subtitle controls', async () => {
		render(JellyfinPlayer, { props: defaultProps });

		expect(jellyfinItemDetail).toHaveBeenCalledWith('jf1', 'm1');

		expect(await screen.findByText(/Chapters \(3\)/)).toBeInTheDocument();
		expect(screen.getByText(/CC/)).toBeInTheDocument();
		expect(screen.getByText(/Audio Tracks/)).toBeInTheDocument();
	});

	it('opens subtitle menu and selects a subtitle track', async () => {
		render(JellyfinPlayer, { props: defaultProps });

		const ccBtn = await screen.findByText(/CC/);
		await fireEvent.click(ccBtn);

		expect(screen.getByText('English (SDH)')).toBeInTheDocument();
		expect(screen.getByText('Spanish')).toBeInTheDocument();

		await fireEvent.click(screen.getByText('Spanish'));

		expect(jellyfinSubtitleUrl).toHaveBeenCalledWith('jf1', 'm1', 4);
	});

	it('opens chapters menu and jumps to selected chapter', async () => {
		render(JellyfinPlayer, { props: defaultProps });

		const chaptersBtn = await screen.findByText(/Chapters \(3\)/);
		await fireEvent.click(chaptersBtn);

		expect(screen.getAllByText('Prologue').length).toBeGreaterThan(0);
		expect(screen.getByText('The Heist')).toBeInTheDocument();

		await fireEvent.click(screen.getByText('The Heist'));
	});

	it('toggles playback info panel displaying media technical specs', async () => {
		render(JellyfinPlayer, { props: defaultProps });

		const infoBtn = await screen.findByRole('button', { name: 'Playback Info' });
		await fireEvent.click(infoBtn);

		expect(screen.getByRole('dialog', { name: 'Playback Info' })).toBeInTheDocument();
		expect(screen.getByText(/mp4/i)).toBeInTheDocument();
		expect(screen.getByText('1920×1080')).toBeInTheDocument();
		expect(screen.getByText(/h264/i)).toBeInTheDocument();

		const infoClose = screen.getByRole('button', { name: '✕' });
		await fireEvent.click(infoClose);

		expect(screen.queryByRole('dialog', { name: 'Playback Info' })).not.toBeInTheDocument();
	});

	it('uses Direct Play for an eligible mp4/h264/aac item', async () => {
		stubCanPlayType((type) => (type.startsWith('video/mp4') ? 'probably' : ''));

		render(JellyfinPlayer, { props: defaultProps });

		await vi.waitFor(() => expect(jellyfinStreamUrl).toHaveBeenCalledWith('jf1', 'm1'));
		expect(jellyfinHlsMasterUrl).not.toHaveBeenCalled();

		const infoBtn = await screen.findByRole('button', { name: 'Playback Info' });
		await fireEvent.click(infoBtn);
		expect(screen.getByText('Direct Play')).toBeInTheDocument();
	});

	it('falls back to HLS for a container Direct Play cannot demux', async () => {
		jellyfinItemDetail.mockResolvedValue(mkvDetail);
		stubCanPlayType(() => '');

		render(JellyfinPlayer, { props: defaultProps });

		await vi.waitFor(() =>
			expect(jellyfinHlsMasterUrl).toHaveBeenCalledWith('jf1', 'm1', {
				playSessionId: expect.any(String),
				audioStreamIndex: 1,
			}),
		);
		expect(jellyfinStreamUrl).not.toHaveBeenCalled();
		await vi.waitFor(() => expect(HlsConstructor).toHaveBeenCalled());
		expect(hlsInstances[0]?.loadSource).toHaveBeenCalled();
	});

	it('uses native HLS without loading hls.js when the browser supports it', async () => {
		jellyfinItemDetail.mockResolvedValue(mkvDetail);
		stubCanPlayType((type) => (type === 'application/vnd.apple.mpegurl' ? 'probably' : ''));

		render(JellyfinPlayer, { props: defaultProps });

		await vi.waitFor(() => expect(jellyfinHlsMasterUrl).toHaveBeenCalled());
		expect(HlsConstructor).not.toHaveBeenCalled();
	});

	it('falls back live to HLS and remembers the device on a runtime Direct Play failure', async () => {
		stubCanPlayType((type) => (type.startsWith('video/mp4') ? 'probably' : ''));

		render(JellyfinPlayer, { props: defaultProps });
		await vi.waitFor(() => expect(jellyfinStreamUrl).toHaveBeenCalled());

		const video = document.querySelector('video')!;
		await fireEvent.error(video);

		expect(markDirectPlayFailed).toHaveBeenCalled();
		await vi.waitFor(() => expect(jellyfinHlsMasterUrl).toHaveBeenCalled());

		const infoBtn = await screen.findByRole('button', { name: 'Playback Info' });
		await fireEvent.click(infoBtn);
		expect(screen.getByText('Transcoding (HLS)')).toBeInTheDocument();
	});

	it('skips Direct Play entirely when this device previously failed it', async () => {
		shouldForceTranscode.mockReturnValue(true);
		stubCanPlayType((type) => (type.startsWith('video/mp4') ? 'probably' : ''));

		render(JellyfinPlayer, { props: defaultProps });

		await vi.waitFor(() => expect(jellyfinHlsMasterUrl).toHaveBeenCalled());
		expect(jellyfinStreamUrl).not.toHaveBeenCalled();
	});

	it('switching audio track forces an HLS transcode with the selected track', async () => {
		stubCanPlayType((type) => (type.startsWith('video/mp4') ? 'probably' : ''));

		render(JellyfinPlayer, { props: defaultProps });
		await vi.waitFor(() => expect(jellyfinStreamUrl).toHaveBeenCalled());

		const audioBtn = await screen.findByText(/Audio Tracks/);
		await fireEvent.click(audioBtn);
		await fireEvent.click(screen.getByText('Director Commentary'));

		await vi.waitFor(() =>
			expect(jellyfinHlsMasterUrl).toHaveBeenCalledWith('jf1', 'm1', {
				playSessionId: expect.any(String),
				audioStreamIndex: 2,
			}),
		);
	});

	it('reports playback start and shows a transcoding indicator while HLS is buffering', async () => {
		jellyfinItemDetail.mockResolvedValue(mkvDetail);
		stubCanPlayType(() => '');

		render(JellyfinPlayer, { props: defaultProps });

		await vi.waitFor(() => expect(jellyfinReportPlaybackStart).toHaveBeenCalledWith('jf1', 'm1', expect.any(String)));
		expect(screen.getByText('Transcoding…')).toBeInTheDocument();

		const video = document.querySelector('video')!;
		await fireEvent.playing(video);

		expect(screen.queryByText('Transcoding…')).not.toBeInTheDocument();
	});

	it('stops the HLS playback session on close', async () => {
		jellyfinItemDetail.mockResolvedValue(mkvDetail);
		stubCanPlayType(() => '');

		const { unmount } = render(JellyfinPlayer, { props: defaultProps });
		await vi.waitFor(() => expect(jellyfinHlsMasterUrl).toHaveBeenCalled());

		// In real usage, clicking close causes the parent to stop rendering
		// this component, which unmounts it and runs the attach action's
		// destroy() teardown.
		const closeBtn = screen.getByRole('button', { name: 'Close player' });
		await fireEvent.click(closeBtn);
		unmount();

		expect(jellyfinStopPlayback).toHaveBeenCalledWith('jf1', 'm1', expect.any(String), expect.any(Number));
	});
});
