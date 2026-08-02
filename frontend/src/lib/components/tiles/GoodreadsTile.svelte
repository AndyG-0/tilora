<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import type { GoodreadsSummary } from '$lib/api';
	import { scrollFade } from '$lib/scrollFade';
	import TileCard from '$lib/components/TileCard.svelte';

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
		{@const book = summary.books[0]}
		{@const rest = summary.books.slice(1)}
		<div class="frame">
			{#if book.book_image_url}
				<div class="cover-wrap">
					<img class="cover" src={book.book_image_url} alt="" loading="lazy" decoding="async" />
				</div>
			{/if}
			<div class="info">
				<div class="book-title">{book.title}</div>
				{#if book.author_name}
					<div class="author">{book.author_name}</div>
				{/if}
			</div>
			{#if rest.length > 0}
				<div class="scroll-wrap">
					<ul class="more-books" use:scrollFade={summary}>
						{#each rest as more (more.link)}
							<li>
								<div class="book-title">{more.title}</div>
								{#if more.author_name}
									<div class="author">{more.author_name}</div>
								{/if}
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		</div>
	{:else}
		<div class="empty">No books on this shelf</div>
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

	.cover-wrap {
		flex: 1;
		min-height: 0;
		max-height: min(45%, 13rem);
		position: relative;
	}

	.cover {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: cover;
		border-radius: 0.75rem;
		display: block;
	}

	.info {
		flex-shrink: 0;
		padding-top: 0.5rem;
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
		margin-top: 0.5rem;
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
		flex-shrink: 0;
		padding-bottom: 0.4rem;
		border-bottom: 1px solid var(--color-border);
	}

	.more-books li:last-child {
		border-bottom: none;
		padding-bottom: 0;
	}

	.empty {
		color: var(--color-text-muted);
	}
</style>
