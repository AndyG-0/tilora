import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const {
	goto,
	widgetDetail,
	updateWidgetSettings,
	hdhomerunTranscodePresets,
	hdhomerunPlaylistUrl,
	hdhomerunPlaybackUrl,
	hdhomerunHwaccelDiagnostics,
} = vi.hoisted(() => ({
	goto: vi.fn(),
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
	hdhomerunTranscodePresets: vi.fn(),
	hdhomerunPlaylistUrl: vi.fn((widgetId: string, ch: string) => `https://example.com/${widgetId}/playlist/${ch}`),
	hdhomerunPlaybackUrl: vi.fn((url: string) => `https://example.com/proxy?src=${url}`),
	hdhomerunHwaccelDiagnostics: vi.fn(),
}));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({
	api: {
		widgetDetail,
		updateWidgetSettings,
		hdhomerunTranscodePresets,
		hdhomerunPlaylistUrl,
		hdhomerunPlaybackUrl,
		hdhomerunHwaccelDiagnostics,
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
	playback_mode: 'server_transcode',
	hwaccel: 'software',
	custom_ffmpeg_args: '',
	hwaccel_device: '/dev/dri/renderD128',
	ffmpeg_debug: false,
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

		expect(screen.getByText('Not connected yet — set up HDHomeRun in Network Settings.')).toBeInTheDocument();
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

	it('loads transcode presets when opening the playback settings editor', async () => {
		hdhomerunTranscodePresets.mockResolvedValue([
			{ id: 'software', label: 'Software', description: 'CPU only', input_args: [], output_args: ['-c:v', 'libx264'] },
		]);

		render(HDHomeRunDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit playback settings'));

		expect(await screen.findByText('Software')).toBeInTheDocument();
	});

	it('saves playback settings and refetches', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue(connected);

		render(HDHomeRunDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit playback settings'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('hdhomerun', {
				playback_mode: 'server_transcode',
				hwaccel: 'software',
				custom_ffmpeg_args: '',
				hwaccel_device: '/dev/dri/renderD128',
				ffmpeg_debug: false,
			}),
		);
		expect(widgetDetail).toHaveBeenCalledWith('hdhomerun');
	});

	it('previews the vaapi command with the configured render device substituted in', async () => {
		hdhomerunTranscodePresets.mockResolvedValue([
			{
				id: 'vaapi',
				label: 'VAAPI',
				description: 'Hardware encode',
				input_args: ['-vaapi_device', '{device}'],
				output_args: ['-vf', 'yadif=deint=interlaced,format=nv12,hwupload', '-c:v', 'h264_vaapi'],
				hardware: true,
			},
		]);

		render(HDHomeRunDetail, {
			props: { data: { ...connected, hwaccel: 'vaapi', hwaccel_device: '/dev/dri/renderD129' } },
		});

		await fireEvent.click(screen.getByText('Edit playback settings'));

		const preview = await screen.findByText(/-vaapi_device/);
		expect(preview.textContent).toContain('-vaapi_device /dev/dri/renderD129');
		expect(preview.textContent).toContain('hwupload');
		// Not '{device}' left unsubstituted, and not the verbose log level
		// while ffmpeg_debug is off.
		expect(preview.textContent).not.toContain('{device}');
		expect(preview.textContent).toContain('-loglevel warning');
	});

	it('previews custom arguments split the way the backend splits them', async () => {
		hdhomerunTranscodePresets.mockResolvedValue([
			{ id: 'custom', label: 'Custom', description: 'Manual', input_args: [], output_args: [], hardware: false },
		]);

		render(HDHomeRunDetail, {
			props: {
				data: {
					...connected,
					hwaccel: 'custom',
					// A quoted filter graph: split(/\s+/) would break this into
					// three tokens where shlex.split keeps it as one.
					custom_ffmpeg_args: '-vf "scale=1280:720, format=nv12" -c:v libx264',
					ffmpeg_debug: true,
				},
			},
		});

		await fireEvent.click(screen.getByText('Edit playback settings'));

		const preview = await screen.findByText(/libx264/);
		expect(preview.textContent).toContain('-vf scale=1280:720, format=nv12 -c:v libx264');
		expect(preview.textContent).toContain('-loglevel verbose');
	});

	it('runs the hardware acceleration diagnostics and shows the findings', async () => {
		hdhomerunTranscodePresets.mockResolvedValue([]);
		hdhomerunHwaccelDiagnostics.mockResolvedValue({
			device: '/dev/dri/renderD128',
			process: { uid: 1000, gid: 1000, groups: [1000, 993] },
			dri: {
				dir_exists: true,
				devices: [
					{
						path: '/dev/dri/renderD128',
						mode: 'crw-rw----',
						owner_uid: 0,
						owner_gid: 993,
						readable: true,
						writable: true,
					},
				],
			},
			ffmpeg: { version: 'ffmpeg 5.1', hwaccels: ['vaapi'], hardware_encoders: ['h264_vaapi'], ffmpeg_available: true },
			vainfo: {
				ok: true,
				output: '',
				driver: 'Intel iHD driver',
				profiles: {},
				can_decode_mpeg2: false,
				can_encode_h264: true,
			},
			probes: {
				software: { ok: true, command: 'ffmpeg ...', exit_code: 0, output: '' },
				vaapi_full: { ok: false, command: 'ffmpeg ...', exit_code: 1, output: 'Impossible to convert between formats' },
			},
			sample_error: null,
			summary: ['VA-API driver loaded for /dev/dri/renderD128: Intel iHD driver.'],
		});

		render(HDHomeRunDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit playback settings'));
		await fireEvent.click(await screen.findByText('Run diagnostics'));

		expect(await screen.findByText(/VA-API driver loaded/)).toBeInTheDocument();
		expect(hdhomerunHwaccelDiagnostics).toHaveBeenCalledWith('hdhomerun', '/dev/dri/renderD128');
		expect(screen.getByText('Backend runs as uid 1000, gid 1000, groups 1000, 993.')).toBeInTheDocument();
		// A failing preset shows its ffmpeg output; a passing one doesn't.
		expect(screen.getByText(/Impossible to convert between formats/)).toBeInTheDocument();
	});

	it('reports a diagnostics run that could not complete', async () => {
		hdhomerunTranscodePresets.mockResolvedValue([]);
		hdhomerunHwaccelDiagnostics.mockRejectedValue(new Error('500'));

		render(HDHomeRunDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit playback settings'));
		await fireEvent.click(await screen.findByText('Run diagnostics'));

		expect(await screen.findByText('Could not run the diagnostics.')).toBeInTheDocument();
	});

	it('hides the edit-playback-settings control for a non-admin', () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });

		render(HDHomeRunDetail, { props: { data: connected } });

		expect(screen.queryByText('Edit playback settings')).not.toBeInTheDocument();
	});
});
