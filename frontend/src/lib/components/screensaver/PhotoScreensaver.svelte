<script lang="ts">
	import { untrack } from 'svelte';
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

	// Read through `$derived` (value-memoized) rather than off `data` directly
	// in the effect below -- `data` is reassigned to a brand-new object on
	// every same-widget refetch (rotation revisit, or the outer screensaver's
	// periodic re-poll of the widget currently on screen), even when the
	// photo count and interval haven't actually changed. Depending on `data`
	// itself would retrigger the effect on every such refetch and clear+
	// restart `autoAdvanceTimer` before it ever gets to fire -- which looked
	// like "photos not rotating" whenever the refetch cadence was shorter
	// than (or close to) the configured photo interval.
	const photoCount = $derived(data.photos.length);
	const intervalSeconds = $derived(data.interval_seconds);

	function restartAutoAdvance(count: number, seconds: number) {
		if (autoAdvanceTimer) clearInterval(autoAdvanceTimer);
		autoAdvanceTimer = null;
		if (count <= 1) return;
		autoAdvanceTimer = setInterval(() => {
			index = (index + 1) % count;
		}, seconds * 1000);
	}

	$effect(() => {
		const count = photoCount;
		const seconds = intervalSeconds;
		// Clamp rather than reset so a same-widget data refresh (rotation
		// revisit, or resuming after an idle interruption) picks up where the
		// last-shown photo left off instead of restarting at photo 0. Read
		// untracked -- `restartAutoAdvance` below already keeps `index` moving
		// on its own recurring interval, so this effect only needs to
		// (re)start that interval when `count`/`seconds` actually change, not
		// on every tick of the interval it just started.
		untrack(() => {
			index = count ? index % count : 0;
		});
		restartAutoAdvance(count, seconds);
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
				src={`${env.PUBLIC_API_BASE_URL ?? ''}${data.photos[index].url}`}
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
