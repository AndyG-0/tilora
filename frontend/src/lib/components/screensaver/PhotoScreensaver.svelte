<script lang="ts">
	import { fade } from 'svelte/transition';
	import { env } from '$env/dynamic/public';
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
		connected?: boolean;
		indexing?: boolean;
		index_error?: string;
	}

	let { data }: { data: PhotoScreensaverData } = $props();

	let index = $state(0);
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
		index = 0;
		restartAutoAdvance();
		return () => {
			if (autoAdvanceTimer) clearInterval(autoAdvanceTimer);
		};
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
