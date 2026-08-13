<script lang="ts">
	import type Mpegts from 'mpegts.js';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';
	import { api } from '$lib/api';

	interface Props {
		src: string;
		title: string;
		widgetId?: string;
		playUrl?: string;
		recordingId?: string | null;
		startTimestamp?: number | null;
		recordEndTimestamp?: number | null;
		seekable?: boolean;
		onClose: () => void;
	}

	let { src, title, widgetId, playUrl, recordingId, startTimestamp, recordEndTimestamp, seekable, onClose }: Props =
		$props();

	interface ThumbnailCue {
		startSeconds: number;
		endSeconds: number;
		x: number;
		y: number;
		w: number;
		h: number;
	}

	const DETAIL_POLL_INTERVAL_MS = 10_000;

	let player: ReturnType<typeof Mpegts.createPlayer> | undefined;
	let videoElement = $state<HTMLVideoElement | null>(null);
	let videoCurrentTime = $state(0);
	let baseOffsetSeconds = $state(0);
	let duration = $state<number | null>(null);
	let isInProgress = $state(false);
	let videoInfo = $state<{
		codec: string | null;
		width: number | null;
		height: number | null;
		fps: number | null;
	} | null>(null);
	let audioTracks = $state<{ index: number; codec: string | null; channels: number | null; language: string | null }[]>(
		[],
	);
	let hasCaptions = $state(false);
	let currentAudioIndex = $state<number | null>(null);
	let captionsEnabled = $state(false);
	let thumbnailsAvailable = $state(false);
	let thumbnailCues: ThumbnailCue[] = [];
	let thumbSpriteUrl = $state('');

	interface CaptionCue {
		start: number;
		end: number;
		text: string;
	}
	// Captions are extracted once for the whole recording, so their cue
	// timestamps are absolute (0 = start of the recording). But each seek
	// tears down and recreates the mpegts player against a freshly
	// `-ss`-seeked ffmpeg stream, which resets the video element's own
	// currentTime back to 0 - so the native VTT cue times would only ever
	// line up with playback when baseOffsetSeconds is 0. A plain
	// `<track src>` can't be re-timed after the browser parses it, so
	// cues are parsed here and re-added to a managed TextTrack, shifted by
	// -baseOffsetSeconds, every time the playback origin changes.
	// Plain (not $state) - a live TextTrack is a mutable host object, and
	// wrapping it in Svelte's deep-reactivity proxy makes every cues
	// add/remove inside refreshCaptionCues() itself trip the reactivity
	// that's supposed to call refreshCaptionCues(), which loops forever.
	// It's refreshed imperatively at every call site that can affect it
	// instead (see ensureCaptionTrack/seekTo/toggleCaptions).
	let captionCues: CaptionCue[] = [];
	let capTextTrack: TextTrack | null = null;

	let showAudioMenu = $state(false);
	let showPlaybackInfo = $state(false);
	let hoverPreview = $state<{ x: number; cue: ThumbnailCue } | null>(null);

	let errorMessage = $state<string | null>(null);
	let errorDetail = $state<string | null>(null);
	let destroyed = false;
	let detailPollHandle: ReturnType<typeof setInterval> | undefined;
	let scrubBarEl: HTMLDivElement | null = $state(null);

	const displayedPosition = $derived(baseOffsetSeconds + videoCurrentTime);
	const progressPercent = $derived(duration ? Math.min(100, (displayedPosition / duration) * 100) : 0);
	const captionsUrl = $derived(
		widgetId && playUrl
			? api.hdhomerunRecordingCaptionsUrl(widgetId, {
					url: playUrl,
					recordingId: recordingId ?? '',
					recordEnd: recordEndTimestamp,
				})
			: '',
	);

	function genericHint() {
		return get(_)('hdhomerun.detail.playback_failed_hint', {
			values: { action: get(_)('hdhomerun.detail.open_external') },
		});
	}

	function formatTime(seconds: number): string {
		if (isNaN(seconds) || seconds < 0) return '0:00';
		const m = Math.floor(seconds / 60);
		const s = Math.floor(seconds % 60);
		const h = Math.floor(m / 60);
		const remM = m % 60;
		if (h > 0) {
			return `${h}:${remM.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
		}
		return `${m}:${s.toString().padStart(2, '0')}`;
	}

	function buildStreamUrl(startSeconds: number | undefined, audioIndex: number | null): string {
		if (!seekable || !widgetId || !playUrl) return src;
		return api.hdhomerunRecordingStreamUrl(widgetId, playUrl, {
			start: startSeconds,
			audioIndex: audioIndex ?? undefined,
		});
	}

	async function loadDetail(): Promise<void> {
		if (!seekable || !widgetId || !playUrl) return;
		try {
			const detail = await api.hdhomerunRecordingDetail(widgetId, {
				url: playUrl,
				recordingId: recordingId ?? '',
				start: startTimestamp,
				recordEnd: recordEndTimestamp,
			});
			duration = detail.duration_seconds;
			isInProgress = detail.is_in_progress;
			videoInfo = detail.video;
			audioTracks = detail.audio;
			hasCaptions = detail.has_captions;
		} catch {
			// Detail is an enhancement (duration/menus/captions) — playback
			// itself doesn't depend on it, so a failed fetch just means those
			// stay unavailable.
		}
	}

	function parseThumbnailVtt(text: string): ThumbnailCue[] {
		const cues: ThumbnailCue[] = [];
		const timeToSeconds = (ts: string): number => {
			const match = ts.match(/(\d+):(\d+):(\d+(?:\.\d+)?)/);
			if (!match) return 0;
			return Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3]);
		};
		const blocks = text.split(/\r?\n\r?\n/);
		for (const block of blocks) {
			const lines = block.split(/\r?\n/).filter((l) => l.trim());
			const cueLine = lines.find((l) => l.includes('-->'));
			const xywhLine = lines.find((l) => l.includes('#xywh='));
			if (!cueLine || !xywhLine) continue;
			const [startRaw, endRaw] = cueLine.split('-->').map((s) => s.trim());
			const xywhMatch = xywhLine.match(/#xywh=(\d+),(\d+),(\d+),(\d+)/);
			if (!xywhMatch) continue;
			cues.push({
				startSeconds: timeToSeconds(startRaw),
				endSeconds: timeToSeconds(endRaw),
				x: Number(xywhMatch[1]),
				y: Number(xywhMatch[2]),
				w: Number(xywhMatch[3]),
				h: Number(xywhMatch[4]),
			});
		}
		return cues;
	}

	async function loadThumbnails(): Promise<void> {
		if (!seekable || !widgetId || !playUrl || isInProgress) return;
		try {
			const vttUrl = api.hdhomerunRecordingThumbnailVttUrl(widgetId, {
				url: playUrl,
				recordingId: recordingId ?? '',
				recordEnd: recordEndTimestamp,
			});
			const response = await fetch(vttUrl, { credentials: 'include' });
			if (!response.ok) return;
			const text = await response.text();
			const cues = parseThumbnailVtt(text);
			if (cues.length === 0) return;
			thumbnailCues = cues;
			thumbSpriteUrl = api.hdhomerunRecordingThumbnailSpriteUrl(widgetId, {
				url: playUrl,
				recordingId: recordingId ?? '',
				recordEnd: recordEndTimestamp,
			});
			thumbnailsAvailable = true;
		} catch {
			// No thumbnails: hover preview stays off, scrub bar still works.
		}
	}

	function parseVttTimestamp(raw: string): number {
		const match = raw.trim().match(/(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)/);
		if (!match) return 0;
		const hours = match[1] ? Number(match[1]) : 0;
		const minutes = Number(match[2]);
		const seconds = Number(match[3]);
		return hours * 3600 + minutes * 60 + seconds;
	}

	function parseCaptionsVtt(text: string): CaptionCue[] {
		const cues: CaptionCue[] = [];
		const blocks = text.replace(/\r\n/g, '\n').split(/\n\n+/);
		for (const block of blocks) {
			const lines = block.split('\n').filter((l) => l.length > 0);
			const cueLineIndex = lines.findIndex((l) => l.includes('-->'));
			if (cueLineIndex === -1) continue;
			const [startRaw, endRaw] = lines[cueLineIndex].split('-->');
			const start = parseVttTimestamp(startRaw);
			const end = parseVttTimestamp(endRaw.trim().split(' ')[0]);
			const textLines = lines.slice(cueLineIndex + 1);
			if (textLines.length === 0) continue;
			// ffmpeg's CEA-608 decoder writes the literal two characters "\h"
			// for a caption-positioning space code (used for indentation)
			// instead of an actual space - a run of "\h\h\h\h" is just
			// indentation that never got converted to real whitespace, so
			// swap it for a real space so it reads as normal text instead of
			// showing the literal escape code.
			const cleanedText = textLines.join('\n').replace(/\\h/g, ' ');
			cues.push({ start, end, text: cleanedText });
		}
		return cues;
	}

	function ensureCaptionTrack() {
		if (capTextTrack || !videoElement) return;
		capTextTrack = videoElement.addTextTrack('subtitles', 'Captions', 'en');
		capTextTrack.mode = captionsEnabled ? 'showing' : 'hidden';
	}

	function refreshCaptionCues() {
		if (!capTextTrack) return;
		while (capTextTrack.cues && capTextTrack.cues.length > 0) {
			capTextTrack.removeCue(capTextTrack.cues[0]);
		}
		for (const cue of captionCues) {
			const start = cue.start - baseOffsetSeconds;
			const end = cue.end - baseOffsetSeconds;
			if (end <= 0) continue;
			try {
				capTextTrack.addCue(new VTTCue(Math.max(0, start), end, cue.text));
			} catch {
				// A malformed cue shouldn't take down the rest of the track.
			}
		}
	}

	async function loadCaptions(): Promise<void> {
		if (!seekable || !captionsUrl) return;
		try {
			const response = await fetch(captionsUrl, { credentials: 'include' });
			if (!response.ok) return;
			const text = await response.text();
			const cues = parseCaptionsVtt(text);
			if (cues.length === 0) return;
			captionCues = cues;
			ensureCaptionTrack();
			refreshCaptionCues();
		} catch {
			// No captions: the CC button stays visible per hasCaptions, but
			// toggling it just won't show anything.
		}
	}

	function findCueAt(seconds: number): ThumbnailCue | null {
		if (thumbnailCues.length === 0) return null;
		let found = thumbnailCues[0];
		for (const cue of thumbnailCues) {
			if (cue.startSeconds > seconds) break;
			found = cue;
		}
		return found;
	}

	function stopPolling() {
		if (detailPollHandle !== undefined) {
			clearInterval(detailPollHandle);
			detailPollHandle = undefined;
		}
	}

	function startPolling() {
		if (detailPollHandle !== undefined) return;
		detailPollHandle = setInterval(async () => {
			const wasInProgress = isInProgress;
			await loadDetail();
			if (wasInProgress && !isInProgress) {
				stopPolling();
				loadThumbnails();
			}
		}, DETAIL_POLL_INTERVAL_MS);
	}

	// mpegts.js reports a failed stream request as a bare "network error" and
	// throws the response body away, so the backend's carefully built 502
	// detail — which names the actual ffmpeg failure — never reaches the
	// user. Re-requesting the same URL is the only way to read it, and it's
	// cheap: the request has already failed, and the backend fails the same
	// way again in well under a second.
	async function fetchServerDetail(url: string) {
		try {
			const response = await fetch(url, { credentials: 'include' });
			if (response.ok) {
				response.body?.cancel();
				return null;
			}
			const body = await response.json();
			return typeof body?.detail === 'string' ? body.detail : null;
		} catch {
			return null;
		}
	}

	function teardownPlayer() {
		player?.pause();
		player?.unload();
		player?.detachMediaElement();
		player?.destroy();
		player = undefined;
	}

	function createPlayerAt(node: HTMLVideoElement, url: string) {
		errorMessage = null;
		errorDetail = null;
		// mpegts.js's UMD bundle references `window` at import time, so a
		// static import would crash SvelteKit's server-side render of this
		// page (Node has no `window`). Deferring to a dynamic import here
		// means it only ever loads client-side, once this action runs.
		import('mpegts.js').then(({ default: mpegts }) => {
			if (destroyed) return;
			player = mpegts.createPlayer(
				{ type: 'mse', isLive: true, url, withCredentials: true },
				// liveBufferLatencyChasing auto-seeks forward whenever the playhead
				// falls behind the live edge — which is exactly what a manual
				// buffer-rewind (see rewind()/fastForward() below) does, so leaving
				// it on snaps the video straight back to live the instant you
				// scrub backward. Off, so a manual seek stays where you put it.
				{ enableStashBuffer: false, liveBufferLatencyChasing: false },
			);
			player.on(mpegts.Events.ERROR, (errorType: string) => {
				errorMessage = genericHint();
				if (errorType !== mpegts.ErrorTypes.NETWORK_ERROR) return;
				fetchServerDetail(url).then((detail) => {
					if (!destroyed) errorDetail = detail;
				});
			});
			player.attachMediaElement(node);
			player.load();
			player.play();
		});
	}

	function seekTo(targetSeconds: number) {
		if (!seekable || !videoElement) return;
		let clamped = Math.max(0, targetSeconds);
		if (duration !== null) clamped = Math.min(clamped, duration);
		teardownPlayer();
		baseOffsetSeconds = clamped;
		videoCurrentTime = 0;
		refreshCaptionCues();
		createPlayerAt(videoElement, buildStreamUrl(clamped, currentAudioIndex));
	}

	function rewind(seconds = 10) {
		if (seekable) {
			seekTo(displayedPosition - seconds);
		} else if (videoElement) {
			videoElement.currentTime = Math.max(0, videoElement.currentTime - seconds);
		}
	}

	function fastForward(seconds = 10) {
		if (seekable) {
			seekTo(displayedPosition + seconds);
		} else if (videoElement) {
			videoElement.currentTime = videoElement.currentTime + seconds;
		}
	}

	function safePlay() {
		if (!videoElement) return;
		try {
			const res = videoElement.play();
			if (res && typeof res.catch === 'function') res.catch(() => {});
		} catch {
			// ignore play errors in non-media environments
		}
	}

	function togglePlay() {
		if (!videoElement) return;
		if (videoElement.paused) {
			safePlay();
		} else {
			videoElement.pause();
		}
	}

	function toggleCaptions() {
		captionsEnabled = !captionsEnabled;
		if (capTextTrack) capTextTrack.mode = captionsEnabled ? 'showing' : 'hidden';
	}

	function selectAudioTrack(index: number) {
		if (!seekable || index === currentAudioIndex) return;
		currentAudioIndex = index;
		showAudioMenu = false;
		seekTo(displayedPosition);
	}

	function handleScrubClick(e: MouseEvent) {
		if (!seekable || duration === null || !scrubBarEl) return;
		const rect = scrubBarEl.getBoundingClientRect();
		const fraction = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
		seekTo(fraction * duration);
	}

	function handleScrubHover(e: MouseEvent) {
		if (!seekable || duration === null || !scrubBarEl || !thumbnailsAvailable) return;
		const rect = scrubBarEl.getBoundingClientRect();
		const fraction = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
		const cue = findCueAt(fraction * duration);
		if (cue) hoverPreview = { x: e.clientX - rect.left, cue };
	}

	function handleScrubKeydown(e: KeyboardEvent) {
		if (!seekable || duration === null) return;
		if (e.key === 'ArrowLeft') {
			e.preventDefault();
			seekTo(Math.max(0, displayedPosition - 10));
		} else if (e.key === 'ArrowRight') {
			e.preventDefault();
			seekTo(Math.min(duration, displayedPosition + 10));
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			if (showPlaybackInfo) {
				showPlaybackInfo = false;
			} else if (showAudioMenu) {
				showAudioMenu = false;
			} else {
				onClose();
			}
		} else if (e.key === ' ') {
			e.preventDefault();
			togglePlay();
		} else if (e.key === 'ArrowLeft' || e.key === 'j') {
			rewind(10);
		} else if (e.key === 'ArrowRight' || e.key === 'l') {
			fastForward(10);
		} else if (e.key === 'c' && hasCaptions) {
			toggleCaptions();
		}
	}

	// See JellyfinPlayer.svelte for why this overlay is portaled to <body>.
	function portal(node: HTMLElement) {
		document.body.appendChild(node);
		return {
			destroy() {
				node.remove();
			},
		};
	}

	function attachPlayer(node: HTMLVideoElement) {
		videoElement = node;

		(async () => {
			if (seekable) {
				await loadDetail();
				if (destroyed) return;
				if (isInProgress) {
					baseOffsetSeconds = duration ?? 0;
					createPlayerAt(node, buildStreamUrl(undefined, currentAudioIndex));
					startPolling();
				} else {
					baseOffsetSeconds = 0;
					createPlayerAt(node, buildStreamUrl(0, currentAudioIndex));
					loadThumbnails();
					if (hasCaptions) loadCaptions();
				}
			} else {
				createPlayerAt(node, src);
			}
		})();

		return {
			destroy() {
				// Closes the underlying HTTP connection — this is what lets the
				// backend's stream route notice the disconnect and kill its
				// ffmpeg process. Skipping this leaks it indefinitely.
				destroyed = true;
				stopPolling();
				teardownPlayer();
				videoElement = null;
				capTextTrack = null;
				captionCues = [];
			},
		};
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="overlay" role="dialog" aria-label={title} use:portal>
	<div class="header">
		<h2>{title}</h2>
		<div class="controls">
			{#if seekable && (videoInfo || audioTracks.length > 0)}
				<button
					class="control-btn"
					class:active={showPlaybackInfo}
					onclick={() => (showPlaybackInfo = !showPlaybackInfo)}
					aria-label={$_('player.playback_info')}
					title={$_('player.playback_info')}
				>
					ℹ
				</button>
			{/if}
			{#if seekable && hasCaptions}
				<button
					class="control-btn"
					class:active={captionsEnabled}
					onclick={toggleCaptions}
					aria-label={$_('player.subtitles')}
					title={$_('player.subtitles')}
				>
					💬 CC
				</button>
			{/if}
			{#if seekable && audioTracks.length > 1}
				<div class="menu-popover-wrap">
					<button
						class="control-btn"
						class:active={showAudioMenu}
						onclick={() => (showAudioMenu = !showAudioMenu)}
						aria-label={$_('player.audio_tracks')}
					>
						🔊 {$_('player.audio_tracks')}
					</button>
					{#if showAudioMenu}
						<div class="popover-menu">
							<div class="menu-header">{$_('player.audio_tracks')}</div>
							<div class="menu-items">
								{#each audioTracks as track (track.index)}
									<button
										class="menu-item"
										class:selected={currentAudioIndex === track.index ||
											(currentAudioIndex === null && track.index === 0)}
										onclick={() => selectAudioTrack(track.index)}
									>
										{track.language ? track.language.toUpperCase() : `Track ${track.index + 1}`}
										{#if track.channels}({track.channels}ch){/if}
									</button>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/if}
			<button class="control-btn" onclick={() => rewind(10)} aria-label={$_('player.rewind')}>↺ 10s</button>
			<button class="control-btn" onclick={() => fastForward(10)} aria-label={$_('player.fast_forward')}>↻ 10s</button>
			<button class="close" onclick={onClose} aria-label={$_('player.close')}>✕</button>
		</div>
	</div>
	{#if errorMessage}
		<p class="error">
			{errorMessage}
			{#if errorDetail}
				<span class="error-detail">{errorDetail}</span>
			{/if}
		</p>
	{/if}

	<div class="video-container">
		<!-- svelte-ignore a11y_media_has_caption -->
		<video
			autoplay
			playsinline
			controls={!seekable}
			class="video"
			use:attachPlayer
			bind:currentTime={videoCurrentTime}
			crossorigin="use-credentials"
		></video>

		{#if seekable}
			<div class="scrub-container">
				<div class="scrub-time">{formatTime(displayedPosition)}</div>
				<div
					class="scrub-bar"
					class:disabled={duration === null}
					bind:this={scrubBarEl}
					onclick={handleScrubClick}
					onmousemove={handleScrubHover}
					onmouseleave={() => (hoverPreview = null)}
					onkeydown={handleScrubKeydown}
					role="slider"
					aria-label={$_('player.playback_info')}
					aria-valuemin="0"
					aria-valuemax={duration ?? 0}
					aria-valuenow={displayedPosition}
					tabindex="0"
				>
					<div class="scrub-track">
						<div class="scrub-fill" style:width="{progressPercent}%"></div>
					</div>
					{#if hoverPreview}
						<div
							class="thumb-preview"
							style:left="{hoverPreview.x}px"
							style:width="{hoverPreview.cue.w}px"
							style:height="{hoverPreview.cue.h}px"
							style:background-image="url({thumbSpriteUrl})"
							style:background-position="-{hoverPreview.cue.x}px -{hoverPreview.cue.y}px"
						>
							<span class="thumb-time">{formatTime(hoverPreview.cue.startSeconds)}</span>
						</div>
					{/if}
				</div>
				<div class="scrub-time">
					{isInProgress ? $_('hdhomerun.detail.recording_in_progress') : formatTime(duration ?? 0)}
				</div>
			</div>
		{/if}
	</div>

	{#if showPlaybackInfo && seekable}
		<div class="info-overlay-modal" role="dialog" aria-label={$_('player.playback_info')}>
			<div class="info-card">
				<div class="info-header">
					<h3>{$_('player.playback_info')}</h3>
					<button class="info-close" onclick={() => (showPlaybackInfo = false)}>✕</button>
				</div>
				<div class="info-body">
					<div class="info-row">
						<span class="label">{$_('player.container')}:</span>
						<span class="value uppercase">MPEG-TS</span>
					</div>
					{#if videoInfo}
						<div class="info-section-heading">{$_('player.video')}</div>
						<div class="info-row">
							<span class="label">Codec:</span>
							<span class="value uppercase">{videoInfo.codec ?? $_('common.unknown')}</span>
						</div>
						{#if videoInfo.width && videoInfo.height}
							<div class="info-row">
								<span class="label">{$_('player.resolution')}:</span>
								<span class="value">{videoInfo.width}×{videoInfo.height}</span>
							</div>
						{/if}
						{#if videoInfo.fps}
							<div class="info-row">
								<span class="label">Framerate:</span>
								<span class="value">{videoInfo.fps} fps</span>
							</div>
						{/if}
					{/if}
					{#if audioTracks.length > 0}
						<div class="info-section-heading">{$_('player.audio')}</div>
						{#each audioTracks as track (track.index)}
							<div class="info-row">
								<span class="label">Track {track.index + 1}:</span>
								<span class="value uppercase">{track.codec ?? $_('common.unknown')} · {track.channels ?? '?'}ch</span>
							</div>
						{/each}
					{/if}
					<div class="info-row">
						<span class="label">{$_('player.duration')}:</span>
						<span class="value">{duration !== null ? formatTime(duration) : $_('common.unknown')}</span>
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 100;
		background: #000;
		display: flex;
		flex-direction: column;
	}

	.header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.75rem 1rem;
		background: rgba(0, 0, 0, 0.6);
	}

	.header h2 {
		margin: 0;
		color: #fff;
		font-size: 1rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.controls {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.control-btn {
		background: rgba(255, 255, 255, 0.15);
		border: 1px solid rgba(255, 255, 255, 0.3);
		border-radius: 0.4rem;
		padding: 0.3rem 0.6rem;
		color: #fff;
		font-size: 0.85rem;
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.control-btn:hover {
		background: rgba(255, 255, 255, 0.25);
	}

	.control-btn.active {
		background: rgba(56, 189, 248, 0.25);
		border-color: #38bdf8;
		color: #38bdf8;
	}

	.close {
		flex-shrink: 0;
		background: none;
		border: 1px solid rgba(255, 255, 255, 0.4);
		border-radius: 50%;
		width: 2rem;
		height: 2rem;
		color: #fff;
		cursor: pointer;
	}

	.error {
		margin: 0;
		padding: 0.75rem 1rem;
		color: #ffb4b4;
		background: rgba(224, 90, 90, 0.15);
	}

	.error-detail {
		display: block;
		margin-top: 0.35rem;
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.75rem;
		max-height: 6rem;
		overflow: auto;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		opacity: 0.85;
	}

	.video-container {
		position: relative;
		flex: 1;
		display: flex;
		flex-direction: column;
		min-height: 0;
		background: #000;
	}

	.video {
		flex: 1;
		width: 100%;
		min-height: 0;
		object-fit: contain;
		background: #000;
	}

	.scrub-container {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.5rem 1rem;
		background: rgba(0, 0, 0, 0.85);
		border-top: 1px solid rgba(255, 255, 255, 0.1);
	}

	.scrub-time {
		color: rgba(255, 255, 255, 0.75);
		font-size: 0.8rem;
		font-family: ui-monospace, SFMono-Regular, monospace;
		white-space: nowrap;
	}

	.scrub-bar {
		position: relative;
		flex: 1;
		cursor: pointer;
		padding: 0.5rem 0;
	}

	.scrub-bar.disabled {
		cursor: default;
		opacity: 0.5;
		pointer-events: none;
	}

	.scrub-track {
		position: relative;
		height: 0.35rem;
		border-radius: 0.2rem;
		background: rgba(255, 255, 255, 0.2);
		overflow: hidden;
	}

	.scrub-fill {
		height: 100%;
		background: #38bdf8;
	}

	.thumb-preview {
		position: absolute;
		bottom: 100%;
		margin-bottom: 0.5rem;
		transform: translateX(-50%);
		border: 2px solid rgba(255, 255, 255, 0.9);
		border-radius: 0.3rem;
		background-repeat: no-repeat;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: flex-end;
		justify-content: center;
	}

	.thumb-time {
		background: rgba(0, 0, 0, 0.75);
		color: #fff;
		font-size: 0.65rem;
		padding: 0.05rem 0.25rem;
		border-radius: 0.2rem;
		margin: 0.2rem;
	}

	.menu-popover-wrap {
		position: relative;
	}

	.popover-menu {
		position: absolute;
		top: 100%;
		right: 0;
		margin-top: 0.5rem;
		width: 12rem;
		max-height: 16rem;
		background: rgba(20, 20, 20, 0.95);
		border: 1px solid rgba(255, 255, 255, 0.2);
		border-radius: 0.6rem;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(12px);
		z-index: 120;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.menu-header {
		padding: 0.5rem 0.75rem;
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: rgba(255, 255, 255, 0.5);
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
	}

	.menu-items {
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		padding: 0.25rem 0;
	}

	.menu-item {
		background: none;
		border: none;
		color: rgba(255, 255, 255, 0.85);
		padding: 0.5rem 0.75rem;
		text-align: left;
		font-size: 0.85rem;
		cursor: pointer;
	}

	.menu-item:hover {
		background: rgba(255, 255, 255, 0.15);
		color: #fff;
	}

	.menu-item.selected {
		color: #38bdf8;
		font-weight: 600;
		background: rgba(56, 189, 248, 0.15);
	}

	.info-overlay-modal {
		position: absolute;
		inset: 0;
		z-index: 150;
		background: rgba(0, 0, 0, 0.65);
		backdrop-filter: blur(6px);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
	}

	.info-card {
		background: rgba(30, 30, 35, 0.95);
		border: 1px solid rgba(255, 255, 255, 0.2);
		border-radius: 0.75rem;
		width: 100%;
		max-width: 24rem;
		padding: 1.25rem;
		color: #fff;
		box-shadow: 0 12px 32px rgba(0, 0, 0, 0.7);
	}

	.info-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 1rem;
	}

	.info-header h3 {
		margin: 0;
		font-size: 1.1rem;
	}

	.info-close {
		background: none;
		border: none;
		color: rgba(255, 255, 255, 0.6);
		font-size: 1.1rem;
		cursor: pointer;
	}

	.info-body {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		font-size: 0.9rem;
	}

	.info-section-heading {
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		color: #38bdf8;
		margin-top: 0.6rem;
		margin-bottom: 0.2rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
		padding-bottom: 0.2rem;
	}

	.info-row {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
	}

	.info-row .label {
		color: rgba(255, 255, 255, 0.6);
	}

	.info-row .value {
		font-weight: 500;
		text-align: right;
	}

	.uppercase {
		text-transform: uppercase;
	}
</style>
