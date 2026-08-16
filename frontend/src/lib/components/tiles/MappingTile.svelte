<script lang="ts">
	import { goto } from '$app/navigation';
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	interface MappingSummary {
		location_name: string | null;
		latitude: number | null;
		longitude: number | null;
	}

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<MappingSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<MappingSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);

	function openPanel(e: MouseEvent, panel: 'directions' | 'nearby') {
		e.stopPropagation();
		goto(`/widget/${widgetId}?panel=${panel}`);
	}
</script>

<TileCard {widgetId}>
	<div class="icon" aria-hidden="true">📍</div>
	{#if summary?.location_name}
		<div class="location">{summary.location_name}</div>
	{:else}
		<div class="location muted">{$_('mapping.tile.no_location')}</div>
	{/if}
	<div class="actions">
		<button class="quick-link" onclick={(e) => openPanel(e, 'directions')}>{$_('mapping.tile.directions')}</button>
		<button class="quick-link" onclick={(e) => openPanel(e, 'nearby')}>{$_('mapping.tile.nearby')}</button>
	</div>
</TileCard>

<style>
	.icon {
		font-size: clamp(1.5rem, 20cqh, 3rem);
		line-height: 1;
	}

	.location {
		font-size: clamp(0.85rem, 10cqh, 1.1rem);
		font-weight: 600;
		margin-top: 0.25rem;
	}

	.location.muted {
		color: var(--color-text-muted);
		font-weight: 400;
	}

	.actions {
		display: flex;
		gap: 0.5rem;
		margin-top: 0.5rem;
	}

	.quick-link {
		font-size: clamp(0.65rem, 7cqh, 0.8rem);
		background: var(--color-surface-hover);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.25rem 0.6rem;
		color: var(--color-accent);
		cursor: pointer;
	}
</style>
