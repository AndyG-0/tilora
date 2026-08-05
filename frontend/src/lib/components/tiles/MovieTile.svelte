<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import { scrollFade } from '$lib/scrollFade';
	import TileCard from '$lib/components/TileCard.svelte';

	interface Movie {
		id: number;
		title: string;
		poster_url: string | null;
	}

	interface MoviesSummary {
		popular_movies?: Movie[];
		popular_tv_shows?: Movie[];
		trending_movies?: Movie[];
		trending_tv_shows?: Movie[];
		on_streaming_movies?: Movie[];
		on_streaming_tv_shows?: Movie[];
	}

	const SECTIONS: { key: keyof MoviesSummary; title: string }[] = [
		{ key: 'popular_movies', title: 'Popular Movies' },
		{ key: 'trending_movies', title: 'Trending Movies' },
		{ key: 'popular_tv_shows', title: 'Popular Shows' },
		{ key: 'trending_tv_shows', title: 'Trending Shows' },
		{ key: 'on_streaming_movies', title: 'On Streaming: Movies' },
		{ key: 'on_streaming_tv_shows', title: 'On Streaming: Shows' },
	];

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<MoviesSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<MoviesSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);
</script>

<TileCard {widgetId}>
	<div class="widget">
		{#if summary}
			<div class="scroll-wrap">
				<div class="list" use:scrollFade={summary}>
					{#each SECTIONS as section (section.key)}
						{@const items = summary[section.key]}
						{#if items?.length}
							<div class="section">
								<div class="title">{section.title}</div>
								<div class="posters">
									{#each items as movie (movie.id)}
										{#if movie.poster_url}
											<img class="poster" src={movie.poster_url} alt={movie.title} />
										{/if}
									{/each}
								</div>
							</div>
						{/if}
					{/each}
				</div>
			</div>
		{:else}
			<div class="title">Movies & Shows</div>
			<div class="condition">Loading…</div>
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

	.list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		height: 100%;
		overflow-y: auto;
	}

	.list::-webkit-scrollbar {
		width: 4px;
	}

	.list::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 2px;
	}

	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin: 0 0 0.35rem;
	}

	.posters {
		display: flex;
		gap: 0.5rem;
		overflow-x: auto;
		padding-bottom: 0.25rem;
	}

	.posters::-webkit-scrollbar {
		height: 4px;
	}

	.posters::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 2px;
	}

	.poster {
		flex-shrink: 0;
		height: 4.5rem;
		border-radius: 0.5rem;
		object-fit: cover;
	}

	.condition {
		color: var(--color-text-muted);
	}
</style>
