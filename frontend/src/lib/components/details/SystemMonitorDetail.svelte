<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api, type SystemMonitorDetail } from '$lib/api';

	let { data: initialData }: { data: SystemMonitorDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from the poll below.
	let stats = $state(initialData);

	const widgetId = $derived(page.params.id!);

	async function refresh() {
		try {
			stats = await api.widgetDetail<SystemMonitorDetail>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	onMount(() => {
		const interval = setInterval(refresh, 10_000);
		return () => clearInterval(interval);
	});

	function formatUptime(seconds: number): string {
		const days = Math.floor(seconds / 86_400);
		const hours = Math.floor((seconds % 86_400) / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		if (days > 0) return `${days}d ${hours}h`;
		if (hours > 0) return `${hours}h ${minutes}m`;
		return `${minutes}m`;
	}
</script>

<h1>{stats.hostname}</h1>

<div class="stats">
	<div class="stat">
		<div class="value">{Math.round(stats.cpu_percent)}%</div>
		<div class="label">CPU ({stats.cpu_count} cores)</div>
	</div>
	<div class="stat">
		<div class="value">{Math.round(stats.memory_percent)}%</div>
		<div class="label">RAM — {stats.memory_used_gb} / {stats.memory_total_gb} GB</div>
	</div>
	<div class="stat">
		<div class="value">{Math.round(stats.disk_percent)}%</div>
		<div class="label">Disk — {stats.disk_used_gb} / {stats.disk_total_gb} GB</div>
	</div>
	<div class="stat">
		<div class="value">{formatUptime(stats.uptime_seconds)}</div>
		<div class="label">Uptime</div>
	</div>
</div>

<div class="section">
	<h2>Per-core CPU</h2>
	<div class="cores">
		{#each stats.cpu_per_core as core, i (i)}
			<div class="core">
				<div class="core-bar"><div class="core-fill" style:width="{core}%"></div></div>
				<div class="core-label">{Math.round(core)}%</div>
			</div>
		{/each}
	</div>
</div>

<div class="section">
	<h2>Network (cumulative since boot)</h2>
	<p class="hint">↑ {stats.network_sent_gb} GB sent · ↓ {stats.network_recv_gb} GB received</p>
</div>

<p class="hint">
	Load average: {stats.load_average.map((n) => n.toFixed(2)).join(' / ')} (1m / 5m / 15m)
</p>

<style>
	h1 {
		margin: 0 0 1rem;
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr));
		gap: 1rem;
		margin: 1rem 0;
	}

	.stat {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.75rem 1rem;
	}

	.value {
		font-size: 1.6rem;
		font-weight: 600;
	}

	.label {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.section {
		margin: 1.5rem 0;
	}

	.section h2 {
		font-size: 1rem;
		margin: 0 0 0.5rem;
	}

	.cores {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(8rem, 1fr));
		gap: 0.5rem;
	}

	.core {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.core-bar {
		flex: 1;
		height: 0.5rem;
		border-radius: 0.25rem;
		background: var(--color-surface-hover, var(--color-border));
		overflow: hidden;
	}

	.core-fill {
		height: 100%;
		background: var(--color-accent);
	}

	.core-label {
		width: 3rem;
		text-align: right;
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.hint {
		color: var(--color-text-muted);
	}
</style>
