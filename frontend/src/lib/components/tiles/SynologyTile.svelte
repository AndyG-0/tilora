<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type SynologySummary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<SynologySummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<SynologySummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);
</script>

<TileCard {widgetId}>
	<div class="title">Synology</div>
	{#if !summary}
		<div class="hint">{$_('common.loading')}</div>
	{:else if !summary.connected}
		<div class="hint">{$_('common.not_connected')}</div>
	{:else if summary.error}
		<div class="hint error">{summary.error}</div>
	{:else if summary.volumes.length === 0}
		<div class="hint">{$_('synology.tile.no_volumes')}</div>
	{:else}
		<ul class="volumes">
			{#each summary.volumes as volume (volume.name)}
				<li>
					<span class="dot" class:warn={volume.status !== 'normal'}></span>
					<span class="name">{volume.name}</span>
					<span class="percent">{volume.used_percent}%</span>
				</li>
			{/each}
		</ul>
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

	.volumes {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		font-size: 0.9rem;
	}

	.volumes li {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	.name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.percent {
		margin-left: auto;
		color: var(--color-text-muted);
	}

	.dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		background: var(--color-success);
		flex-shrink: 0;
	}

	.dot.warn {
		background: var(--color-warning);
	}
</style>
