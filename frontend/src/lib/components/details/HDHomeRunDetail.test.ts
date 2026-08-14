import { render, screen, fireEvent, within } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const {
	goto,
	widgetDetail,
	updateWidgetSettings,
	hdhomerunTranscodePresets,
	hdhomerunPlaylistUrl,
	hdhomerunPlaybackUrl,
	hdhomerunHwaccelDiagnostics,
	hdhomerunRecordingStreamUrl,
	getHDHomeRunGuide,
	addHDHomeRunRecordingRule,
	deleteHDHomeRunRecordingRule,
} = vi.hoisted(() => ({
	goto: vi.fn(),
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
	hdhomerunTranscodePresets: vi.fn(),
	hdhomerunPlaylistUrl: vi.fn((widgetId: string, ch: string) => `https://example.com/${widgetId}/playlist/${ch}`),
	hdhomerunPlaybackUrl: vi.fn((url: string) => `https://example.com/proxy?src=${url}`),
	hdhomerunHwaccelDiagnostics: vi.fn(),
	hdhomerunRecordingStreamUrl: vi.fn(
		(widgetId: string, playUrl: string) => `https://example.com/${widgetId}/recording-stream?url=${playUrl}`,
	),
	getHDHomeRunGuide: vi.fn(),
	addHDHomeRunRecordingRule: vi.fn(),
	deleteHDHomeRunRecordingRule: vi.fn(),
}));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('mpegts.js', () => ({
	default: {
		createPlayer: vi.fn(() => ({
			on: vi.fn(),
			attachMediaElement: vi.fn(),
			load: vi.fn(),
			play: vi.fn(),
			pause: vi.fn(),
			unload: vi.fn(),
			detachMediaElement: vi.fn(),
			destroy: vi.fn(),
		})),
		Events: { ERROR: 'error' },
		ErrorTypes: { NETWORK_ERROR: 'NetworkError', MEDIA_ERROR: 'MediaError' },
	},
}));
vi.mock('$lib/api', () => ({
	api: {
		widgetDetail,
		updateWidgetSettings,
		hdhomerunTranscodePresets,
		hdhomerunPlaylistUrl,
		hdhomerunPlaybackUrl,
		hdhomerunHwaccelDiagnostics,
		hdhomerunRecordingStreamUrl,
		getHDHomeRunGuide,
		addHDHomeRunRecordingRule,
		deleteHDHomeRunRecordingRule,
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
	thumbnails_enabled: true,
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

const nowSeconds = () => Math.floor(Date.now() / 1000);

// A guide entry with an airing currently in progress, for exercising the
// grid's live-cell watch/record interactions.
const guideWithLiveAiring = () => [
	{
		channel_number: '4.1',
		channel_name: 'KDFW',
		airings: [
			{
				series_id: 'SH123',
				title: 'Evening News',
				episode_title: null,
				start: nowSeconds() - 60,
				end: nowSeconds() + 30 * 60,
			},
		],
	},
];

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
		localStorage.clear();
		getHDHomeRunGuide.mockResolvedValue([]);
		pageUrl = new URL('http://localhost/widget/hdhomerun');
		user.set({ id: 'admin-user', name: 'Admin', avatar: null, role: 'admin' });
	});

	it('shows a not-connected hint', () => {
		render(HDHomeRunDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — set up HDHomeRun in Network Settings.')).toBeInTheDocument();
	});

	it('renders tuner info and the channel lineup with guide entries', async () => {
		getHDHomeRunGuide.mockResolvedValue(guideWithLiveAiring());

		render(HDHomeRunDetail, { props: { data: connected } });

		expect(screen.getByText(/HDHomeRun Connect/)).toBeInTheDocument();
		expect(await screen.findByText('Evening News')).toBeInTheDocument();
		expect(screen.getByText('4.1')).toBeInTheDocument();
		expect(screen.getByText('KDFW')).toBeInTheDocument();
	});

	it('toggles a channel as a favorite and persists it', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });

		render(HDHomeRunDetail, { props: { data: connected } });

		await fireEvent.click(await screen.findByRole('button', { name: 'Add to favorites' }));

		expect(updateWidgetSettings).toHaveBeenCalledWith('hdhomerun', { favorite_channels: ['4.1'] });
		expect(await screen.findByRole('button', { name: 'Remove from favorites' })).toBeInTheDocument();
	});

	it('shows the DVR section with recordings in progress', async () => {
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

		await fireEvent.click(screen.getByRole('button', { name: 'DVR' }));

		expect(screen.getByText('● Recording')).toBeInTheDocument();
		expect(screen.getByText('Big Game')).toBeInTheDocument();
		expect(screen.getByText('Free space: 500.0 GB')).toBeInTheDocument();
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
		getHDHomeRunGuide.mockResolvedValue(guideWithLiveAiring());

		render(HDHomeRunDetail, { props: { data: connected } });

		const liveCell = (await screen.findByText('Evening News')).closest('.airing-cell');
		if (!liveCell) throw new Error('live airing cell not found');
		await fireEvent.click(liveCell);

		expect(screen.getByRole('dialog', { name: '4.1 KDFW' })).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Close player' }));

		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
	});

	it('surfaces the server-provided reason when a series recording rule is rejected', async () => {
		vi.useFakeTimers({ shouldAdvanceTime: true });
		getHDHomeRunGuide.mockResolvedValue(guideWithLiveAiring());
		// Mirrors the backend: a rejected recording_rules request (e.g. no active
		// HDHomeRun DVR subscription) surfaces as an Error carrying the server's
		// detail message, not a silent "success" with zero rules.
		addHDHomeRunRecordingRule.mockRejectedValue(new Error('no active DVR subscription'));

		render(HDHomeRunDetail, { props: { data: connected } });

		const liveCell = (await screen.findByText('Evening News')).closest('.airing-cell');
		if (!liveCell) throw new Error('live airing cell not found');

		await fireEvent.pointerDown(liveCell);
		await vi.advanceTimersByTimeAsync(500);

		await fireEvent.click(screen.getByRole('menuitem', { name: 'Record Series' }));

		expect(await screen.findByText('no active DVR subscription')).toBeInTheDocument();
		vi.useRealTimers();
	});

	it('shows a pending confirmation badge for a newly created rule until a later fetch confirms it', async () => {
		vi.useFakeTimers({ shouldAdvanceTime: true });
		getHDHomeRunGuide.mockResolvedValue(guideWithLiveAiring());
		const newRule = {
			RecordingRuleID: 'new-1',
			SeriesID: 'SH123',
			Title: 'Evening News',
		};
		addHDHomeRunRecordingRule.mockResolvedValue([newRule]);
		// Simulates SiliconDust's cloud API being eventually consistent: the
		// very next fetch right after creating the rule doesn't include it yet.
		widgetDetail.mockResolvedValue({ ...connected, recording_rules: [] });

		render(HDHomeRunDetail, { props: { data: connected } });

		const liveCell = (await screen.findByText('Evening News')).closest('.airing-cell');
		if (!liveCell) throw new Error('live airing cell not found');

		await fireEvent.pointerDown(liveCell);
		await vi.advanceTimersByTimeAsync(500);
		await fireEvent.click(screen.getByRole('menuitem', { name: 'Record Series' }));

		await vi.waitFor(() => expect(addHDHomeRunRecordingRule).toHaveBeenCalled());
		await fireEvent.click(screen.getByRole('button', { name: 'DVR' }));

		expect(await screen.findByText('Pending confirmation')).toBeInTheDocument();

		// A later fetch that does include the rule should clear the pending badge.
		widgetDetail.mockResolvedValue({ ...connected, recording_rules: [newRule] });
		hdhomerunTranscodePresets.mockResolvedValue([
			{ id: 'software', label: 'Software', description: 'CPU only', input_args: [], output_args: ['-c:v', 'libx264'] },
		]);
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		await fireEvent.click(screen.getByText('Edit playback settings'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(screen.queryByText('Pending confirmation')).not.toBeInTheDocument());
		vi.useRealTimers();
	});

	it('does not mark a pre-existing rule as pending just because it is missing from an unrelated fetch', async () => {
		vi.useFakeTimers({ shouldAdvanceTime: true });
		getHDHomeRunGuide.mockResolvedValue(guideWithLiveAiring());
		const oldRule = { RecordingRuleID: 'old-1', SeriesID: 'SH999', Title: 'Old Show' };
		const newRule = { RecordingRuleID: 'new-1', SeriesID: 'SH123', Title: 'Evening News' };
		const withOldRule = { ...connected, recording_rules: [oldRule] };
		addHDHomeRunRecordingRule.mockResolvedValue([oldRule, newRule]);
		// The old rule is still present in the fresh fetch — only the brand
		// new one hasn't propagated yet — so only the new one should ever be
		// flagged pending.
		widgetDetail.mockResolvedValue({ ...withOldRule, recording_rules: [oldRule] });

		render(HDHomeRunDetail, { props: { data: withOldRule } });

		const liveCell = (await screen.findByText('Evening News')).closest('.airing-cell');
		if (!liveCell) throw new Error('live airing cell not found');

		await fireEvent.pointerDown(liveCell);
		await vi.advanceTimersByTimeAsync(500);
		await fireEvent.click(screen.getByRole('menuitem', { name: 'Record Series' }));

		await vi.waitFor(() => expect(addHDHomeRunRecordingRule).toHaveBeenCalled());
		await fireEvent.click(screen.getByRole('button', { name: 'DVR' }));

		const oldCard = (await screen.findByText('Old Show')).closest('.rule-card');
		if (!oldCard) throw new Error('old rule card not found');
		expect(within(oldCard as HTMLElement).queryByText('Pending confirmation')).not.toBeInTheDocument();

		const newCard = screen.getByText('Evening News').closest('.rule-card');
		if (!newCard) throw new Error('new rule card not found');
		expect(within(newCard as HTMLElement).getByText('Pending confirmation')).toBeInTheDocument();
		vi.useRealTimers();
	});

	it('keeps showing a pending rule as pending after a reload, until a fresh fetch confirms it', async () => {
		getHDHomeRunGuide.mockResolvedValue([]);
		const newRule = { RecordingRuleID: 'new-1', SeriesID: 'SH123', Title: 'Evening News' };
		localStorage.setItem(
			'hdhomerun-pending-rules:hdhomerun',
			JSON.stringify([{ rule: newRule, createdAt: Date.now() }]),
		);
		// The initial server-rendered data (as if freshly reloaded) still
		// doesn't include the rule — the pending flag must survive the reload.
		render(HDHomeRunDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByRole('button', { name: 'DVR' }));
		expect(await screen.findByText('Pending confirmation')).toBeInTheDocument();
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
				thumbnails_enabled: true,
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

	it('marks a completed DVR-file recording as seekable when playing it', async () => {
		const { container } = render(HDHomeRunDetail, {
			props: {
				data: {
					...connected,
					dvr_connected: true,
					dvr_info: { friendly_name: 'DVR', version: '1.0', free_space_bytes: 500_000_000_000 },
					all_recordings: [
						{
							recording_id: 'rec1',
							title: 'Finished Show',
							channel_name: 'KDFW',
							start: 1000,
							record_end: 2000,
							play_url: '/recorded/rec1',
							is_dvr_file: true,
						},
					],
				},
			},
		});

		await fireEvent.click(screen.getByRole('button', { name: 'DVR' }));
		const watchButton = container.querySelector<HTMLButtonElement>('button.watch');
		if (!watchButton) throw new Error('watch button not found');
		await fireEvent.click(watchButton);

		expect(screen.getByRole('dialog', { name: 'Finished Show' })).toBeInTheDocument();
		expect(hdhomerunRecordingStreamUrl).toHaveBeenCalledWith('hdhomerun', '/recorded/rec1');
		expect(screen.getByRole('slider')).toBeInTheDocument();
	});

	it('does not mark a live-tuner placeholder (no DVR file yet) as seekable', async () => {
		const { container } = render(HDHomeRunDetail, {
			props: {
				data: {
					...connected,
					dvr_connected: true,
					dvr_info: { friendly_name: 'DVR', version: '1.0', free_space_bytes: 500_000_000_000 },
					all_recordings: [
						{
							recording_id: 'rec2',
							title: 'Currently Airing',
							channel_name: 'KDFW',
							start: 1000,
							record_end: null,
							play_url: '/auto/v4.1',
							is_dvr_file: false,
						},
					],
				},
			},
		});

		await fireEvent.click(screen.getByRole('button', { name: 'DVR' }));
		const watchButton = container.querySelector<HTMLButtonElement>('button.watch');
		if (!watchButton) throw new Error('watch button not found');
		await fireEvent.click(watchButton);

		expect(screen.getByRole('dialog', { name: 'Currently Airing' })).toBeInTheDocument();
		expect(screen.queryByRole('slider')).not.toBeInTheDocument();
	});

	it('hides the edit-playback-settings control for a non-admin', () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });

		render(HDHomeRunDetail, { props: { data: connected } });

		expect(screen.queryByText('Edit playback settings')).not.toBeInTheDocument();
	});

	it('displays tuner status popover with active channel and idle tuners', () => {
		const dataWithTuners = {
			...connected,
			tuners: [
				{
					index: 0,
					in_use: true,
					channel_number: '4.1',
					channel_name: 'KDFW',
					signal_strength_percent: 95,
					signal_quality_percent: 100,
					symbol_quality_percent: 100,
					network_rate_bps: 12000000,
				},
				{
					index: 1,
					in_use: false,
					channel_number: null,
					channel_name: null,
					signal_strength_percent: null,
					signal_quality_percent: null,
					symbol_quality_percent: null,
					network_rate_bps: null,
				},
			],
		};

		const { container } = render(HDHomeRunDetail, { props: { data: dataWithTuners } });

		expect(screen.getByText('2 tuners')).toBeInTheDocument();
		const popover = container.querySelector('.tuner-status-popover') as HTMLElement;
		expect(popover).toBeInTheDocument();
		expect(within(popover).getByText('Tuner Status')).toBeInTheDocument();
		expect(within(popover).getByText('Tuner 0')).toBeInTheDocument();
		expect(within(popover).getByText('4.1')).toBeInTheDocument();
		expect(within(popover).getByText('KDFW')).toBeInTheDocument();
		expect(within(popover).getByText('Signal 95%')).toBeInTheDocument();
		expect(within(popover).getByText('Tuner 1')).toBeInTheDocument();
		expect(within(popover).getByText('Idle')).toBeInTheDocument();
	});

	it('allows searching through programs in the guide and shows results panel', async () => {
		getHDHomeRunGuide.mockResolvedValue([
			{
				channel_number: '4.1',
				channel_name: 'KDFW',
				airings: [
					{
						series_id: 'SH101',
						title: 'Morning News',
						episode_title: 'Early Edition',
						synopsis: 'Local breaking news and weather.',
						start: nowSeconds() - 100,
						end: nowSeconds() + 1800,
					},
					{
						series_id: 'SH102',
						title: 'Evening Comedy',
						episode_title: null,
						synopsis: 'Funny sitcom series.',
						start: nowSeconds() + 7200,
						end: nowSeconds() + 9000,
					},
				],
			},
		]);

		const { container } = render(HDHomeRunDetail, { props: { data: connected } });

		const searchInput = await screen.findByPlaceholderText('Search programs…');
		expect(searchInput).toBeInTheDocument();

		// Search for "comedy"
		await fireEvent.input(searchInput, { target: { value: 'Comedy' } });

		expect(await screen.findByText('1 programs found')).toBeInTheDocument();
		const resultsPanel = container.querySelector('.search-results-panel') as HTMLElement;
		expect(resultsPanel).toBeInTheDocument();
		expect(within(resultsPanel).getByText('Evening Comedy')).toBeInTheDocument();
		expect(within(resultsPanel).getByText('Funny sitcom series.')).toBeInTheDocument();
		expect(within(resultsPanel).getByText('Show in guide')).toBeInTheDocument();

		// Clear search
		await fireEvent.click(screen.getAllByRole('button', { name: 'Clear search' })[0]);
		expect(screen.queryByText('1 programs found')).not.toBeInTheDocument();
	});
});
