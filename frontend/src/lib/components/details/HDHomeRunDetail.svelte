<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { api, type HDHomeRunTestConnectionResult, type HDHomeRunTranscodePreset } from '$lib/api';
	import HDHomeRunPlayer from '$lib/components/HDHomeRunPlayer.svelte';
	import { user } from '$lib/stores/user';

	interface HDHomeRunGuideEntry {
		title: string;
		episode_title: string | null;
		start: number | null;
		end: number | null;
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
		title: string;
		channel_name: string | null;
		start: number | null;
		record_end: number | null;
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
		upcoming_recording_rules_count: number;
		tuner_host: string;
		tuner_port: number;
		dvr_host: string;
		dvr_port: number;
		epg_url: string;
		playback_mode: string;
		hwaccel: string;
		custom_ffmpeg_args: string;
		ffmpeg_command: string;
		favorite_channels: string[];
	}

	let { data: initialData }: { data: HDHomeRunDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let hdhomerun = $state(initialData);

	let editing = $state(false);
	let tunerHostInput = $state('');
	let tunerPortInput = $state(80);
	let dvrHostInput = $state('');
	let dvrPortInput = $state(59090);
	let epgUrlInput = $state('');
	let playbackModeInput = $state('server_transcode');
	let hwaccelInput = $state('software');
	let customFfmpegArgsInput = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);

	let testingTuner = $state(false);
	let tunerTestResult = $state<HDHomeRunTestConnectionResult | null>(null);
	let testingDvr = $state(false);
	let dvrTestResult = $state<HDHomeRunTestConnectionResult | null>(null);

	let transcodePresets = $state<HDHomeRunTranscodePreset[]>([]);
	const selectedPreset = $derived(transcodePresets.find((p) => p.id === hwaccelInput) ?? null);

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
				? trimmed.split(/\s+/)
				: (transcodePresets.find((p) => p.id === 'software')?.output_args ?? []);
		}
		return [
			'ffmpeg',
			'-hide_banner',
			'-loglevel',
			'warning',
			'-nostats',
			...selectedPreset.input_args,
			'-i',
			'<channel stream>',
			...outputArgs,
			'-f',
			'mpegts',
			'pipe:1',
		].join(' ');
	});

	let playingChannel = $state<HDHomeRunChannel | null>(null);

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; toggleFavorite keeps it in sync afterward.
	let favoriteChannels = $state(new Set(initialData.favorite_channels));
	let savingFavorite = $state(false);

	const widgetId = $derived(page.params.id!);
	const favoriteList = $derived(hdhomerun.channels.filter((c) => favoriteChannels.has(c.channel_number)));

	function watchChannel(channel: HDHomeRunChannel) {
		if (channel.playback_url) {
			playingChannel = channel;
		} else {
			window.open(api.hdhomerunPlaylistUrl(widgetId, channel.channel_number), '_blank');
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
		tunerHostInput = hdhomerun.tuner_host;
		tunerPortInput = hdhomerun.tuner_port;
		dvrHostInput = hdhomerun.dvr_host;
		dvrPortInput = hdhomerun.dvr_port;
		epgUrlInput = hdhomerun.epg_url;
		playbackModeInput = hdhomerun.playback_mode;
		hwaccelInput = hdhomerun.hwaccel;
		customFfmpegArgsInput = hdhomerun.custom_ffmpeg_args;
		tunerTestResult = null;
		dvrTestResult = null;
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
			tuner_host: tunerHostInput,
			tuner_port: tunerPortInput,
			dvr_host: dvrHostInput,
			dvr_port: dvrPortInput,
			epg_url: epgUrlInput,
			playback_mode: playbackModeInput,
			hwaccel: hwaccelInput,
			custom_ffmpeg_args: customFfmpegArgsInput,
		};
	}

	async function testTunerConnection() {
		testingTuner = true;
		tunerTestResult = null;
		try {
			tunerTestResult = await api.hdhomerunTestTunerConnection(widgetId, currentFormSettings());
		} catch {
			tunerTestResult = { ok: false, name: null, error: 'Could not reach the backend.' };
		} finally {
			testingTuner = false;
		}
	}

	async function testDvrConnection() {
		testingDvr = true;
		dvrTestResult = null;
		try {
			dvrTestResult = await api.hdhomerunTestDvrConnection(widgetId, currentFormSettings());
		} catch {
			dvrTestResult = { ok: false, name: null, error: 'Could not reach the backend.' };
		} finally {
			testingDvr = false;
		}
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, currentFormSettings());
			hdhomerun = await api.widgetDetail<HDHomeRunDetailData>(widgetId);
			editing = false;
		} catch {
			error = 'Could not save the connection settings.';
		} finally {
			saving = false;
		}
	}

	function formatBytes(bytes: number | null): string {
		if (bytes === null) return 'unknown';
		const gb = bytes / 1_000_000_000;
		return `${gb.toFixed(1)} GB`;
	}

	function formatTime(seconds: number | null): string {
		if (seconds === null) return '';
		return new Date(seconds * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
	}
</script>

<div class="header">
	<h1>HDHomeRun</h1>
	{#if $user?.role === 'admin'}
		<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
			{editing ? 'Cancel' : 'Edit connection'}
		</button>
	{/if}
</div>

{#if editing}
	<div class="settings-form">
		<h2>Tuner</h2>
		<label>
			Host
			<input type="text" bind:value={tunerHostInput} placeholder="hdhomerun.local" />
		</label>
		<label>
			Port
			<input type="number" min="1" max="65535" bind:value={tunerPortInput} />
		</label>
		<div class="test-row">
			<button class="test" disabled={testingTuner} onclick={testTunerConnection}>
				{testingTuner ? 'Testing…' : 'Test connection'}
			</button>
			{#if tunerTestResult}
				{#if tunerTestResult.ok}
					<span class="test-result ok">✓ Connected to {tunerTestResult.name}</span>
				{:else}
					<span class="test-result fail">✗ {tunerTestResult.error}</span>
				{/if}
			{/if}
		</div>

		<h2>Playback</h2>
		<div class="auth-mode">
			<button
				type="button"
				class:active={playbackModeInput === 'server_transcode'}
				onclick={() => (playbackModeInput = 'server_transcode')}
			>
				Server transcode
			</button>
			<button
				type="button"
				class:active={playbackModeInput === 'external'}
				onclick={() => (playbackModeInput = 'external')}
			>
				External player only
			</button>
		</div>
		{#if playbackModeInput === 'server_transcode'}
			<p class="hint">
				The backend runs ffmpeg to transcode the raw stream to H.264 so it plays in-app. Works with any tuner model, but
				adds real CPU load per viewer on whatever device is running the backend.
			</p>

			<label>
				Transcode hardware
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
					Custom ffmpeg arguments
					<textarea bind:value={customFfmpegArgsInput} rows="2" placeholder="-c:v h264_v4l2m2m -b:v 4M -c:a aac"
					></textarea>
				</label>
			{/if}

			<p class="hint ffmpeg-command">
				<code>{livePreviewCommand}</code>
			</p>
		{:else}
			<p class="hint">
				No in-app player — channels only offer a raw stream link to open in an external player like VLC.
			</p>
		{/if}

		<h2>Program guide <span class="optional">(optional)</span></h2>
		<label>
			XMLTV URL
			<input type="text" bind:value={epgUrlInput} placeholder="http://example.com/guide.xml" />
		</label>
		<p class="hint">
			"Now playing" titles are tried first from a HDHomeRun DVR subscription. If you don't have one, set an XMLTV guide
			URL here instead (the format used by Plex, Channels DVR, TVheadend, etc.) — its channel ids must match your
			HDHomeRun channel numbers (e.g. "4.1").
		</p>

		<h2>DVR recording engine <span class="optional">(optional)</span></h2>
		<label>
			Host
			<input type="text" bind:value={dvrHostInput} placeholder="dvr.local" />
		</label>
		<label>
			Port
			<input type="number" min="1" max="65535" bind:value={dvrPortInput} />
		</label>
		<div class="test-row">
			<button class="test" disabled={testingDvr} onclick={testDvrConnection}>
				{testingDvr ? 'Testing…' : 'Test connection'}
			</button>
			{#if dvrTestResult}
				{#if dvrTestResult.ok}
					<span class="test-result ok">✓ Connected to {dvrTestResult.name}</span>
				{:else}
					<span class="test-result fail">✗ {dvrTestResult.error}</span>
				{/if}
			{/if}
		</div>

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={saveSettings}>
			{saving ? 'Saving…' : 'Save'}
		</button>
	</div>
{:else if error}
	<p class="hint error">{error}</p>
{/if}

{#if !editing}
	{#if !hdhomerun.tuner_connected && !hdhomerun.dvr_connected}
		<p class="hint">Not connected yet — tap "Edit connection" to set up HDHomeRun.</p>
	{:else}
		{#if hdhomerun.tuner_connected && hdhomerun.tuner_info}
			<p class="tuner-info">
				{hdhomerun.tuner_info.friendly_name}
				{#if hdhomerun.tuner_info.model_number}· {hdhomerun.tuner_info.model_number}{/if}
				{#if hdhomerun.tuner_info.tuner_count}· {hdhomerun.tuner_info.tuner_count} tuners{/if}
			</p>
		{/if}

		{#if hdhomerun.playback_mode === 'server_transcode'}
			<p class="hint ffmpeg-command">
				<code>{hdhomerun.ffmpeg_command}</code>
			</p>
		{/if}

		{#if hdhomerun.tuners.length > 0}
			<div class="tuners">
				{#each hdhomerun.tuners as tuner (tuner.index)}
					<div class="tuner">
						<span class="tuner-index">Tuner {tuner.index}</span>
						{#if tuner.in_use}
							<span class="tuner-channel">{tuner.channel_number} {tuner.channel_name}</span>
							{#if tuner.signal_strength_percent !== null}
								<span class="tuner-signal">Signal {tuner.signal_strength_percent}%</span>
							{/if}
						{:else}
							<span class="tuner-idle">Idle</span>
						{/if}
					</div>
				{/each}
			</div>
		{/if}

		{#if hdhomerun.tuner_connected}
			{#if !hdhomerun.guide_available}
				<p class="hint">
					Guide unavailable — showing channel lineup only. Program titles require an HDHomeRun DVR subscription.
				</p>
			{/if}

			{#if favoriteList.length > 0}
				<h2>Favorites — Now Playing</h2>
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
									Now: {channel.now.title}{#if channel.now.episode_title}
										— {channel.now.episode_title}{/if}
								</p>
							{:else}
								<p class="hint">No guide data</p>
							{/if}
							{#if channel.next}
								<p class="guide-next">Next: {channel.next.title}</p>
							{/if}
							<div class="channel-actions">
								<button class="watch" onclick={() => watchChannel(channel)}>▶ Watch</button>
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
								aria-label={favoriteChannels.has(channel.channel_number) ? 'Remove from favorites' : 'Add to favorites'}
							>
								{favoriteChannels.has(channel.channel_number) ? '★' : '☆'}
							</button>
							<span class="channel-number">{channel.channel_number}</span>
							<span class="channel-name">{channel.name}</span>
							{#if channel.is_hd}<span class="badge">HD</span>{/if}
						</div>
						{#if channel.now}
							<p class="guide-now">
								Now: {channel.now.title}{#if channel.now.episode_title}
									— {channel.now.episode_title}{/if}
							</p>
						{/if}
						{#if channel.next}
							<p class="guide-next">Next: {channel.next.title}</p>
						{/if}
						<div class="channel-actions">
							{#if channel.playback_url}
								<button class="watch" onclick={() => (playingChannel = channel)}> ▶ Watch </button>
							{/if}
							<a
								class="open-external"
								href={api.hdhomerunPlaylistUrl(widgetId, channel.channel_number)}
								target="_blank"
								rel="noopener noreferrer"
							>
								Open in external player
							</a>
						</div>
					</div>
				{/each}
			</div>
		{/if}

		{#if hdhomerun.dvr_connected}
			<h2>DVR</h2>
			{#if hdhomerun.dvr_info}
				<p class="hint">Free space: {formatBytes(hdhomerun.dvr_info.free_space_bytes)}</p>
			{/if}
			{#if hdhomerun.recordings_in_progress.length > 0}
				<div class="recordings">
					{#each hdhomerun.recordings_in_progress as recording, i (i)}
						<div class="recording">
							<span class="rec-badge">● Recording</span>
							<span class="rec-title">{recording.title}</span>
							{#if recording.channel_name}<span class="rec-channel">{recording.channel_name}</span>{/if}
							{#if recording.record_end}
								<span class="rec-end">until {formatTime(recording.record_end)}</span>
							{/if}
						</div>
					{/each}
				</div>
			{:else}
				<p class="hint">No recordings in progress.</p>
			{/if}
			<p class="hint">{hdhomerun.upcoming_recording_rules_count} upcoming recording rules.</p>
		{/if}
	{/if}
{/if}

{#if playingChannel}
	<HDHomeRunPlayer
		src={api.hdhomerunPlaybackUrl(playingChannel.playback_url!)}
		title={`${playingChannel.channel_number} ${playingChannel.name}`}
		onClose={() => (playingChannel = null)}
	/>
{/if}

<style>
	.header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
	}

	.header h1 {
		margin: 0;
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

	.optional {
		font-weight: normal;
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.settings-form label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.settings-form input[type='text'],
	.settings-form input[type='number'],
	.settings-form select,
	.settings-form textarea {
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

	.test-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.test {
		align-self: flex-start;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.test-result {
		font-size: 0.85rem;
	}

	.test-result.ok {
		color: var(--color-success);
	}

	.test-result.fail {
		color: var(--color-error);
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

	.tuners {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		margin: 0.5rem 0 1rem;
	}

	.tuner {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		font-size: 0.9rem;
	}

	.tuner-index {
		color: var(--color-text-muted);
	}

	.tuner-idle {
		color: var(--color-text-muted);
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
		gap: 0.75rem;
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

	.open-external {
		color: var(--color-accent);
		font-size: 0.85rem;
	}

	.recordings {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		margin: 0.5rem 0;
	}

	.recording {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.9rem;
	}

	.rec-badge {
		color: var(--color-error);
	}

	.rec-channel,
	.rec-end {
		color: var(--color-text-muted);
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
