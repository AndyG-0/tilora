<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type BF6Summary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<BF6Summary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<BF6Summary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	// Server population changes fast — matches the plugin's own 60s refresh
	// interval.
	pollWidget(refresh, 60_000);
</script>

<TileCard {widgetId}>
	<div class="title">Battlefield 6</div>
	{#if !summary}
		<div class="hint">Loading…</div>
	{:else if !summary.configured}
		<div class="hint">Not configured</div>
	{:else if summary.error && !summary.server && !summary.player}
		<div class="hint error">{summary.error}</div>
	{:else}
		{#if summary.server}
			<div class="server">
				<span class="pop">{summary.server.player_count}/{summary.server.max_players}</span>
				<span class="label">players</span>
			</div>
			<div class="map">{summary.server.mode} on {summary.server.map}</div>
		{/if}
		{#if summary.player}
			<div class="player">
				<span class="name">{summary.player.user_name}</span>
				<span class="kd">{summary.player.kill_death.toFixed(2)} K/D</span>
				{#if summary.player.win_percent}
					<span class="win">{summary.player.win_percent} win</span>
				{/if}
			</div>
		{/if}
		{#if summary.error}
			<div class="hint error small">{summary.error}</div>
		{/if}
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

	.hint.error.small {
		font-size: 0.8rem;
		margin-top: 0.35rem;
	}

	.server {
		display: flex;
		align-items: baseline;
		gap: 0.35rem;
		font-weight: 600;
	}

	.pop {
		font-size: 1.3rem;
	}

	.label {
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}

	.map {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin-top: 0.1rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.player {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.5rem;
		overflow: hidden;
	}

	.name {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.kd,
	.win {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		flex-shrink: 0;
	}
</style>
