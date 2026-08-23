<script lang="ts">
	import { page } from '$app/state';
	import { api, type SystemMonitorDetail } from '$lib/api';
	import { pollWidget } from '$lib/polling';
	import { _ } from 'svelte-i18n';

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

	pollWidget(refresh, 10_000);

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
		<div class="label">{$_('system_monitor.detail.cpu_label', { values: { count: stats.cpu_count } })}</div>
	</div>
	<div class="stat">
		<div class="value">{Math.round(stats.memory_percent)}%</div>
		<div class="label">
			{$_('system_monitor.detail.ram_label', {
				values: { used: stats.memory_used_gb, total: stats.memory_total_gb },
			})}
		</div>
	</div>
	<div class="stat">
		<div class="value">{Math.round(stats.disk_percent)}%</div>
		<div class="label">
			{$_('system_monitor.detail.disk_label', { values: { used: stats.disk_used_gb, total: stats.disk_total_gb } })}
		</div>
	</div>
	<div class="stat">
		<div class="value">{formatUptime(stats.uptime_seconds)}</div>
		<div class="label">{$_('system_monitor.detail.uptime')}</div>
	</div>
</div>

<div class="section">
	<h2>{$_('system_monitor.detail.per_core_cpu')}</h2>
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
	<h2>{$_('system_monitor.detail.network_heading')}</h2>
	<p class="hint">
		{$_('system_monitor.detail.network_summary', {
			values: { sent: stats.network_sent_gb, recv: stats.network_recv_gb },
		})}
	</p>
</div>

<p class="hint">
	{$_('system_monitor.detail.load_average', {
		values: { avg: stats.load_average.map((n) => n.toFixed(2)).join(' / ') },
	})}
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
