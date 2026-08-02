<script lang="ts">
	import type Mpegts from 'mpegts.js';

	interface Props {
		src: string;
		title: string;
		onClose: () => void;
	}

	let { src, title, onClose }: Props = $props();

	let player: ReturnType<typeof Mpegts.createPlayer> | undefined;
	let errorMessage = $state<string | null>(null);
	let destroyed = false;

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
				{ type: 'mse', isLive: true, url: src },
				{ enableStashBuffer: false, liveBufferLatencyChasing: true },
			);
			player.on(mpegts.Events.ERROR, () => {
				errorMessage =
					'Playback failed — this tuner may not support this playback mode. Try "Open in external player" instead.';
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
		<button class="close" onclick={onClose} aria-label="Close player">✕</button>
	</div>
	{#if errorMessage}
		<p class="error">{errorMessage}</p>
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

	.video {
		flex: 1;
		width: 100%;
		min-height: 0;
		object-fit: contain;
		background: #000;
	}
</style>
