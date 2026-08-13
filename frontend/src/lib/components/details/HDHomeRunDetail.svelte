<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import {
		api,
		type HDHomeRunTranscodePreset,
		type HWAccelDiagnostics,
		type HDHomeRunRecordingRule,
		type HDHomeRunFullGuideChannel,
	} from '$lib/api';
	import HDHomeRunPlayer from '$lib/components/HDHomeRunPlayer.svelte';
	import { user } from '$lib/stores/user';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	interface HDHomeRunGuideEntry {
		series_id?: string | null;
		title: string;
		episode_title: string | null;
		episode_number?: string | null;
		synopsis?: string | null;
		start: number | null;
		end: number | null;
		original_airdate?: number | string | null;
		image_url?: string | null;
		channel_number?: string;
	}

	interface HDHomeRunChannel {
		channel_number: string;
		name: string;
		is_hd: boolean;
		is_drm: boolean;
		stream_url: string;
		playback_url: string | null;
		now: HDHomeRunGuideEntry | null;
		next: HDHomeRunGuideEntry | null;
	}

	interface HDHomeRunTuner {
		index: number;
		in_use: boolean;
		channel_number: string | null;
		channel_name: string | null;
		signal_strength_percent: number | null;
		signal_quality_percent: number | null;
		symbol_quality_percent: number | null;
		network_rate_bps: number | null;
	}

	interface HDHomeRunRecording {
		recording_id?: string | null;
		series_id?: string | null;
		title: string;
		episode_title?: string | null;
		episode_number?: string | null;
		synopsis?: string | null;
		channel_number?: string | null;
		channel_name: string | null;
		start: number | null;
		record_end: number | null;
		play_url?: string | null;
		image_url?: string | null;
		duration_seconds?: number | null;
		is_dvr_file?: boolean;
	}

	interface HDHomeRunTunerInfo {
		friendly_name: string;
		model_number: string | null;
		firmware_version: string | null;
		tuner_count: number | null;
	}

	interface HDHomeRunDvrInfo {
		friendly_name: string;
		version: string | null;
		free_space_bytes: number | null;
	}

	interface HDHomeRunDetailData {
		tuner_connected: boolean;
		dvr_connected: boolean;
		guide_available: boolean;
		tuner_info: HDHomeRunTunerInfo | null;
		channels: HDHomeRunChannel[];
		tuners: HDHomeRunTuner[];
		dvr_info: HDHomeRunDvrInfo | null;
		recordings_in_progress: HDHomeRunRecording[];
		all_recordings?: HDHomeRunRecording[];
		recording_rules?: HDHomeRunRecordingRule[];
		upcoming_recording_rules_count: number;
		playback_mode: string;
		hwaccel: string;
		custom_ffmpeg_args: string;
		hwaccel_device: string;
		ffmpeg_debug: boolean;
		ffmpeg_command: string;
		favorite_channels: string[];
		thumbnails_enabled: boolean;
	}

	let { data: initialData }: { data: HDHomeRunDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let hdhomerun = $state(initialData);

	let editing = $state(false);
	let playbackModeInput = $state('server_transcode');
	let hwaccelInput = $state('software');
	let customFfmpegArgsInput = $state('');
	let hwaccelDeviceInput = $state('/dev/dri/renderD128');
	let ffmpegDebugInput = $state(false);
	let thumbnailsEnabledInput = $state(true);
	let saving = $state(false);
	let error = $state<string | null>(null);

	let transcodePresets = $state<HDHomeRunTranscodePreset[]>([]);
	const selectedPreset = $derived(transcodePresets.find((p) => p.id === hwaccelInput) ?? null);

	// Word-splits the way Python's shlex.split does — which is what the
	// backend uses on custom_ffmpeg_args (transcoding._output_args). A plain
	// split(/\s+/) disagrees with it on any quoted argument (a filter graph
	// with spaces, a path with a space), so the preview would show a command
	// the backend never runs.
	function shlexSplit(input: string): string[] {
		const tokens: string[] = [];
		// A quoted run, an escaped char, or a run of unquoted non-space.
		const pattern = /"((?:\\.|[^"\\])*)"|'([^']*)'|((?:\\.|[^\s'"\\])+)/g;
		let token = '';
		let end = 0;
		for (const match of input.matchAll(pattern)) {
			// A gap since the previous match means whitespace, i.e. a token
			// boundary; adjacent matches ("-vf"x'y') are one token.
			if (match.index > end && token) {
				tokens.push(token);
				token = '';
			}
			const [, doubleQuoted, singleQuoted, bare] = match;
			if (singleQuoted !== undefined) token += singleQuoted;
			else token += (doubleQuoted ?? bare).replace(/\\(.)/g, '$1');
			end = match.index + match[0].length;
		}
		if (token) tokens.push(token);
		return tokens;
	}

	// Mirrors transcoding.build_ffmpeg_args()'s argument order, so the
	// command shown while editing matches what saving would actually run —
	// computed client-side (rather than round-tripped per keystroke) since
	// it's pure string assembly over data already fetched with the presets.
	const livePreviewCommand = $derived.by(() => {
		if (!selectedPreset) return '';
		let outputArgs = selectedPreset.output_args;
		if (hwaccelInput === 'custom') {
			const trimmed = customFfmpegArgsInput.trim();
			outputArgs = trimmed
				? shlexSplit(trimmed)
				: (transcodePresets.find((p) => p.id === 'software')?.output_args ?? []);
		}
		const device = hwaccelDeviceInput.trim() || '/dev/dri/renderD128';
		const substitute = (args: string[]) => args.map((arg) => arg.replaceAll('{device}', device));
		return [
			'ffmpeg',
			'-hide_banner',
			'-loglevel',
			ffmpegDebugInput ? 'verbose' : 'warning',
			'-nostats',
			...substitute(selectedPreset.input_args),
			'-i',
			'<channel stream>',
			...substitute(outputArgs),
			'-f',
			'mpegts',
			'pipe:1',
		].join(' ');
	});

	let diagnostics = $state<HWAccelDiagnostics | null>(null);
	let diagnosticsRunning = $state(false);
	let diagnosticsError = $state<string | null>(null);

	async function runDiagnostics() {
		diagnosticsRunning = true;
		diagnosticsError = null;
		try {
			diagnostics = await api.hdhomerunHwaccelDiagnostics(widgetId, hwaccelDeviceInput.trim() || undefined);
		} catch {
			diagnostics = null;
			diagnosticsError = get(_)('hdhomerun.detail.diagnostics_failed');
		} finally {
			diagnosticsRunning = false;
		}
	}

	let playingMedia = $state<{
		title: string;
		url: string;
		playUrl: string;
		recordingId: string | null;
		startTimestamp: number | null;
		recordEndTimestamp: number | null;
		seekable: boolean;
	} | null>(null);

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; toggleFavorite keeps it in sync afterward.
	let favoriteChannels = $state(new Set(initialData.favorite_channels));
	let savingFavorite = $state(false);
	let recordingLoading = $state<string | null>(null);
	let fullGuide = $state<HDHomeRunFullGuideChannel[] | null>(null);
	let loadingGuide = $state(false);

	const widgetId = $derived(page.params.id!);
	const favoriteList = $derived(hdhomerun.channels.filter((c) => favoriteChannels.has(c.channel_number)));

	function watchChannel(channel: HDHomeRunChannel) {
		if (channel.playback_url) {
			playingMedia = {
				title: `${channel.channel_number} ${channel.name}`,
				url: api.hdhomerunPlaybackUrl(channel.playback_url),
				playUrl: channel.playback_url,
				recordingId: null,
				startTimestamp: null,
				recordEndTimestamp: null,
				seekable: false,
			};
		} else {
			window.open(api.hdhomerunPlaylistUrl(widgetId, channel.channel_number), '_blank');
		}
	}

	// Tab persistence via URL search param ?tab=lineup | guide | dvr
	let activeTab = $state<'lineup' | 'guide' | 'recordings'>('lineup');

	$effect(() => {
		const paramTab = page.url.searchParams.get('tab');
		if (paramTab) {
			const target = paramTab === 'dvr' ? 'recordings' : (paramTab as 'lineup' | 'guide' | 'recordings');
			if (activeTab !== target && (target === 'lineup' || target === 'guide' || target === 'recordings')) {
				activeTab = target;
				if (target === 'guide' && !fullGuide) {
					loadGuide();
				}
			}
		}
	});

	function selectTab(tab: 'lineup' | 'guide' | 'recordings') {
		activeTab = tab;
		const url = new URL(page.url);
		url.searchParams.set('tab', tab === 'recordings' ? 'dvr' : tab);
		goto(url, { replaceState: true, noScroll: true, keepFocus: true });
		if (tab === 'guide') {
			loadGuide();
		}
	}

	function playRecording(recording: HDHomeRunRecording) {
		let playUrl = recording.play_url;
		if (!playUrl && recording.recording_id) {
			playUrl = `/recorded/${recording.recording_id}`;
		}
		if (!playUrl && recording.channel_number) {
			playUrl = `/auto/v${recording.channel_number}`;
		}
		if (!playUrl) return;

		// Only a real DVR file entry is seekable (a resolvable file behind the
		// backend's -ss input-seeking) — a currently-airing/no-file-yet
		// placeholder's play_url points at the bare live tuner stream, which
		// has no file to seek within. And seeking only works when the backend
		// is actually transcoding: the raw-proxy fallback (playback_mode !=
		// "server_transcode") streams the source file byte-for-byte from the
		// start and has no way to honor a `start` offset.
		const seekable = recording.is_dvr_file === true && hdhomerun.playback_mode === 'server_transcode';
		const streamUrl = api.hdhomerunRecordingStreamUrl(widgetId, playUrl);

		playingMedia = {
			title: recording.episode_title ? `${recording.title} - ${recording.episode_title}` : recording.title,
			url: streamUrl,
			playUrl,
			recordingId: recording.recording_id ?? null,
			startTimestamp: recording.start,
			recordEndTimestamp: recording.record_end,
			seekable,
		};
	}

	async function recordShowEpisode(seriesId?: string | null, channelNumber?: string, startTime?: number | null) {
		const targetId = seriesId || channelNumber || 'now';
		recordingLoading = targetId;
		try {
			const updatedRules = await api.addHDHomeRunRecordingRule(widgetId, {
				series_id: seriesId || 'auto',
				channel: channelNumber,
				date_time: startTime ?? undefined,
			});
			if (Array.isArray(updatedRules)) {
				hdhomerun.recording_rules = updatedRules;
			}
			hdhomerun = await api.widgetDetail<HDHomeRunDetailData>(widgetId);
		} catch {
			error = get(_)('common.connection_save_error');
		} finally {
			recordingLoading = null;
		}
	}

	async function recordShowSeries(seriesId: string, channelNumber?: string) {
		recordingLoading = seriesId;
		try {
			const updatedRules = await api.addHDHomeRunRecordingRule(widgetId, {
				series_id: seriesId,
				channel: channelNumber,
			});
			if (Array.isArray(updatedRules)) {
				hdhomerun.recording_rules = updatedRules;
			}
			hdhomerun = await api.widgetDetail<HDHomeRunDetailData>(widgetId);
		} catch {
			error = get(_)('common.connection_save_error');
		} finally {
			recordingLoading = null;
		}
	}

	async function cancelRecordingRule(ruleId: string) {
		recordingLoading = ruleId;
		try {
			const updatedRules = await api.deleteHDHomeRunRecordingRule(widgetId, ruleId);
			if (Array.isArray(updatedRules)) {
				hdhomerun.recording_rules = updatedRules;
			}
			hdhomerun = await api.widgetDetail<HDHomeRunDetailData>(widgetId);
		} catch {
			error = get(_)('common.connection_save_error');
		} finally {
			recordingLoading = null;
		}
	}

	async function loadGuide() {
		activeTab = 'guide';
		if (fullGuide) return;
		loadingGuide = true;
		try {
			fullGuide = await api.getHDHomeRunGuide(widgetId);
		} catch {
			fullGuide = [];
		} finally {
			loadingGuide = false;
		}
	}

	// A tile's "now playing" entry links here with ?watch=<channel_number> to
	// jump straight into playback. The param is stripped immediately after
	// use so it doesn't re-trigger on unrelated state changes (e.g. saving
	// settings re-renders this effect's dependencies).
	$effect(() => {
		const watchTarget = page.url.searchParams.get('watch');
		if (!watchTarget) return;
		const channel = hdhomerun.channels.find((c) => c.channel_number === watchTarget);
		if (channel) watchChannel(channel);
		const url = new URL(page.url);
		url.searchParams.delete('watch');
		goto(url, { replaceState: true, noScroll: true, keepFocus: true });
	});

	async function toggleFavorite(channelNumber: string) {
		const next = new Set(favoriteChannels);
		if (next.has(channelNumber)) {
			next.delete(channelNumber);
		} else {
			next.add(channelNumber);
		}
		favoriteChannels = next;
		savingFavorite = true;
		try {
			await api.updateWidgetSettings(widgetId, { favorite_channels: [...next] });
		} finally {
			savingFavorite = false;
		}
	}

	async function openEditor() {
		playbackModeInput = hdhomerun.playback_mode;
		hwaccelInput = hdhomerun.hwaccel;
		customFfmpegArgsInput = hdhomerun.custom_ffmpeg_args;
		hwaccelDeviceInput = hdhomerun.hwaccel_device;
		ffmpegDebugInput = hdhomerun.ffmpeg_debug;
		thumbnailsEnabledInput = hdhomerun.thumbnails_enabled;
		editing = true;
		if (transcodePresets.length === 0) {
			try {
				transcodePresets = await api.hdhomerunTranscodePresets();
			} catch {
				transcodePresets = [];
			}
		}
	}

	function currentFormSettings(): Record<string, unknown> {
		return {
			playback_mode: playbackModeInput,
			hwaccel: hwaccelInput,
			custom_ffmpeg_args: customFfmpegArgsInput,
			hwaccel_device: hwaccelDeviceInput.trim(),
			ffmpeg_debug: ffmpegDebugInput,
			thumbnails_enabled: thumbnailsEnabledInput,
		};
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, currentFormSettings());
			hdhomerun = await api.widgetDetail<HDHomeRunDetailData>(widgetId);
			editing = false;
		} catch {
			error = get(_)('common.connection_save_error');
		} finally {
			saving = false;
		}
	}

	function formatBytes(bytes: number | null): string {
		if (bytes === null) return get(_)('common.unknown');
		const gb = bytes / 1_000_000_000;
		return `${gb.toFixed(1)} GB`;
	}

	function formatTime(seconds: number | null): string {
		if (seconds === null) return '';
		return new Date(seconds * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
	}

	function formatDate(seconds: number | null): string {
		if (seconds === null) return '';
		return new Date(seconds * 1000).toLocaleString([], {
			month: 'short',
			day: 'numeric',
			hour: 'numeric',
			minute: '2-digit',
		});
	}
</script>

<div class="header">
	<h1>HDHomeRun</h1>
	<div class="header-actions">
		<div class="view-tabs">
			<button class:active={activeTab === 'lineup'} onclick={() => selectTab('lineup')}>
				{$_('hdhomerun.detail.channels_tab')}
			</button>
			<button class:active={activeTab === 'guide'} onclick={() => selectTab('guide')}>
				{$_('hdhomerun.detail.guide_tab')}
			</button>
			<button class:active={activeTab === 'recordings'} onclick={() => selectTab('recordings')}>
				{$_('hdhomerun.detail.dvr_section_heading')}
			</button>
		</div>
		{#if $user?.role === 'admin'}
			<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
				{editing ? $_('common.cancel') : $_('hdhomerun.detail.edit_playback_settings')}
			</button>
		{/if}
	</div>
</div>

{#if editing}
	<div class="settings-form">
		<h2>{$_('hdhomerun.detail.playback_heading')}</h2>
		<div class="auth-mode">
			<button
				type="button"
				class:active={playbackModeInput === 'server_transcode'}
				onclick={() => (playbackModeInput = 'server_transcode')}
			>
				{$_('hdhomerun.detail.mode_server_transcode')}
			</button>
			<button
				type="button"
				class:active={playbackModeInput === 'external'}
				onclick={() => (playbackModeInput = 'external')}
			>
				{$_('hdhomerun.detail.mode_external')}
			</button>
		</div>
		{#if playbackModeInput === 'server_transcode'}
			<p class="hint">
				{$_('hdhomerun.detail.server_transcode_hint')}
			</p>

			<label>
				{$_('hdhomerun.detail.transcode_hardware_label')}
				<select bind:value={hwaccelInput}>
					{#each transcodePresets as preset (preset.id)}
						<option value={preset.id}>{preset.label}</option>
					{/each}
				</select>
			</label>
			{#if selectedPreset}
				<p class="hint">{selectedPreset.description}</p>
			{/if}

			{#if hwaccelInput === 'custom'}
				<label>
					{$_('hdhomerun.detail.custom_ffmpeg_label')}
					<textarea bind:value={customFfmpegArgsInput} rows="2" placeholder="-c:v h264_v4l2m2m -b:v 4M -c:a aac"
					></textarea>
				</label>
			{/if}

			<label>
				{$_('hdhomerun.detail.hwaccel_device_label')}
				<input bind:value={hwaccelDeviceInput} placeholder="/dev/dri/renderD128" />
			</label>
			<p class="hint">{$_('hdhomerun.detail.hwaccel_device_hint')}</p>

			<label class="checkbox">
				<input type="checkbox" bind:checked={ffmpegDebugInput} />
				{$_('hdhomerun.detail.ffmpeg_debug_label')}
			</label>
			<p class="hint">{$_('hdhomerun.detail.ffmpeg_debug_hint')}</p>

			<label class="checkbox">
				<input type="checkbox" bind:checked={thumbnailsEnabledInput} />
				{$_('hdhomerun.detail.thumbnails_enabled_label')}
			</label>
			<p class="hint">{$_('hdhomerun.detail.thumbnails_enabled_hint')}</p>

			<p class="hint ffmpeg-command">
				<code>{livePreviewCommand}</code>
			</p>

			<div class="diagnostics">
				<h3>{$_('hdhomerun.detail.diagnostics_heading')}</h3>
				<p class="hint">{$_('hdhomerun.detail.diagnostics_hint')}</p>
				<button type="button" class="diagnostics-run" disabled={diagnosticsRunning} onclick={runDiagnostics}>
					{diagnosticsRunning ? $_('hdhomerun.detail.diagnostics_running') : $_('hdhomerun.detail.diagnostics_run')}
				</button>

				{#if diagnosticsError}
					<p class="hint error">{diagnosticsError}</p>
				{/if}

				{#if diagnostics}
					{#each diagnostics.summary as finding, index (index)}
						<p class="finding">{finding}</p>
					{/each}

					<h4>{$_('hdhomerun.detail.diagnostics_devices_heading')}</h4>
					{#if !diagnostics.dri.dir_exists}
						<p class="hint">{$_('hdhomerun.detail.diagnostics_no_dri')}</p>
					{:else if diagnostics.dri.devices.length === 0}
						<p class="hint">{$_('hdhomerun.detail.diagnostics_no_devices')}</p>
					{:else}
						<ul class="diagnostics-list">
							{#each diagnostics.dri.devices as device (device.path)}
								<li>
									<span class="status" class:ok={device.readable && device.writable}>
										{device.readable && device.writable ? '✓' : '✗'}
									</span>
									<code>{device.path}</code>
									<span class="muted">
										{device.error ?? `${device.mode} ${device.owner_uid}:${device.owner_gid}`}
									</span>
								</li>
							{/each}
						</ul>
					{/if}
					<p class="hint">
						{$_('hdhomerun.detail.diagnostics_process', {
							values: {
								uid: diagnostics.process.uid,
								gid: diagnostics.process.gid,
								groups: diagnostics.process.groups.join(', ') || '—',
							},
						})}
					</p>

					{#if diagnostics.vainfo}
						<h4>{$_('hdhomerun.detail.diagnostics_driver_heading')}</h4>
						<p class="hint">
							{diagnostics.vainfo.driver ?? $_('common.unknown')} ·
							{$_('hdhomerun.detail.diagnostics_h264_encode')}: {diagnostics.vainfo.can_encode_h264 ? '✓' : '✗'} ·
							{$_('hdhomerun.detail.diagnostics_mpeg2_decode')}: {diagnostics.vainfo.can_decode_mpeg2 ? '✓' : '✗'}
						</p>
						{#if !diagnostics.vainfo.ok}
							<pre class="diagnostics-output">{diagnostics.vainfo.output}</pre>
						{/if}
					{/if}

					<h4>{$_('hdhomerun.detail.diagnostics_presets_heading')}</h4>
					{#if diagnostics.sample_error}
						<p class="hint error">{diagnostics.sample_error}</p>
					{/if}
					<ul class="diagnostics-list">
						{#each Object.entries(diagnostics.probes) as [presetId, probe] (presetId)}
							<li>
								<span class="status" class:ok={probe.ok}>{probe.ok ? '✓' : '✗'}</span>
								<code>{presetId}</code>
								{#if !probe.ok}
									<pre class="diagnostics-output">{probe.output || $_('hdhomerun.detail.diagnostics_no_output')}</pre>
								{/if}
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		{:else}
			<p class="hint">
				{$_('hdhomerun.detail.external_only_hint')}
			</p>
		{/if}

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={saveSettings}>
			{saving ? $_('common.saving') : $_('common.save')}
		</button>
	</div>
{:else if error}
	<p class="hint error">{error}</p>
{/if}

{#if !editing}
	{#if !hdhomerun.tuner_connected && !hdhomerun.dvr_connected}
		<p class="hint">{$_('hdhomerun.detail.not_connected_hint')}</p>
	{:else}
		{#if hdhomerun.tuner_connected && hdhomerun.tuner_info}
			<p class="tuner-info">
				{hdhomerun.tuner_info.friendly_name}
				{#if hdhomerun.tuner_info.model_number}· {hdhomerun.tuner_info.model_number}{/if}
				{#if hdhomerun.tuner_info.tuner_count}
					· {$_('hdhomerun.detail.tuner_count', { values: { count: hdhomerun.tuner_info.tuner_count } })}
				{/if}
			</p>
		{/if}

		{#if activeTab === 'lineup'}
			{#if hdhomerun.tuner_connected}
				{#if !hdhomerun.guide_available}
					<p class="hint">
						{$_('hdhomerun.detail.guide_unavailable_hint')}
					</p>
				{/if}

				{#if favoriteList.length > 0}
					<h2>{$_('hdhomerun.detail.favorites_heading')}</h2>
					<div class="channels favorites">
						{#each favoriteList as channel (channel.channel_number)}
							<div class="channel">
								<div class="channel-header">
									<span class="channel-number">{channel.channel_number}</span>
									<span class="channel-name">{channel.name}</span>
									{#if channel.is_hd}<span class="badge">HD</span>{/if}
								</div>
								{#if channel.now}
									<p class="guide-now">
										{#if channel.now.episode_title}
											{$_('hdhomerun.detail.guide_now_episode', {
												values: { title: channel.now.title, episode: channel.now.episode_title },
											})}
										{:else}
											{$_('hdhomerun.detail.guide_now', { values: { title: channel.now.title } })}
										{/if}
									</p>
								{:else}
									<p class="hint">{$_('hdhomerun.detail.no_guide_data')}</p>
								{/if}
								{#if channel.next}
									<p class="guide-next">
										{$_('hdhomerun.detail.guide_next', { values: { title: channel.next.title } })}
									</p>
								{/if}
								<div class="channel-actions">
									<button class="watch" onclick={() => watchChannel(channel)}
										>{$_('hdhomerun.detail.watch_button')}</button
									>
									{#if channel.now}
										<button
											class="record-btn"
											disabled={recordingLoading === (channel.now.series_id || channel.channel_number)}
											onclick={() =>
												recordShowEpisode(channel.now?.series_id, channel.channel_number, channel.now?.start)}
										>
											🔴 {$_('hdhomerun.detail.record_episode')}
										</button>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				{/if}

				<div class="channels">
					{#each hdhomerun.channels as channel (channel.channel_number)}
						<div class="channel">
							<div class="channel-header">
								<button
									class="favorite-toggle"
									class:active={favoriteChannels.has(channel.channel_number)}
									disabled={savingFavorite}
									onclick={() => toggleFavorite(channel.channel_number)}
									aria-label={favoriteChannels.has(channel.channel_number)
										? $_('hdhomerun.detail.remove_favorite')
										: $_('hdhomerun.detail.add_favorite')}
								>
									{favoriteChannels.has(channel.channel_number) ? '★' : '☆'}
								</button>
								<span class="channel-number">{channel.channel_number}</span>
								<span class="channel-name">{channel.name}</span>
								{#if channel.is_hd}<span class="badge">HD</span>{/if}
							</div>
							{#if channel.now}
								<p class="guide-now">
									{#if channel.now.episode_title}
										{$_('hdhomerun.detail.guide_now_episode', {
											values: { title: channel.now.title, episode: channel.now.episode_title },
										})}
									{:else}
										{$_('hdhomerun.detail.guide_now', { values: { title: channel.now.title } })}
									{/if}
								</p>
							{/if}
							{#if channel.next}
								<p class="guide-next">{$_('hdhomerun.detail.guide_next', { values: { title: channel.next.title } })}</p>
							{/if}
							<div class="channel-actions">
								{#if channel.playback_url}
									<button class="watch" onclick={() => watchChannel(channel)}>
										{$_('hdhomerun.detail.watch_button')}
									</button>
								{/if}
								{#if channel.now}
									<button
										class="record-btn"
										disabled={recordingLoading === (channel.now.series_id || channel.channel_number)}
										onclick={() =>
											recordShowEpisode(channel.now?.series_id, channel.channel_number, channel.now?.start)}
									>
										🔴 {$_('hdhomerun.detail.record_episode')}
									</button>
								{/if}
								<a
									class="open-external"
									href={api.hdhomerunPlaylistUrl(widgetId, channel.channel_number)}
									target="_blank"
									rel="noopener noreferrer"
								>
									{$_('hdhomerun.detail.open_external')}
								</a>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		{:else if activeTab === 'guide'}
			<h2>{$_('hdhomerun.detail.guide_tab')}</h2>
			{#if loadingGuide}
				<p class="hint">{$_('common.loading')}</p>
			{:else if fullGuide && fullGuide.length > 0}
				<div class="guide-channels">
					{#each fullGuide as channel (channel.channel_number)}
						<div class="guide-channel-row">
							<div class="guide-channel-header">
								<span class="channel-number">{channel.channel_number}</span>
								<span class="channel-name">{channel.channel_name}</span>
							</div>
							<div class="guide-airings">
								{#each channel.airings as airing, i (i)}
									<div class="airing-card">
										<div class="airing-time">{formatDate(airing.start)}</div>
										<div class="airing-title">{airing.title}</div>
										{#if airing.episode_title}<div class="airing-episode">{airing.episode_title}</div>{/if}
										{#if airing.synopsis}<div class="airing-synopsis">{airing.synopsis}</div>{/if}
										{#if airing.series_id}
											<div class="airing-actions">
												<button
													class="record-btn small"
													disabled={recordingLoading === airing.series_id}
													onclick={() => recordShowEpisode(airing.series_id!, channel.channel_number, airing.start)}
												>
													🔴 {$_('hdhomerun.detail.record_episode')}
												</button>
												<button
													class="record-btn small secondary"
													disabled={recordingLoading === airing.series_id}
													onclick={() => recordShowSeries(airing.series_id!, channel.channel_number)}
												>
													{$_('hdhomerun.detail.record_series')}
												</button>
											</div>
										{/if}
									</div>
								{/each}
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<p class="hint">{$_('hdhomerun.detail.no_guide_data')}</p>
			{/if}
		{:else if activeTab === 'recordings'}
			<h2>{$_('hdhomerun.detail.dvr_section_heading')}</h2>
			{#if hdhomerun.dvr_info}
				<p class="hint">
					{$_('hdhomerun.detail.free_space', { values: { value: formatBytes(hdhomerun.dvr_info.free_space_bytes) } })}
				</p>
			{/if}

			<h3>{$_('hdhomerun.detail.recordings_in_progress')}</h3>
			{#if hdhomerun.recordings_in_progress.length > 0}
				<div class="recordings">
					{#each hdhomerun.recordings_in_progress as recording, i (i)}
						<div
							class="recording clickable"
							role="button"
							tabindex="0"
							onclick={() => playRecording(recording)}
							onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && playRecording(recording)}
						>
							{#if recording.image_url}
								<img class="rec-thumb" src={recording.image_url} alt="" />
							{/if}
							<div class="rec-info">
								<span class="rec-badge">{$_('hdhomerun.tile.recording_badge')}</span>
								<span class="rec-title">{recording.title}</span>
								{#if recording.episode_title}<span class="rec-sub">{recording.episode_title}</span>{/if}
								{#if recording.synopsis}<p class="rec-synopsis">{recording.synopsis}</p>{/if}
								<div class="rec-meta">
									{#if recording.channel_name}<span class="rec-channel">{recording.channel_name}</span>{/if}
									{#if recording.record_end}
										<span class="rec-end"
											>{$_('hdhomerun.detail.recording_until', {
												values: { time: formatTime(recording.record_end) },
											})}</span
										>
									{/if}
								</div>
							</div>
							<div class="rec-actions">
								{#if recording.play_url}
									<button
										class="watch small"
										onclick={(e) => {
											e.stopPropagation();
											playRecording(recording);
										}}
									>
										▶ {$_('hdhomerun.detail.watch_button')}
									</button>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<p class="hint">{$_('hdhomerun.detail.no_recordings')}</p>
			{/if}

			{#if hdhomerun.all_recordings && hdhomerun.all_recordings.length > 0}
				<h3>{$_('hdhomerun.detail.recorded_programs')}</h3>
				<div class="recordings">
					{#each hdhomerun.all_recordings as recording, i (i)}
						<div
							class="recording clickable"
							role="button"
							tabindex="0"
							onclick={() => playRecording(recording)}
							onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && playRecording(recording)}
						>
							{#if recording.image_url}
								<img class="rec-thumb" src={recording.image_url} alt="" />
							{/if}
							<div class="rec-info">
								<span class="rec-title">{recording.title}</span>
								{#if recording.episode_title}<span class="rec-sub">{recording.episode_title}</span>{/if}
								{#if recording.synopsis}<p class="rec-synopsis">{recording.synopsis}</p>{/if}
								<div class="rec-meta">
									{#if recording.channel_name}<span class="rec-channel">{recording.channel_name}</span>{/if}
									{#if recording.start}<span class="rec-end">{formatDate(recording.start)}</span>{/if}
								</div>
							</div>
							<div class="rec-actions">
								<button
									class="watch small"
									onclick={(e) => {
										e.stopPropagation();
										playRecording(recording);
									}}
								>
									▶ {$_('hdhomerun.detail.watch_button')}
								</button>
								{#if recording.play_url}
									<a
										class="open-external small"
										href={recording.play_url}
										target="_blank"
										rel="noopener noreferrer"
										onclick={(e) => e.stopPropagation()}
									>
										{$_('hdhomerun.detail.open_external')}
									</a>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{/if}

			<h3>{$_('hdhomerun.detail.scheduled_recordings')}</h3>
			{#if hdhomerun.recording_rules && hdhomerun.recording_rules.length > 0}
				<div class="recording-rules">
					{#each hdhomerun.recording_rules as rule (rule.RecordingRuleID)}
						<div class="rule-card">
							<div class="rule-title">{rule.Title}</div>
							<div class="rule-details">
								<span class="rule-badge">
									{rule.DateTimeOnly ? $_('hdhomerun.detail.single_airing_rule') : $_('hdhomerun.detail.series_rule')}
								</span>
								{#if rule.ChannelOnly}<span class="rule-channel">Ch: {rule.ChannelOnly}</span>{/if}
								{#if rule.DateTimeOnly}<span class="rule-time">{formatDate(rule.DateTimeOnly)}</span>{/if}
							</div>
							<button
								class="cancel-rule-btn"
								disabled={recordingLoading === rule.RecordingRuleID}
								onclick={() => cancelRecordingRule(rule.RecordingRuleID)}
							>
								{$_('hdhomerun.detail.cancel_recording')}
							</button>
						</div>
					{/each}
				</div>
			{:else}
				<p class="hint">{$_('hdhomerun.detail.no_scheduled_recordings')}</p>
			{/if}
		{/if}
	{/if}
{/if}

{#if playingMedia}
	<HDHomeRunPlayer
		src={playingMedia.url}
		title={playingMedia.title}
		widgetId={playingMedia.seekable ? widgetId : undefined}
		playUrl={playingMedia.seekable ? playingMedia.playUrl : undefined}
		recordingId={playingMedia.seekable ? playingMedia.recordingId : undefined}
		startTimestamp={playingMedia.seekable ? playingMedia.startTimestamp : undefined}
		recordEndTimestamp={playingMedia.seekable ? playingMedia.recordEndTimestamp : undefined}
		seekable={playingMedia.seekable}
		onClose={() => (playingMedia = null)}
	/>
{/if}

<style>
	.header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.header h1 {
		margin: 0;
	}

	.header-actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.view-tabs {
		display: flex;
		gap: 0.25rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.2rem;
	}

	.view-tabs button {
		background: none;
		border: none;
		padding: 0.35rem 0.75rem;
		font-size: 0.85rem;
		color: var(--color-text-muted);
		border-radius: 0.35rem;
		cursor: pointer;
	}

	.view-tabs button.active {
		background: var(--color-accent);
		color: var(--color-surface);
	}

	.edit-settings {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.settings-form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		max-width: 30rem;
		margin: 1rem 0 1.5rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem;
	}

	.settings-form h2 {
		margin: 0.5rem 0 0;
		font-size: 1rem;
	}

	.settings-form h2:first-child {
		margin-top: 0;
	}

	.settings-form label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.settings-form select,
	.settings-form textarea,
	.settings-form label > input:not([type]) {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.settings-form textarea {
		font-family: var(--font-mono, monospace);
		font-size: 0.85rem;
		resize: vertical;
	}

	.settings-form label.checkbox {
		flex-direction: row;
		align-items: center;
		gap: 0.5rem;
	}

	.diagnostics {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		border-top: 1px solid var(--color-border);
		padding-top: 0.75rem;
	}

	.diagnostics h3 {
		margin: 0;
		font-size: 0.95rem;
	}

	.diagnostics h4 {
		margin: 0.5rem 0 0;
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.diagnostics-run {
		align-self: flex-start;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.85rem;
		font-size: 0.85rem;
		color: var(--color-text);
		cursor: pointer;
	}

	.diagnostics-run:disabled {
		cursor: default;
		opacity: 0.6;
	}

	.finding {
		margin: 0;
		font-size: 0.85rem;
	}

	.diagnostics-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-size: 0.85rem;
	}

	.diagnostics-list .status {
		color: var(--color-danger, #e05a5a);
		margin-right: 0.4rem;
	}

	.diagnostics-list .status.ok {
		color: var(--color-success, #4caf50);
	}

	.diagnostics-list .muted {
		color: var(--color-text-muted);
		margin-left: 0.4rem;
	}

	.diagnostics-output {
		margin: 0.25rem 0 0;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		font-family: var(--font-mono, monospace);
		font-size: 0.75rem;
		/* ffmpeg's verbose output runs to dozens of lines; cap it so a single
		   failing preset can't push the rest of the report off the page. */
		max-height: 12rem;
		overflow: auto;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}

	.ffmpeg-command {
		margin: 0;
	}

	.ffmpeg-command code {
		display: block;
		overflow-x: auto;
		white-space: pre;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		font-size: 0.8rem;
	}

	.auth-mode {
		display: flex;
		gap: 0.5rem;
	}

	.auth-mode button {
		flex: 1;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem;
		font-size: 0.85rem;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.auth-mode button.active {
		border-color: var(--color-accent);
		color: var(--color-accent);
	}

	.save {
		align-self: flex-start;
		background: var(--color-accent);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.tuner-info {
		color: var(--color-text-muted);
		margin: 1rem 0 0.5rem;
	}

	.channels {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
		gap: 1rem;
		margin: 0.5rem 0;
	}

	.channel {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.channel-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.favorite-toggle {
		background: none;
		border: none;
		padding: 0;
		font-size: 1.1rem;
		line-height: 1;
		color: var(--color-accent);
		cursor: pointer;
	}

	.favorite-toggle:disabled {
		opacity: 0.6;
		cursor: default;
	}

	.favorite-toggle:not(.active) {
		color: var(--color-text-muted);
	}

	.channel-number {
		color: var(--color-text-muted);
	}

	.channel-name {
		font-weight: 600;
	}

	.badge {
		font-size: 0.7rem;
		border: 1px solid var(--color-accent);
		color: var(--color-accent);
		border-radius: 0.3rem;
		padding: 0.05rem 0.3rem;
	}

	.guide-now,
	.guide-next {
		margin: 0;
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.channel-actions {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 0.35rem;
	}

	.watch {
		background: var(--color-accent);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.35rem 0.75rem;
		font-size: 0.85rem;
		cursor: pointer;
	}

	.watch.small {
		padding: 0.2rem 0.5rem;
		font-size: 0.75rem;
	}

	.record-btn {
		background: var(--color-error, #e05a5a);
		color: #fff;
		border: none;
		border-radius: 0.5rem;
		padding: 0.35rem 0.65rem;
		font-size: 0.8rem;
		cursor: pointer;
	}

	.record-btn.small {
		padding: 0.2rem 0.5rem;
		font-size: 0.75rem;
	}

	.record-btn.secondary {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		color: var(--color-text);
	}

	.record-btn:disabled {
		opacity: 0.6;
		cursor: default;
	}

	.open-external {
		color: var(--color-accent);
		font-size: 0.85rem;
	}

	.recordings {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin: 0.5rem 0 1.5rem;
	}

	.recording {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		font-size: 0.9rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.6rem 0.85rem;
	}

	.recording.clickable {
		cursor: pointer;
		transition:
			background 0.15s ease,
			border-color 0.15s ease,
			transform 0.15s ease;
	}

	.recording.clickable:hover {
		background: var(--color-surface-hover, rgba(255, 255, 255, 0.08));
		border-color: var(--color-accent, #3b82f6);
		transform: translateY(-1px);
	}

	.rec-thumb {
		width: 3.5rem;
		height: 2.2rem;
		object-fit: cover;
		border-radius: 0.25rem;
	}

	.rec-info {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		flex: 1;
	}

	.rec-sub {
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}

	.rec-synopsis {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		margin: 0.15rem 0 0;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.rec-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.8rem;
	}

	.rec-actions {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	.open-external.small {
		font-size: 0.75rem;
		padding: 0.25rem 0.5rem;
	}

	.rec-badge {
		color: var(--color-error);
		font-weight: 600;
	}

	.rec-title {
		font-weight: 600;
	}

	.rec-channel,
	.rec-end {
		color: var(--color-text-muted);
	}

	.recording-rules {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin: 0.5rem 0 1.5rem;
	}

	.rule-card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.6rem 0.85rem;
	}

	.rule-title {
		font-weight: 600;
	}

	.rule-details {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.rule-badge {
		border: 1px solid var(--color-border);
		border-radius: 0.3rem;
		padding: 0.1rem 0.35rem;
		font-size: 0.75rem;
	}

	.cancel-rule-btn {
		background: none;
		border: 1px solid var(--color-border);
		color: var(--color-error, #e05a5a);
		border-radius: 0.4rem;
		padding: 0.25rem 0.6rem;
		font-size: 0.8rem;
		cursor: pointer;
	}

	.guide-channels {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		margin-top: 1rem;
	}

	.guide-channel-row {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.85rem;
	}

	.guide-channel-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
		font-weight: 600;
	}

	.guide-airings {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
		gap: 0.6rem;
	}

	.airing-card {
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		font-size: 0.85rem;
	}

	.airing-time {
		color: var(--color-accent);
		font-size: 0.75rem;
	}

	.airing-title {
		font-weight: 600;
	}

	.airing-episode,
	.airing-synopsis {
		color: var(--color-text-muted);
		font-size: 0.8rem;
	}

	.airing-actions {
		display: flex;
		gap: 0.35rem;
		margin-top: 0.35rem;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
