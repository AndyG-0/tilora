<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type ContainerSummary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<ContainerSummary | null>(null);

	const ENGINE_LABELS: Record<string, string> = { docker: 'Docker', podman: 'Podman' };
	const title = $derived(summary ? (ENGINE_LABELS[summary.engine] ?? 'Container') : 'Container');

	async function refresh() {
		try {
			summary = await api.widgetSummary<ContainerSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);
</script>

<TileCard {widgetId}>
	<div class="title">{title}</div>
	{#if !summary}
		<div class="hint">{$_('common.loading')}</div>
	{:else if !summary.connected}
		<div class="hint">{$_('common.not_connected')}</div>
	{:else if summary.error}
		<div class="hint error">{summary.error}</div>
	{:else}
		<div class="counts">
			<span class="running">{$_('container.tile.running', { values: { count: summary.running_count } })}</span>
			{#if summary.stopped_count > 0}
				<span class="stopped">{$_('container.tile.stopped', { values: { count: summary.stopped_count } })}</span>
			{/if}
		</div>
		<ul class="containers">
			{#each summary.containers.slice(0, 5) as container (container.name)}
				<li>
					<span class="dot" class:on={container.state === 'running'}></span>
					{container.name}
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

	.counts {
		display: flex;
		gap: 0.75rem;
		font-size: 0.9rem;
		margin-bottom: 0.35rem;
	}

	.running {
		color: var(--color-success);
	}

	.stopped {
		color: var(--color-text-muted);
	}

	.containers {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		font-size: 0.9rem;
		overflow: hidden;
	}

	.containers li {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		background: var(--color-text-muted);
		flex-shrink: 0;
	}

	.dot.on {
		background: var(--color-success);
	}
</style>
