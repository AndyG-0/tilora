<script lang="ts">
	import type Hls from 'hls.js';
	import { onMount } from 'svelte';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';
	import { api, type JellyfinMediaDetail } from '$lib/api';
	import { markDirectPlayFailed, shouldForceTranscode } from '$lib/jellyfinPlaybackCache';

	interface Props {
		widgetId: string;
		itemId: string;
		title: string;
		onClose: () => void;
	}

	let { widgetId, itemId, title, onClose }: Props = $props();

	// Only containers a browser's native <video> element can demux without
	// help. Everything else (MKV, AVI, TS, ...) always falls back to HLS.
	const DIRECT_PLAY_CONTAINERS = new Set(['mp4', 'm4v', 'mov']);
	const VIDEO_CODEC_MAP: Record<string, string> = { h264: 'avc1.640028', hevc: 'hvc1.1.6.L93.B0' };
	const AUDIO_CODEC_MAP: Record<string, string> = { aac: 'mp4a.40.2' };

	let videoElement = $state<HTMLVideoElement | null>(null);
	let mediaDetail = $state<JellyfinMediaDetail | null>(null);

	let selectedAudioIndex = $state<number | null>(null);
	let selectedSubtitleIndex = $state<number | null>(null);

	let currentTime = $state(0);
	let duration = $state(0);

	let showAudioMenu = $state(false);
	let showSubtitlesMenu = $state(false);
	let showChaptersMenu = $state(false);
	let showPlaybackInfo = $state(false);

	let pendingSeekTime = $state<number | null>(null);

	let playbackMethod = $state<'direct' | 'hls' | null>(null);
	let usedCachedFallback = $state(false);
	let errorMessage = $state<string | null>(null);
	// Starting a fresh HLS transcode can take a few seconds before Jellyfin
	// has a first segment ready — without this, the player just sits on a
	// black frame with no indication anything is happening.
	let isBuffering = $state(true);

	let hlsPlayer: Hls | undefined;
	let playSessionId: string | null = null;
	let destroyed = false;
	let progressIntervalId: ReturnType<typeof setInterval> | undefined;

	function portal(node: HTMLElement) {
		document.body.appendChild(node);
		return {
			destroy() {
				node.remove();
			},
		};
	}

	async function loadMediaDetail() {
		if (!widgetId || !itemId || !api?.jellyfinItemDetail) return;
		try {
			const detail = await api.jellyfinItemDetail(widgetId, itemId);
			if (!detail) return;
			mediaDetail = detail;

			const defaultAudio = detail.audio_streams?.find((s) => s.is_default) || detail.audio_streams?.[0];
			if (defaultAudio) {
				selectedAudioIndex = defaultAudio.index;
			}

			const defaultSub = detail.subtitle_streams?.find((s) => s.is_default);
			if (defaultSub) {
				selectedSubtitleIndex = defaultSub.index;
			}
		} catch {
			mediaDetail = null;
		}
	}

	function isDirectPlayEligible(node: HTMLVideoElement, detail: JellyfinMediaDetail): boolean {
		const container = detail.container?.toLowerCase();
		if (!container || !DIRECT_PLAY_CONTAINERS.has(container)) return false;

		const videoCodec = detail.video_stream?.codec?.toLowerCase();
		const mappedVideo = videoCodec ? VIDEO_CODEC_MAP[videoCodec] : undefined;
		if (!mappedVideo) return false;

		const audioCodec =
			detail.audio_streams?.find((s) => s.index === selectedAudioIndex)?.codec?.toLowerCase() ??
			detail.audio_streams?.[0]?.codec?.toLowerCase();
		const mappedAudio = audioCodec ? AUDIO_CODEC_MAP[audioCodec] : undefined;

		const codecs = mappedAudio ? `${mappedVideo}, ${mappedAudio}` : mappedVideo;
		const support = node.canPlayType(`video/mp4; codecs="${codecs}"`);
		return support === 'probably' || support === 'maybe';
	}

	function teardownHls() {
		hlsPlayer?.destroy();
		hlsPlayer = undefined;
		stopProgressReporting();
	}

	// Heartbeat so Jellyfin's own "continue watching" resume position stays
	// current while transcoding, rather than only updating once the session
	// ends (which is what made it feel stuck/stale before this).
	function startProgressReporting() {
		stopProgressReporting();
		progressIntervalId = setInterval(() => {
			if (!playSessionId || !videoElement) return;
			api
				.jellyfinReportPlaybackProgress(widgetId, itemId, playSessionId, videoElement.currentTime, videoElement.paused)
				.catch(() => {});
		}, 10000);
	}

	function stopProgressReporting() {
		if (progressIntervalId !== undefined) {
			clearInterval(progressIntervalId);
			progressIntervalId = undefined;
		}
	}

	// `crypto.randomUUID()` is spec'd as secure-context-only, so it's missing
	// on iPhones hitting the dev server over `http://<lan-ip>` — that made
	// this throw before any HLS request went out. `getRandomValues` has no
	// such restriction, so build the UUID from that instead.
	function generateSessionId(): string {
		const bytes = new Uint8Array(16);
		crypto.getRandomValues(bytes);
		bytes[6] = (bytes[6] & 0x0f) | 0x40;
		bytes[8] = (bytes[8] & 0x3f) | 0x80;
		const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0'));
		return `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10, 16).join('')}`;
	}

	function attachDirectPlay(node: HTMLVideoElement) {
		teardownHls();
		errorMessage = null;
		isBuffering = true;
		playbackMethod = 'direct';
		node.src = api.jellyfinStreamUrl(widgetId, itemId);
	}

	async function attachHlsPlayer(node: HTMLVideoElement) {
		teardownHls();
		errorMessage = null;
		isBuffering = true;
		playbackMethod = 'hls';
		playSessionId = generateSessionId();
		const url = api.jellyfinHlsMasterUrl(widgetId, itemId, {
			playSessionId,
			...(selectedAudioIndex !== null && { audioStreamIndex: selectedAudioIndex }),
		});

		api.jellyfinReportPlaybackStart(widgetId, itemId, playSessionId).catch(() => {});
		startProgressReporting();

		if (node.canPlayType('application/vnd.apple.mpegurl')) {
			// Native HLS (Safari/iOS) — no extra JS needed, same lesson as
			// HDHomeRun leaning on the browser's own decoder.
			node.src = url;
			return;
		}

		const { default: HlsCtor } = await import('hls.js');
		if (destroyed) return;
		if (!HlsCtor.isSupported()) {
			errorMessage = get(_)('player.playback_failed');
			return;
		}
		hlsPlayer = new HlsCtor();
		hlsPlayer.on(HlsCtor.Events.ERROR, (_event, data) => {
			if (!data.fatal) return;
			errorMessage = get(_)('player.playback_failed');
		});
		hlsPlayer.loadSource(url);
		hlsPlayer.attachMedia(node);
	}

	function handleVideoError() {
		if (playbackMethod === 'direct' && videoElement) {
			markDirectPlayFailed();
			usedCachedFallback = true;
			pendingSeekTime = currentTime;
			attachHlsPlayer(videoElement).catch(() => {
				errorMessage = get(_)('player.playback_failed');
			});
			return;
		}
		errorMessage = get(_)('player.playback_failed');
	}

	function attachPlayer(node: HTMLVideoElement) {
		videoElement = node;

		(async () => {
			try {
				await loadMediaDetail();
				if (destroyed) return;

				if (shouldForceTranscode()) {
					usedCachedFallback = true;
					await attachHlsPlayer(node);
					return;
				}

				if (mediaDetail && isDirectPlayEligible(node, mediaDetail)) {
					attachDirectPlay(node);
				} else {
					await attachHlsPlayer(node);
				}
			} catch {
				if (!destroyed) errorMessage = get(_)('player.playback_failed');
			}
		})();

		return {
			destroy() {
				destroyed = true;
				const stoppedPlaySessionId = playSessionId;
				const stoppedPosition = currentTime;
				teardownHls();
				if (playbackMethod === 'hls' && stoppedPlaySessionId) {
					api.jellyfinStopPlayback(widgetId, itemId, stoppedPlaySessionId, stoppedPosition).catch(() => {});
				}
				videoElement = null;
			},
		};
	}

	function selectAudioTrack(index: number) {
		if (!widgetId || !itemId || index === selectedAudioIndex || !videoElement) return;
		pendingSeekTime = currentTime;
		selectedAudioIndex = index;
		// Direct Play can't remux to a different embedded audio track — any
		// track switch always routes through the HLS transcode, which honors
		// AudioStreamIndex.
		attachHlsPlayer(videoElement).catch(() => {
			errorMessage = get(_)('player.playback_failed');
		});
		showAudioMenu = false;
	}

	function selectSubtitleTrack(index: number | null) {
		selectedSubtitleIndex = index;
		showSubtitlesMenu = false;
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

	const currentChapterIndex = $derived.by(() => {
		if (!mediaDetail?.chapters || mediaDetail.chapters.length === 0) return -1;
		let found = -1;
		for (let i = 0; i < mediaDetail.chapters.length; i++) {
			if (currentTime >= mediaDetail.chapters[i].start_seconds - 0.5) {
				found = i;
			} else {
				break;
			}
		}
		return found;
	});

	const currentChapter = $derived(
		currentChapterIndex >= 0 && mediaDetail?.chapters ? mediaDetail.chapters[currentChapterIndex] : null,
	);

	const activeAudioTrack = $derived(mediaDetail?.audio_streams?.find((s) => s.index === selectedAudioIndex) || null);

	const activeSubtitleTrack = $derived(
		mediaDetail?.subtitle_streams?.find((s) => s.index === selectedSubtitleIndex) || null,
	);

	function jumpToTime(seconds: number) {
		if (videoElement) {
			videoElement.currentTime = Math.max(0, Math.min(seconds, duration || seconds));
		}
	}

	function skipPrevChapter() {
		if (!mediaDetail?.chapters || mediaDetail.chapters.length === 0) {
			jumpToTime(currentTime - 10);
			return;
		}

		const idx = currentChapterIndex;
		if (idx === -1) {
			jumpToTime(0);
			return;
		}

		const chStart = mediaDetail.chapters[idx].start_seconds;
		if (currentTime > chStart + 3) {
			jumpToTime(chStart);
		} else if (idx > 0) {
			jumpToTime(mediaDetail.chapters[idx - 1].start_seconds);
		} else {
			jumpToTime(0);
		}
	}

	function skipNextChapter() {
		if (!mediaDetail?.chapters || mediaDetail.chapters.length === 0) {
			jumpToTime(currentTime + 10);
			return;
		}

		const idx = currentChapterIndex;
		if (idx >= 0 && idx < mediaDetail.chapters.length - 1) {
			jumpToTime(mediaDetail.chapters[idx + 1].start_seconds);
		} else if (idx === -1 && mediaDetail.chapters.length > 0) {
			jumpToTime(mediaDetail.chapters[0].start_seconds);
		}
	}

	function safePlay() {
		if (!videoElement) return;
		try {
			const res = videoElement.play();
			if (res && typeof res.catch === 'function') {
				res.catch(() => {});
			}
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

	function handleLoadedData() {
		if (pendingSeekTime !== null && videoElement) {
			videoElement.currentTime = pendingSeekTime;
			pendingSeekTime = null;
			safePlay();
		}
	}

	function handleWaiting() {
		isBuffering = true;
	}

	function handlePlaying() {
		isBuffering = false;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			if (showPlaybackInfo) {
				showPlaybackInfo = false;
			} else if (showAudioMenu || showSubtitlesMenu || showChaptersMenu) {
				showAudioMenu = false;
				showSubtitlesMenu = false;
				showChaptersMenu = false;
			} else {
				onClose();
			}
		} else if (e.key === ' ') {
			e.preventDefault();
			togglePlay();
		} else if (e.key === 'ArrowLeft') {
			e.preventDefault();
			jumpToTime(currentTime - 10);
		} else if (e.key === 'ArrowRight') {
			e.preventDefault();
			jumpToTime(currentTime + 10);
		} else if (e.key === 'PageUp') {
			e.preventDefault();
			skipPrevChapter();
		} else if (e.key === 'PageDown') {
			e.preventDefault();
			skipNextChapter();
		}
	}

	$effect(() => {
		if (selectedSubtitleIndex !== null && videoElement) {
			for (let i = 0; i < videoElement.textTracks.length; i++) {
				videoElement.textTracks[i].mode = 'showing';
			}
		}
	});

	onMount(() => {
		window.addEventListener('keydown', handleKeydown);
		return () => window.removeEventListener('keydown', handleKeydown);
	});
</script>

<div class="overlay" role="dialog" aria-label={title} use:portal>
	<div class="header">
		<div class="title-wrap">
			<h2>{title}</h2>
			{#if currentChapter}
				<span class="chapter-badge">{currentChapter.name}</span>
			{/if}
		</div>
		<div class="header-actions">
			{#if mediaDetail}
				<button
					class="icon-btn"
					class:active={showPlaybackInfo}
					onclick={() => (showPlaybackInfo = !showPlaybackInfo)}
					aria-label={$_('player.playback_info')}
					title={$_('player.playback_info')}
				>
					ℹ
				</button>
			{/if}
			<button class="close" onclick={onClose} aria-label={$_('player.close')}>✕</button>
		</div>
	</div>
	{#if errorMessage}
		<p class="error">{errorMessage}</p>
	{/if}

	<div class="video-container">
		<!-- svelte-ignore a11y_media_has_caption -->
		<video
			use:attachPlayer
			controls
			autoplay
			playsinline
			class="video"
			bind:currentTime
			bind:duration
			onloadeddata={handleLoadedData}
			onerror={handleVideoError}
			onwaiting={handleWaiting}
			onplaying={handlePlaying}
		>
			{#if widgetId && itemId && selectedSubtitleIndex !== null}
				<track
					kind="subtitles"
					src={api.jellyfinSubtitleUrl(widgetId, itemId, selectedSubtitleIndex)}
					label={activeSubtitleTrack?.display_title || 'Subtitles'}
					srclang={activeSubtitleTrack?.language || 'en'}
					default
				/>
			{/if}
		</video>

		{#if isBuffering && !errorMessage}
			<div class="buffering-overlay" aria-live="polite">
				<div class="spinner"></div>
				<span class="buffering-label">
					{playbackMethod === 'hls' ? $_('player.transcoding') : $_('common.loading')}
				</span>
			</div>
		{/if}

		{#if mediaDetail}
			<div class="custom-toolbar">
				<!-- Prev / Next Chapter Buttons -->
				<div class="chapter-nav-btns">
					<button
						class="control-btn"
						onclick={skipPrevChapter}
						aria-label={$_('player.prev_chapter')}
						title={$_('player.prev_chapter')}
					>
						⏮
					</button>
					<button
						class="control-btn"
						onclick={skipNextChapter}
						aria-label={$_('player.next_chapter')}
						title={$_('player.next_chapter')}
					>
						⏭
					</button>
				</div>

				<div class="menus-group">
					<!-- Chapters Menu -->
					{#if mediaDetail.chapters && mediaDetail.chapters.length > 0}
						<div class="menu-popover-wrap">
							<button
								class="control-btn menu-btn"
								class:active={showChaptersMenu}
								onclick={() => {
									showChaptersMenu = !showChaptersMenu;
									showAudioMenu = false;
									showSubtitlesMenu = false;
								}}
							>
								📑 {$_('player.chapters')} ({mediaDetail.chapters.length})
							</button>
							{#if showChaptersMenu}
								<div class="popover-menu">
									<div class="menu-header">{$_('player.chapters')}</div>
									<div class="menu-items">
										{#each mediaDetail.chapters as ch, idx (ch.start_seconds)}
											<button
												class="menu-item"
												class:selected={currentChapterIndex === idx}
												onclick={() => {
													jumpToTime(ch.start_seconds);
													showChaptersMenu = false;
												}}
											>
												<span class="ch-time">{formatTime(ch.start_seconds)}</span>
												<span class="ch-name">{ch.name || `Chapter ${idx + 1}`}</span>
											</button>
										{/each}
									</div>
								</div>
							{/if}
						</div>
					{/if}

					<!-- Subtitles (CC) Menu -->
					{#if mediaDetail.subtitle_streams && mediaDetail.subtitle_streams.length > 0}
						<div class="menu-popover-wrap">
							<button
								class="control-btn menu-btn"
								class:active={showSubtitlesMenu || selectedSubtitleIndex !== null}
								onclick={() => {
									showSubtitlesMenu = !showSubtitlesMenu;
									showAudioMenu = false;
									showChaptersMenu = false;
								}}
							>
								💬 CC
								{#if selectedSubtitleIndex !== null}
									<span class="active-dot">•</span>
								{/if}
							</button>
							{#if showSubtitlesMenu}
								<div class="popover-menu">
									<div class="menu-header">{$_('player.subtitles')}</div>
									<div class="menu-items">
										<button
											class="menu-item"
											class:selected={selectedSubtitleIndex === null}
											onclick={() => selectSubtitleTrack(null)}
										>
											{$_('player.subtitles_off')}
										</button>
										{#each mediaDetail.subtitle_streams as sub (sub.index)}
											<button
												class="menu-item"
												class:selected={selectedSubtitleIndex === sub.index}
												onclick={() => selectSubtitleTrack(sub.index)}
											>
												{sub.display_title}
											</button>
										{/each}
									</div>
								</div>
							{/if}
						</div>
					{/if}

					<!-- Audio Tracks Menu -->
					{#if mediaDetail.audio_streams && mediaDetail.audio_streams.length > 0}
						<div class="menu-popover-wrap">
							<button
								class="control-btn menu-btn"
								class:active={showAudioMenu}
								onclick={() => {
									showAudioMenu = !showAudioMenu;
									showSubtitlesMenu = false;
									showChaptersMenu = false;
								}}
							>
								🔊 {$_('player.audio_tracks')}
							</button>
							{#if showAudioMenu}
								<div class="popover-menu">
									<div class="menu-header">{$_('player.audio_tracks')}</div>
									<div class="menu-items">
										{#each mediaDetail.audio_streams as aud (aud.index)}
											<button
												class="menu-item"
												class:selected={selectedAudioIndex === aud.index}
												onclick={() => selectAudioTrack(aud.index)}
											>
												{aud.display_title}
											</button>
										{/each}
									</div>
								</div>
							{/if}
						</div>
					{/if}
				</div>
			</div>
		{/if}
	</div>

	<!-- Playback Info Overlay Modal -->
	{#if showPlaybackInfo && mediaDetail}
		<div class="info-overlay-modal" role="dialog" aria-label={$_('player.playback_info')}>
			<div class="info-card">
				<div class="info-header">
					<h3>{$_('player.playback_info')}</h3>
					<button class="info-close" onclick={() => (showPlaybackInfo = false)}>✕</button>
				</div>
				<div class="info-body">
					<div class="info-row">
						<span class="label">Media:</span>
						<span class="value"
							>{mediaDetail.name}
							{#if mediaDetail.year}({mediaDetail.year}){/if}</span
						>
					</div>
					{#if mediaDetail.container}
						<div class="info-row">
							<span class="label">{$_('player.container')}:</span>
							<span class="value uppercase">{mediaDetail.container}</span>
						</div>
					{/if}

					<div class="info-section-heading">{$_('player.playback_mode')}</div>
					<div class="info-row">
						<span class="label">{$_('player.playback_mode')}:</span>
						<span class="value"
							>{playbackMethod === 'direct'
								? $_('player.playback_method_direct')
								: $_('player.playback_method_hls')}</span
						>
					</div>
					{#if usedCachedFallback}
						<div class="info-row">
							<span class="value">{$_('player.playback_cache_active')}</span>
						</div>
					{/if}

					{#if mediaDetail.video_stream}
						<div class="info-section-heading">{$_('player.video')}</div>
						<div class="info-row">
							<span class="label">Codec:</span>
							<span class="value uppercase">{mediaDetail.video_stream.codec}</span>
						</div>
						{#if mediaDetail.video_stream.width && mediaDetail.video_stream.height}
							<div class="info-row">
								<span class="label">{$_('player.resolution')}:</span>
								<span class="value">{mediaDetail.video_stream.width}×{mediaDetail.video_stream.height}</span>
							</div>
						{/if}
						{#if mediaDetail.video_stream.framerate}
							<div class="info-row">
								<span class="label">Framerate:</span>
								<span class="value">{mediaDetail.video_stream.framerate} fps</span>
							</div>
						{/if}
					{/if}

					<div class="info-section-heading">{$_('player.audio')}</div>
					{#if activeAudioTrack}
						<div class="info-row">
							<span class="label">Track:</span>
							<span class="value">{activeAudioTrack.display_title}</span>
						</div>
						<div class="info-row">
							<span class="label">Codec:</span>
							<span class="value uppercase">{activeAudioTrack.codec}</span>
						</div>
						<div class="info-row">
							<span class="label">Channels:</span>
							<span class="value">{activeAudioTrack.channels} ch</span>
						</div>
					{:else}
						<div class="info-row"><span class="value">Default</span></div>
					{/if}

					<div class="info-section-heading">{$_('player.subtitle')}</div>
					<div class="info-row">
						<span class="label">Track:</span>
						<span class="value"
							>{activeSubtitleTrack ? activeSubtitleTrack.display_title : $_('player.subtitles_off')}</span
						>
					</div>

					{#if currentChapter}
						<div class="info-section-heading">Chapter</div>
						<div class="info-row">
							<span class="label">Current:</span>
							<span class="value">{currentChapter.name}</span>
						</div>
					{/if}
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
		background: rgba(0, 0, 0, 0.75);
		backdrop-filter: blur(8px);
	}

	.title-wrap {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		min-width: 0;
	}

	.header h2 {
		margin: 0;
		color: #fff;
		font-size: 1rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.chapter-badge {
		background: rgba(255, 255, 255, 0.15);
		color: rgba(255, 255, 255, 0.9);
		padding: 0.2rem 0.5rem;
		border-radius: 0.35rem;
		font-size: 0.8rem;
		white-space: nowrap;
	}

	.header-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.icon-btn {
		background: none;
		border: 1px solid rgba(255, 255, 255, 0.3);
		border-radius: 50%;
		width: 2rem;
		height: 2rem;
		color: #fff;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.9rem;
	}

	.icon-btn.active {
		border-color: #38bdf8;
		color: #38bdf8;
		background: rgba(56, 189, 248, 0.2);
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

	.buffering-overlay {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		pointer-events: none;
		background: rgba(0, 0, 0, 0.25);
	}

	.spinner {
		width: 2.5rem;
		height: 2.5rem;
		border: 3px solid rgba(255, 255, 255, 0.25);
		border-top-color: #38bdf8;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	.buffering-label {
		color: rgba(255, 255, 255, 0.85);
		font-size: 0.85rem;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.custom-toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.5rem 1rem;
		background: rgba(0, 0, 0, 0.85);
		border-top: 1px solid rgba(255, 255, 255, 0.1);
	}

	.chapter-nav-btns {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	.menus-group {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.control-btn {
		background: rgba(255, 255, 255, 0.1);
		border: 1px solid rgba(255, 255, 255, 0.2);
		border-radius: 0.4rem;
		padding: 0.35rem 0.65rem;
		color: #fff;
		font-size: 0.85rem;
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 0.35rem;
		transition: background 0.15s ease;
	}

	.control-btn:hover {
		background: rgba(255, 255, 255, 0.2);
	}

	.control-btn.active {
		background: rgba(56, 189, 248, 0.25);
		border-color: #38bdf8;
		color: #38bdf8;
	}

	.active-dot {
		color: #38bdf8;
		font-weight: bold;
	}

	.menu-popover-wrap {
		position: relative;
	}

	.popover-menu {
		position: absolute;
		bottom: 100%;
		right: 0;
		margin-bottom: 0.5rem;
		width: 15rem;
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
		display: flex;
		align-items: center;
		gap: 0.5rem;
		transition: background 0.15s ease;
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

	.ch-time {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.75rem;
		color: rgba(255, 255, 255, 0.5);
	}

	.ch-name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
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
