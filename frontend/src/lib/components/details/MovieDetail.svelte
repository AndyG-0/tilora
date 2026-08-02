<script lang="ts">
	interface Movie {
		id: number;
		title: string;
		release_date: string | null;
		rating: number | null;
		poster_url: string | null;
		overview: string;
		where_to_watch: string[];
	}

	interface MoviesDetailData {
		movies: Movie[];
		tv_shows: Movie[];
		trending_tv_shows: Movie[];
		region: string;
	}

	let { data }: { data: MoviesDetailData } = $props();
</script>

{#snippet mediaList(items: Movie[])}
	<div class="list">
		{#each items as item (item.id)}
			<div class="movie">
				{#if item.poster_url}
					<img class="poster" src={item.poster_url} alt={item.title} />
				{/if}
				<div class="info">
					<h2>{item.title}</h2>
					<p class="meta">
						{item.release_date ?? 'Unknown release date'}
						{#if item.rating}· {item.rating.toFixed(1)}★{/if}
					</p>
					<p class="overview">{item.overview}</p>
					{#if item.where_to_watch.length > 0}
						<p class="providers">
							Streaming in {data.region} on: {item.where_to_watch.join(', ')}
						</p>
					{:else}
						<p class="providers muted">Not currently streaming in {data.region}</p>
					{/if}
				</div>
			</div>
		{/each}
	</div>
{/snippet}

<h1>Movies</h1>
{@render mediaList(data.movies)}

<h1>Shows</h1>
{@render mediaList(data.tv_shows)}

<h1>Trending</h1>
{@render mediaList(data.trending_tv_shows)}

<style>
	h1 {
		margin: 0 0 1rem;
	}

	h1:not(:first-child) {
		margin-top: 2rem;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.movie {
		display: flex;
		gap: 1rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1rem;
	}

	.poster {
		width: 6rem;
		height: 9rem;
		object-fit: cover;
		border-radius: 0.5rem;
		flex-shrink: 0;
	}

	.info h2 {
		margin: 0 0 0.25rem;
		font-size: 1.1rem;
	}

	.meta {
		color: var(--color-text-muted);
		margin: 0 0 0.5rem;
	}

	.overview {
		margin: 0 0 0.5rem;
	}

	.providers {
		font-size: 0.9rem;
		margin: 0;
	}

	.providers.muted {
		color: var(--color-text-muted);
	}
</style>
