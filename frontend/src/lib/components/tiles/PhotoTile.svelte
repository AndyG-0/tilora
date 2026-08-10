<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { env } from '$env/dynamic/public';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	interface PhotoSummary {
		count: number;
		current: { filename: string; url: string } | null;
		indexing?: boolean;
		index_error?: string;
	}

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<PhotoSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<PhotoSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);
</script>

<TileCard
	{widgetId}
	href={summary?.current ? `/widget/${widgetId}?photo=${encodeURIComponent(summary.current.filename)}` : undefined}
>
	{#if summary?.current}
		<div class="frame">
			<img class="photo" src={`${env.PUBLIC_API_BASE_URL}${summary.current.url}`} alt="" />
			<div class="count">{$_('photos.tile.count', { values: { count: summary.count } })}</div>
		</div>
	{:else if summary?.indexing}
		<div class="empty">{$_('photos.tile.indexing')}</div>
	{:else if summary?.index_error}
		<div class="empty error">{summary.index_error}</div>
	{:else}
		<div class="empty">{$_('photos.tile.no_photos')}</div>
	{/if}
</TileCard>

<style>
	.frame {
		position: relative;
		width: 100%;
		height: 100%;
	}

	.photo {
		width: 100%;
		height: 100%;
		object-fit: cover;
		border-radius: 0.75rem;
		display: block;
	}

	.count {
		position: absolute;
		bottom: 0.5rem;
		left: 0.5rem;
		font-size: 0.8rem;
		color: var(--color-text-muted);
		background: var(--color-surface);
		padding: 0.15rem 0.5rem;
		border-radius: 0.5rem;
	}

	.empty {
		color: var(--color-text-muted);
	}

	.empty.error {
		color: var(--color-error);
	}
</style>
