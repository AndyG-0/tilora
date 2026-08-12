import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { jellyfinItemDetail, jellyfinSubtitleUrl, jellyfinStreamUrl, updatePreferences, getPreferences } = vi.hoisted(
	() => ({
		jellyfinItemDetail: vi.fn(),
		jellyfinSubtitleUrl: vi.fn(
			(wId: string, itemId: string, idx: number) => `https://example.com/${wId}/${itemId}/subtitles/${idx}.vtt`,
		),
		jellyfinStreamUrl: vi.fn(
			(wId: string, itemId: string, opts?: { audioStreamIndex?: number }) =>
				`https://example.com/${wId}/${itemId}/stream${opts?.audioStreamIndex !== undefined ? `?audio_stream_index=${opts.audioStreamIndex}` : ''}`,
		),
		updatePreferences: vi.fn().mockResolvedValue({}),
		getPreferences: vi.fn().mockResolvedValue({}),
	}),
);

vi.mock('$lib/api', () => ({
	api: {
		jellyfinItemDetail,
		jellyfinSubtitleUrl,
		jellyfinStreamUrl,
		updatePreferences,
		getPreferences,
	},
}));

import JellyfinPlayer from './JellyfinPlayer.svelte';

const defaultProps = {
	widgetId: 'jf1',
	itemId: 'm1',
	src: 'https://example.com/stream/m1',
	title: 'Inception',
	onClose: vi.fn(),
};

const sampleDetail = {
	id: 'm1',
	name: 'Inception',
	type: 'Movie',
	overview: 'A thief who steals corporate secrets...',
	year: 2010,
	runtime_minutes: 148,
	container: 'mkv',
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

describe('JellyfinPlayer', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		jellyfinItemDetail.mockResolvedValue(sampleDetail);
		updatePreferences.mockResolvedValue({});
		getPreferences.mockResolvedValue({});
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

	it('opens audio track menu and switches audio track', async () => {
		render(JellyfinPlayer, { props: defaultProps });

		const audioBtn = await screen.findByText(/Audio Tracks/);
		await fireEvent.click(audioBtn);

		const commentaryBtn = screen.getByText('Director Commentary');
		await fireEvent.click(commentaryBtn);

		expect(jellyfinStreamUrl).toHaveBeenCalledWith('jf1', 'm1', { audioStreamIndex: 2 });
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
		expect(screen.getByText(/mkv/i)).toBeInTheDocument();
		expect(screen.getByText('1920×1080')).toBeInTheDocument();
		expect(screen.getByText(/h264/i)).toBeInTheDocument();

		const infoClose = screen.getByRole('button', { name: '✕' });
		await fireEvent.click(infoClose);

		expect(screen.queryByRole('dialog', { name: 'Playback Info' })).not.toBeInTheDocument();
	});
});
