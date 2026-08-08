<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import type { RSSSummary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

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

	let groups = $derived(summary?.feed_groups ?? []);
	let hasItems = $derived(groups.some((group) => group.items.length > 0));
</script>

<TileCard {widgetId}>
	<div class="widget">
		<div class="title">{summary?.title ?? 'Headlines'}</div>
		{#if hasItems}
			<div class="groups">
				{#each groups as group (group.feed_id)}
					{#if group.items.length}
						{#if groups.length > 1}
							<div class="group-label">{group.name}</div>
						{/if}
						<ul class="items">
							{#each group.items as item (item.link)}
								<li>{item.title}</li>
							{/each}
						</ul>
					{/if}
				{/each}
			</div>
		{:else}
			<div class="empty">{$_('rss.tile.loading')}</div>
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

	.groups {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}

	.group-label {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}

	.items {
		margin: 0;
		padding: 0;
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
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

	.groups::-webkit-scrollbar {
		width: 4px;
	}

	.groups::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 2px;
	}

	.empty {
		color: var(--color-text-muted);
	}
</style>
