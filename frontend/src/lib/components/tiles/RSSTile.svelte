<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import type { RSSSummary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<RSSSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<RSSSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);

	let groups = $derived(summary?.feed_groups ?? []);
	let erroredGroups = $derived(groups.filter((group) => !!group.error));
	let validGroups = $derived(groups.filter((group) => !group.error && group.items.length > 0));
	let hasItems = $derived(validGroups.length > 0);
</script>

<TileCard {widgetId}>
	<div class="widget">
		<div class="title">{summary?.title ?? $_('rss.tile.default_title')}</div>
		{#if !summary}
			<div class="empty">{$_('rss.tile.loading')}</div>
		{:else}
			{#if erroredGroups.length > 0}
				<div class="errors">
					{#each erroredGroups as group (group.feed_id)}
						<div class="error-notice">
							{#if groups.length > 1}
								<span class="error-feed-name">{group.name}:</span>
							{/if}
							<span class="error-text">{group.error}</span>
						</div>
					{/each}
				</div>
			{/if}
			{#if hasItems}
				<div class="groups">
					{#each validGroups as group (group.feed_id)}
						<div class="group">
							{#if groups.length > 1}
								<div class="group-label">{group.name}</div>
							{/if}
							<ul class="items">
								{#each group.items as item (item.link)}
									<li>{item.title}</li>
								{/each}
							</ul>
						</div>
					{/each}
				</div>
			{:else if erroredGroups.length === 0}
				{#if groups.length === 0}
					<div class="empty">{$_('rss.detail.no_feeds_selected_hint')}</div>
				{:else}
					<div class="empty">{$_('rss.detail.no_items')}</div>
				{/if}
			{/if}
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

	.errors {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		margin-bottom: 0.5rem;
		flex-shrink: 0;
	}

	.error-notice {
		display: flex;
		align-items: baseline;
		gap: 0.35rem;
		font-size: 0.85rem;
		line-height: 1.3;
		color: var(--color-error);
		overflow: hidden;
	}

	.error-feed-name {
		font-weight: 600;
		flex-shrink: 0;
	}

	.error-text {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.groups {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}

	.group {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.group-label {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.03em;
		margin-top: 0.25rem;
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
