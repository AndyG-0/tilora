<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import type { GoodreadsSummary } from '$lib/api';
	import { scrollFade } from '$lib/scrollFade';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<GoodreadsSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<GoodreadsSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);
</script>

<TileCard {widgetId}>
	{#if summary?.books.length}
		<div class="frame">
			<div class="title">Goodreads</div>
			<div class="scroll-wrap">
				<ul class="more-books" use:scrollFade={summary}>
					{#each summary.books as book (book.link)}
						<li>
							{#if book.book_image_url}
								<img class="thumb" src={book.book_image_url} alt="" loading="lazy" decoding="async" />
							{/if}
							<div class="book-text">
								<div class="book-title">{book.title}</div>
								{#if book.author_name}
									<div class="author">{book.author_name}</div>
								{/if}
							</div>
						</li>
					{/each}
				</ul>
			</div>
		</div>
	{:else}
		<div class="empty">{$_('goodreads.tile.empty')}</div>
	{/if}
</TileCard>

<style>
	.frame {
		position: relative;
		width: 100%;
		height: 100%;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin: 0 0 0.35rem;
	}

	.book-title {
		font-size: 0.95rem;
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.author {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.scroll-wrap {
		position: relative;
		flex: 1;
		min-height: 0;
	}

	.scroll-wrap::before,
	.scroll-wrap::after {
		content: '';
		position: absolute;
		left: 0;
		right: 0;
		height: 1.25rem;
		pointer-events: none;
		opacity: 0;
		transition: opacity 0.15s ease;
	}

	.scroll-wrap::before {
		top: 0;
		background: linear-gradient(to bottom, var(--color-surface), transparent);
	}

	.scroll-wrap::after {
		bottom: 0;
		background: linear-gradient(to top, var(--color-surface), transparent);
	}

	.scroll-wrap:global(.fade-top)::before {
		opacity: 1;
	}

	.scroll-wrap:global(.fade-bottom)::after {
		opacity: 1;
	}

	.more-books {
		list-style: none;
		margin: 0;
		padding: 0;
		height: 100%;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.more-books::-webkit-scrollbar {
		width: 4px;
	}

	.more-books::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 2px;
	}

	.more-books li {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-shrink: 0;
		padding-bottom: 0.4rem;
		border-bottom: 1px solid var(--color-border);
	}

	.more-books li:last-child {
		border-bottom: none;
		padding-bottom: 0;
	}

	.thumb {
		flex-shrink: 0;
		width: 2rem;
		height: 2.85rem;
		object-fit: cover;
		border-radius: 0.35rem;
	}

	.book-text {
		min-width: 0;
	}

	.empty {
		color: var(--color-text-muted);
	}
</style>
