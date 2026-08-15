<script lang="ts">
	import { fade } from 'svelte/transition';
	import { env } from '$env/dynamic/public';
	import { getCursor, setCursor } from '$lib/stores/screensaverProgress';
	import { _ } from 'svelte-i18n';

	interface Photo {
		filename: string;
		url: string;
	}

	interface PhotoScreensaverData {
		provider?: 'local' | 'icloud_shared' | 'icloud_private' | 'immich';
		count: number;
		interval_seconds: number;
		photos: Photo[];
		configured?: boolean;
		connected?: boolean;
		indexing?: boolean;
		index_error?: string;
	}

	let { id, data }: { id: string; data: PhotoScreensaverData } = $props();

	// Clamp immediately (not just in the effect below) so a stale/out-of-range
	// stored cursor never reaches the initial render's `data.photos[index]`
	// lookup before the effect has a chance to correct it.
	const initialCursor = getCursor(id);
	let index = $state(data.photos.length ? initialCursor % data.photos.length : 0);
	let autoAdvanceTimer: ReturnType<typeof setInterval> | null = null;

	function restartAutoAdvance() {
		if (autoAdvanceTimer) clearInterval(autoAdvanceTimer);
		autoAdvanceTimer = null;
		if (data.photos.length <= 1) return;
		autoAdvanceTimer = setInterval(() => {
			index = (index + 1) % data.photos.length;
		}, data.interval_seconds * 1000);
	}

	$effect(() => {
		// Clamp rather than reset so a same-widget data refresh (rotation
		// revisit, or resuming after an idle interruption) picks up where the
		// last-shown photo left off instead of restarting at photo 0.
		index = data.photos.length ? index % data.photos.length : 0;
		restartAutoAdvance();
		return () => {
			if (autoAdvanceTimer) clearInterval(autoAdvanceTimer);
		};
	});

	$effect(() => {
		setCursor(id, index);
	});
</script>

<div class="stage">
	{#if data.photos.length > 0}
		{#key index}
			<img
				class="photo"
				src={`${env.PUBLIC_API_BASE_URL}${data.photos[index].url}`}
				alt={data.photos[index].filename}
				transition:fade={{ duration: 800 }}
			/>
		{/key}
	{:else if data.indexing}
		<p class="caption">{$_('photos.tile.indexing')}</p>
	{:else if data.configured === false}
		<p class="caption">{$_('common.not_configured')}</p>
	{:else if data.provider === 'icloud_private' && !data.connected}
		<p class="caption">{$_('common.not_connected')}</p>
	{:else}
		<p class="caption">{$_('photos.tile.no_photos')}</p>
	{/if}
</div>

<style>
	.stage {
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		position: relative;
	}

	.photo {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: contain;
	}

	.caption {
		color: var(--color-text-muted);
		font-size: 1.5rem;
	}
</style>
