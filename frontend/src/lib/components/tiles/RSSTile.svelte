<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';

	interface RSSItem {
		title: string;
		link: string;
		source: string;
	}

	interface RSSSummary {
		title: string;
		items: RSSItem[];
	}

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<RSSSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<RSSSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);
</script>

<TileCard {widgetId}>
	<div class="widget">
		<div class="title">{summary?.title ?? 'Headlines'}</div>
		{#if summary?.items.length}
			<ul class="items">
				{#each summary.items as item (item.link)}
					<li>{item.title}</li>
				{/each}
			</ul>
		{:else}
			<div class="empty">Loading headlines…</div>
		{/if}
	</div>
</TileCard>

<style>
	.widget {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
	}

	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin-bottom: 0.5rem;
		flex-shrink: 0;
	}

	.items {
		margin: 0;
		padding: 0;
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}

	.items li {
		flex-shrink: 0;
		font-size: 0.95rem;
		line-height: 1.3;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		padding-bottom: 0.35rem;
		border-bottom: 1px solid var(--color-border);
	}

	.items li:last-child {
		border-bottom: none;
		padding-bottom: 0;
	}

	.items::-webkit-scrollbar {
		width: 4px;
	}

	.items::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 2px;
	}

	.empty {
		color: var(--color-text-muted);
	}
</style>
