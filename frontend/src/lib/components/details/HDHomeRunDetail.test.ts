import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const {
	goto,
	widgetDetail,
	updateWidgetSettings,
	hdhomerunTestTunerConnection,
	hdhomerunTestDvrConnection,
	hdhomerunTranscodePresets,
	hdhomerunPlaylistUrl,
	hdhomerunPlaybackUrl,
} = vi.hoisted(() => ({
	goto: vi.fn(),
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
	hdhomerunTestTunerConnection: vi.fn(),
	hdhomerunTestDvrConnection: vi.fn(),
	hdhomerunTranscodePresets: vi.fn(),
	hdhomerunPlaylistUrl: vi.fn((widgetId: string, ch: string) => `https://example.com/${widgetId}/playlist/${ch}`),
	hdhomerunPlaybackUrl: vi.fn((url: string) => `https://example.com/proxy?src=${url}`),
}));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({
	api: {
		widgetDetail,
		updateWidgetSettings,
		hdhomerunTestTunerConnection,
		hdhomerunTestDvrConnection,
		hdhomerunTranscodePresets,
		hdhomerunPlaylistUrl,
		hdhomerunPlaybackUrl,
	},
}));

let pageUrl = new URL('http://localhost/widget/hdhomerun');
vi.mock('$app/state', () => ({
	page: {
		params: { id: 'hdhomerun' },
		get url() {
			return pageUrl;
		},
	},
}));

import { user } from '$lib/stores/user';
import HDHomeRunDetail from './HDHomeRunDetail.svelte';

const notConnected = {
	tuner_connected: false,
	dvr_connected: false,
	guide_available: false,
	tuner_info: null,
	channels: [],
	tuners: [],
	dvr_info: null,
	recordings_in_progress: [],
	upcoming_recording_rules_count: 0,
	tuner_host: '',
	tuner_port: 80,
	dvr_host: '',
	dvr_port: 59090,
	epg_url: '',
	playback_mode: 'server_transcode',
	hwaccel: 'software',
	custom_ffmpeg_args: '',
	ffmpeg_command: '',
	favorite_channels: [] as string[],
};

const channel = {
	channel_number: '4.1',
	name: 'KDFW',
	is_hd: true,
	is_drm: false,
	stream_url: 'http://tuner.local/stream/4.1',
	playback_url: '/api/hdhomerun/hdhomerun/watch/4.1',
	now: { title: 'Evening News', episode_title: null, start: null, end: null },
	next: { title: 'Nightly Show', episode_title: null, start: null, end: null },
};

const connected = {
	...notConnected,
	tuner_connected: true,
	guide_available: true,
	tuner_info: {
		friendly_name: 'HDHomeRun Connect',
		model_number: 'HDHR5-2US',
		firmware_version: '20231218',
		tuner_count: 2,
	},
	channels: [channel],
};

describe('HDHomeRunDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		pageUrl = new URL('http://localhost/widget/hdhomerun');
		user.set({ id: 'admin-user', name: 'Admin', avatar: null, role: 'admin' });
	});

	it('shows a not-connected hint', () => {
		render(HDHomeRunDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — tap "Edit connection" to set up HDHomeRun.')).toBeInTheDocument();
	});

	it('renders tuner info and the channel lineup with guide entries', () => {
		render(HDHomeRunDetail, { props: { data: connected } });

		expect(screen.getByText(/HDHomeRun Connect/)).toBeInTheDocument();
		expect(screen.getByText('4.1')).toBeInTheDocument();
		expect(screen.getByText('KDFW')).toBeInTheDocument();
		expect(screen.getByText(/Evening News/)).toBeInTheDocument();
		expect(screen.getByText('Next: Nightly Show')).toBeInTheDocument();
	});

	it('toggles a channel as a favorite and persists it', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });

		render(HDHomeRunDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByRole('button', { name: 'Add to favorites' }));

		expect(updateWidgetSettings).toHaveBeenCalledWith('hdhomerun', { favorite_channels: ['4.1'] });
		expect(await screen.findByText('Favorites — Now Playing')).toBeInTheDocument();
	});

	it('shows the DVR section with recordings in progress', () => {
		render(HDHomeRunDetail, {
			props: {
				data: {
					...connected,
					dvr_connected: true,
					dvr_info: { friendly_name: 'DVR', version: '1.0', free_space_bytes: 500_000_000_000 },
					recordings_in_progress: [{ title: 'Big Game', channel_name: 'KDFW', start: null, record_end: null }],
					upcoming_recording_rules_count: 3,
				},
			},
		});

		expect(screen.getByText('● Recording')).toBeInTheDocument();
		expect(screen.getByText('Big Game')).toBeInTheDocument();
		expect(screen.getByText('Free space: 500.0 GB')).toBeInTheDocument();
		expect(screen.getByText('3 upcoming recording rules.')).toBeInTheDocument();
	});

	it('auto-launches playback from a ?watch= query param and strips it', async () => {
		pageUrl = new URL('http://localhost/widget/hdhomerun?watch=4.1');

		render(HDHomeRunDetail, { props: { data: connected } });

		expect(screen.getByRole('dialog', { name: '4.1 KDFW' })).toBeInTheDocument();
		expect(goto).toHaveBeenCalledWith(expect.any(URL), { replaceState: true, noScroll: true, keepFocus: true });
		const calledUrl = goto.mock.calls[0][0] as URL;
		expect(calledUrl.searchParams.get('watch')).toBeNull();
	});

	it('opens the player when watch is clicked and closes it', async () => {
		render(HDHomeRunDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByRole('button', { name: '▶ Watch' }));

		expect(screen.getByRole('dialog', { name: '4.1 KDFW' })).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Close player' }));

		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
	});

	it('loads transcode presets when opening the editor and tests the tuner connection', async () => {
		hdhomerunTranscodePresets.mockResolvedValue([
			{ id: 'software', label: 'Software', description: 'CPU only', input_args: [], output_args: ['-c:v', 'libx264'] },
		]);
		hdhomerunTestTunerConnection.mockResolvedValue({ ok: true, name: 'HDHomeRun Connect', error: null });

		render(HDHomeRunDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));

		expect(await screen.findByText('Software')).toBeInTheDocument();

		await fireEvent.click(screen.getAllByText('Test connection')[0]);

		expect(await screen.findByText('✓ Connected to HDHomeRun Connect')).toBeInTheDocument();
	});

	it('saves connection settings and refetches', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue(connected);

		render(HDHomeRunDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(widgetDetail).toHaveBeenCalledWith('hdhomerun');
	});

	it('hides the edit-connection control for a non-admin', () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });

		render(HDHomeRunDetail, { props: { data: connected } });

		expect(screen.queryByText('Edit connection')).not.toBeInTheDocument();
	});
});
