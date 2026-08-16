<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import type { ChoresData } from '$lib/api';
	import { _ } from 'svelte-i18n';

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<ChoresData | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<ChoresData>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);

	// Checking an item off from the tile should complete it, not fall
	// through to TileCard's button and navigate to the detail page.
	async function complete(event: Event, id: number) {
		event.stopPropagation();
		try {
			await api.completeChore(id);
			await refresh();
		} catch {
			// leave the item checked-but-unsynced state to the next poll
		}
	}
</script>

<TileCard {widgetId}>
	<div class="widget">
		<div class="header">
			<span class="title">{summary?.title ?? 'To-Do'}</span>
			{#if summary && summary.open_count > 0}
				<span class="badge">{summary.open_count}</span>
			{/if}
		</div>
		{#if summary}
			{@const openItems = summary.chores.filter((chore) => !chore.completed)}
			{#if openItems.length > 0}
				<ul class="items">
					{#each openItems as chore (chore.id)}
						<li>
							<label>
								<input type="checkbox" onclick={(event) => complete(event, chore.id)} />
								<span class="text">{chore.text}</span>
							</label>
						</li>
					{/each}
				</ul>
			{:else}
				<div class="empty">{$_('common.all_done')}</div>
			{/if}
		{:else}
			<div class="empty">{$_('common.loading')}</div>
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

	.header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
		flex-shrink: 0;
	}

	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
	}

	.badge {
		flex-shrink: 0;
		background: var(--color-accent);
		color: var(--color-on-accent);
		border-radius: 999px;
		font-size: 0.75rem;
		line-height: 1;
		padding: 0.25rem 0.5rem;
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

	.items label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
	}

	.items input[type='checkbox'] {
		flex-shrink: 0;
	}

	.text {
		font-size: 0.95rem;
		line-height: 1.3;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
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
