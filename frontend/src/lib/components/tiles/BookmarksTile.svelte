<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import type { BookmarksData } from '$lib/api';
	import { faviconSrc, hideBrokenIcon } from '$lib/bookmarkIcons';
	import { _ } from 'svelte-i18n';

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<BookmarksData | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<BookmarksData>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);

	// A bookmark tap should open the link, not fall through to TileCard's
	// button and navigate to the widget's detail page — stop it here so it
	// never bubbles up.
	function openBookmark(event: Event) {
		event.stopPropagation();
	}
</script>

<TileCard {widgetId}>
	<div class="widget">
		<div class="title">{summary?.title ?? 'Bookmarks'}</div>
		{#if summary?.bookmarks.length}
			<ul class="items">
				{#each summary.bookmarks as bookmark (bookmark.url)}
					<li>
						<a href={bookmark.url} target="_blank" rel="noreferrer" onclick={openBookmark}>
							<img class="icon" src={faviconSrc(bookmark)} alt="" onerror={hideBrokenIcon} />
							<span class="name">{bookmark.name}</span>
						</a>
					</li>
				{/each}
			</ul>
		{:else if summary}
			<div class="empty">{$_('bookmarks.tile.empty')}</div>
		{:else}
			<div class="empty">{$_('bookmarks.tile.loading')}</div>
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
		border-bottom: 1px solid var(--color-border);
		padding-bottom: 0.35rem;
	}

	.items li:last-child {
		border-bottom: none;
		padding-bottom: 0;
	}

	.items a {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: inherit;
		text-decoration: none;
	}

	.icon {
		width: 1rem;
		height: 1rem;
		flex-shrink: 0;
		border-radius: 0.2rem;
	}

	.name {
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
