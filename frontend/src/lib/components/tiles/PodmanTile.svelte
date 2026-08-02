<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type DockerSummary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<DockerSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<DockerSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 30_000);
</script>

<TileCard {widgetId}>
	<div class="title">Podman</div>
	{#if !summary}
		<div class="hint">Loading…</div>
	{:else if !summary.connected}
		<div class="hint">Not connected</div>
	{:else if summary.error}
		<div class="hint error">{summary.error}</div>
	{:else}
		<div class="counts">
			<span class="running">{summary.running_count} running</span>
			{#if summary.stopped_count > 0}
				<span class="stopped">{summary.stopped_count} stopped</span>
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
