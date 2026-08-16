<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type AsusRouterSummary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<AsusRouterSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<AsusRouterSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);
</script>

<TileCard {widgetId}>
	<div class="title">Router</div>
	{#if !summary}
		<div class="hint">{$_('common.loading')}</div>
	{:else if !summary.connected}
		<div class="hint">{$_('common.not_connected')}</div>
	{:else if summary.error}
		<div class="hint error">{summary.error}</div>
	{:else}
		<div class="stats">
			<div class="wan">
				<span class="dot" class:down={!summary.wan_connected}></span>
				{summary.wan_connected ? $_('asus_router.tile.wan_up') : $_('asus_router.tile.wan_down')}
			</div>
			<div class="clients">{$_('asus_router.tile.clients', { values: { count: summary.client_count } })}</div>
		</div>
	{/if}
</TileCard>

<style>
	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin: 0 0 0.35rem;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}

	.stats {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		font-size: 0.9rem;
	}

	.wan {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	.clients {
		color: var(--color-text-muted);
	}

	.dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		background: var(--color-success);
		flex-shrink: 0;
	}

	.dot.down {
		background: var(--color-error);
	}
</style>
