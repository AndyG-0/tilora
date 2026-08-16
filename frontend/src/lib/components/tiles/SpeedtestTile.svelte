<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type SpeedtestSummary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<SpeedtestSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<SpeedtestSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);

	function formatMbps(value: number | null | undefined): string {
		return value === null || value === undefined ? '—' : `${value.toFixed(1)} Mbps`;
	}
</script>

<TileCard {widgetId}>
	{#if !summary}
		<div class="status">{$_('speedtest.tile.loading')}</div>
	{:else if summary.ran_at === null}
		<div class="title">{summary.title}</div>
		<div class="status">{$_('speedtest.tile.no_results')}</div>
	{:else}
		<div class="title">{summary.title}</div>
		<div class="speeds">
			<div class="speed down">↓ {formatMbps(summary.download_mbps)}</div>
			<div class="speed up">↑ {formatMbps(summary.upload_mbps)}</div>
		</div>
		<div class="status">{summary.ping_ms?.toFixed(0)} ms · {summary.server_name}</div>
	{/if}
</TileCard>

<style>
	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
	}

	.speeds {
		display: flex;
		gap: 1rem;
		font-size: 1.5rem;
		font-weight: 600;
		line-height: 1.1;
	}

	.speed.down {
		color: var(--color-accent);
	}

	.speed.up {
		color: var(--color-success);
	}

	.status {
		color: var(--color-text-muted);
	}
</style>
