<script lang="ts">
	import type Mpegts from 'mpegts.js';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	interface Props {
		src: string;
		title: string;
		onClose: () => void;
	}

	let { src, title, onClose }: Props = $props();

	let player: ReturnType<typeof Mpegts.createPlayer> | undefined;
	let errorMessage = $state<string | null>(null);
	let errorDetail = $state<string | null>(null);
	let destroyed = false;

	function genericHint() {
		return get(_)('hdhomerun.detail.playback_failed_hint', {
			values: { action: get(_)('hdhomerun.detail.open_external') },
		});
	}

	// mpegts.js reports a failed stream request as a bare "network error" and
	// throws the response body away, so the backend's carefully built 502
	// detail — which names the actual ffmpeg failure — never reaches the
	// user. Re-requesting the same URL is the only way to read it, and it's
	// cheap: the request has already failed, and the backend fails the same
	// way again in well under a second.
	async function fetchServerDetail() {
		try {
			const response = await fetch(src, { credentials: 'include' });
			if (response.ok) {
				// It works on a retry, so there's nothing more specific to
				// say than the generic hint.
				response.body?.cancel();
				return null;
			}
			const body = await response.json();
			return typeof body?.detail === 'string' ? body.detail : null;
		} catch {
			return null;
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
		// mpegts.js's UMD bundle references `window` at import time, so a
		// static import would crash SvelteKit's server-side render of this
		// page (Node has no `window`). Deferring to a dynamic import here
		// means it only ever loads client-side, once this action runs.
		import('mpegts.js').then(({ default: mpegts }) => {
			if (destroyed) return;
			player = mpegts.createPlayer(
				{ type: 'mse', isLive: true, url: src, withCredentials: true },
				{ enableStashBuffer: false, liveBufferLatencyChasing: true },
			);
			player.on(mpegts.Events.ERROR, (errorType: string) => {
				errorMessage = genericHint();
				if (errorType !== mpegts.ErrorTypes.NETWORK_ERROR) return;
				fetchServerDetail().then((detail) => {
					if (!destroyed) errorDetail = detail;
				});
			});
			player.attachMediaElement(node);
			player.load();
			player.play();
		});

		return {
			destroy() {
				// Closes the underlying HTTP connection — this is what lets the
				// backend's stream route notice the disconnect and kill its
				// ffmpeg process. Skipping this leaks it indefinitely.
				destroyed = true;
				player?.pause();
				player?.unload();
				player?.detachMediaElement();
				player?.destroy();
				player = undefined;
			},
		};
	}
</script>

<div class="overlay" role="dialog" aria-label={title} use:portal>
	<div class="header">
		<h2>{title}</h2>
		<button class="close" onclick={onClose} aria-label={$_('player.close')}>✕</button>
	</div>
	{#if errorMessage}
		<p class="error">
			{errorMessage}
			{#if errorDetail}
				<span class="error-detail">{errorDetail}</span>
			{/if}
		</p>
	{/if}
	<!-- svelte-ignore a11y_media_has_caption -->
	<video controls autoplay playsinline class="video" use:attachPlayer></video>
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
		/* ffmpeg output is long, unwrappable and often the whole answer —
		   scroll it rather than letting it push the video off-screen. */
		max-height: 6rem;
		overflow: auto;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		opacity: 0.85;
	}

	.video {
		flex: 1;
		width: 100%;
		min-height: 0;
		object-fit: contain;
		background: #000;
	}
</style>
