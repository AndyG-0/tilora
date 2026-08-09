<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { api, type HDHomeRunTranscodePreset } from '$lib/api';
	import HDHomeRunPlayer from '$lib/components/HDHomeRunPlayer.svelte';
	import { user } from '$lib/stores/user';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

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
	let playbackModeInput = $state('server_transcode');
	let hwaccelInput = $state('software');
	let customFfmpegArgsInput = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);

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
		playbackModeInput = hdhomerun.playback_mode;
		hwaccelInput = hdhomerun.hwaccel;
		customFfmpegArgsInput = hdhomerun.custom_ffmpeg_args;
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
</script>

<div class="header">
	<h1>HDHomeRun</h1>
	{#if $user?.role === 'admin'}
		<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
			{editing ? $_('common.cancel') : $_('hdhomerun.detail.edit_playback_settings')}
		</button>
	{/if}
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

			<p class="hint ffmpeg-command">
				<code>{livePreviewCommand}</code>
			</p>
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

		{#if hdhomerun.playback_mode === 'server_transcode'}
			<p class="hint ffmpeg-command">
				<code>{hdhomerun.ffmpeg_command}</code>
			</p>
		{/if}

		{#if hdhomerun.tuners.length > 0}
			<div class="tuners">
				{#each hdhomerun.tuners as tuner (tuner.index)}
					<div class="tuner">
						<span class="tuner-index">{$_('hdhomerun.detail.tuner_label', { values: { index: tuner.index } })}</span>
						{#if tuner.in_use}
							<span class="tuner-channel">{tuner.channel_number} {tuner.channel_name}</span>
							{#if tuner.signal_strength_percent !== null}
								<span class="tuner-signal"
									>{$_('hdhomerun.detail.tuner_signal', { values: { percent: tuner.signal_strength_percent } })}</span
								>
							{/if}
						{:else}
							<span class="tuner-idle">{$_('hdhomerun.detail.tuner_idle')}</span>
						{/if}
					</div>
				{/each}
			</div>
		{/if}

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
								<p class="guide-next">{$_('hdhomerun.detail.guide_next', { values: { title: channel.next.title } })}</p>
							{/if}
							<div class="channel-actions">
								<button class="watch" onclick={() => watchChannel(channel)}
									>{$_('hdhomerun.detail.watch_button')}</button
								>
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
								<button class="watch" onclick={() => (playingChannel = channel)}>
									{$_('hdhomerun.detail.watch_button')}
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

		{#if hdhomerun.dvr_connected}
			<h2>{$_('hdhomerun.detail.dvr_section_heading')}</h2>
			{#if hdhomerun.dvr_info}
				<p class="hint">
					{$_('hdhomerun.detail.free_space', { values: { value: formatBytes(hdhomerun.dvr_info.free_space_bytes) } })}
				</p>
			{/if}
			{#if hdhomerun.recordings_in_progress.length > 0}
				<div class="recordings">
					{#each hdhomerun.recordings_in_progress as recording, i (i)}
						<div class="recording">
							<span class="rec-badge">{$_('hdhomerun.tile.recording_badge')}</span>
							<span class="rec-title">{recording.title}</span>
							{#if recording.channel_name}<span class="rec-channel">{recording.channel_name}</span>{/if}
							{#if recording.record_end}
								<span class="rec-end"
									>{$_('hdhomerun.detail.recording_until', {
										values: { time: formatTime(recording.record_end) },
									})}</span
								>
							{/if}
						</div>
					{/each}
				</div>
			{:else}
				<p class="hint">{$_('hdhomerun.detail.no_recordings')}</p>
			{/if}
			<p class="hint">
				{$_('hdhomerun.detail.upcoming_rules', { values: { count: hdhomerun.upcoming_recording_rules_count } })}
			</p>
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

	.settings-form label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

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
