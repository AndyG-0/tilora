<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type PiholeSummary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<PiholeSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<PiholeSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);
</script>

<TileCard {widgetId}>
	{#if !summary}
		<div class="status">{$_('pihole.tile.loading')}</div>
	{:else if !summary.connected}
		<div class="title">Pi-hole</div>
		<div class="status">{$_('common.not_connected')}</div>
	{:else if summary.error}
		<div class="title">Pi-hole</div>
		<div class="status error">{summary.error}</div>
	{:else}
		<div class="header">
			<div class="title">Pi-hole</div>
			<div class="badge" class:on={summary.blocking_enabled} class:off={!summary.blocking_enabled}>
				{summary.blocking_enabled ? $_('pihole.tile.enabled') : $_('pihole.tile.paused')}
			</div>
		</div>
		<div class="percent">{Math.round(summary.percent_blocked ?? 0)}%</div>
		<div class="status">
			{$_('pihole.tile.blocked_summary', {
				values: {
					blocked: (summary.blocked_today ?? 0).toLocaleString(),
					queries: (summary.queries_today ?? 0).toLocaleString(),
				},
			})}
		</div>
	{/if}
</TileCard>

<style>
	.header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
	}

	.badge {
		font-size: 0.75rem;
		border-radius: 1rem;
		padding: 0.15rem 0.5rem;
	}

	.badge.on {
		color: var(--color-success);
	}

	.badge.off {
		color: var(--color-warning);
	}

	.percent {
		font-size: 3rem;
		font-weight: 600;
		line-height: 1.1;
	}

	.status {
		color: var(--color-text-muted);
	}

	.status.error {
		color: var(--color-error);
	}
</style>
