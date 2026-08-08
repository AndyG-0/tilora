<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import type { NASAApodSummary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<NASAApodSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<NASAApodSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);
</script>

<TileCard {widgetId}>
	{#if summary?.available}
		<div class="frame">
			{#if summary.thumbnail_url}
				<div class="image-wrap">
					<img class="image" src={summary.thumbnail_url} alt="" loading="lazy" decoding="async" />
				</div>
			{/if}
			<div class="info">
				<div class="apod-title">{summary.apod_title}</div>
				{#if summary.date}
					<div class="date">{summary.date}</div>
				{/if}
			</div>
		</div>
	{:else if summary}
		<div class="empty">{$_('nasa_apod.tile.unavailable')}</div>
	{:else}
		<div class="empty">{$_('common.loading')}</div>
	{/if}
</TileCard>

<style>
	.frame {
		position: relative;
		width: 100%;
		height: 100%;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.image-wrap {
		flex: 1;
		min-height: 0;
		position: relative;
	}

	.image {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: cover;
		border-radius: 0.75rem;
		display: block;
	}

	.info {
		flex-shrink: 0;
		padding-top: 0.5rem;
	}

	.apod-title {
		font-size: 0.95rem;
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.date {
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}

	.empty {
		color: var(--color-text-muted);
	}
</style>
