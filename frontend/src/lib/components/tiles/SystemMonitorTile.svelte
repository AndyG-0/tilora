<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type SystemMonitorSummary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<SystemMonitorSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<SystemMonitorSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 10_000);
</script>

<TileCard {widgetId}>
	{#if !summary}
		<div class="status">Loading system stats…</div>
	{:else}
		<div class="title">{summary.hostname}</div>
		<div class="stats">
			<div class="stat">
				<div class="value">{Math.round(summary.cpu_percent)}%</div>
				<div class="label">CPU</div>
			</div>
			<div class="stat">
				<div class="value">{Math.round(summary.memory_percent)}%</div>
				<div class="label">RAM</div>
			</div>
			<div class="stat">
				<div class="value">{Math.round(summary.disk_percent)}%</div>
				<div class="label">Disk</div>
			</div>
		</div>
	{/if}
</TileCard>

<style>
	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin-bottom: 0.5rem;
	}

	.stats {
		display: flex;
		gap: 1.5rem;
	}

	.value {
		font-size: 1.6rem;
		font-weight: 600;
		line-height: 1.1;
	}

	.label {
		color: var(--color-text-muted);
		font-size: 0.8rem;
	}

	.status {
		color: var(--color-text-muted);
	}
</style>
