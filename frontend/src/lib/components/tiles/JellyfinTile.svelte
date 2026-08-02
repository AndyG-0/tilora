<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import JellyfinPlayer from '$lib/components/JellyfinPlayer.svelte';
	import type { JellyfinItem } from '$lib/api';

	interface JellyfinSummary {
		connected: boolean;
		recent_items: JellyfinItem[];
	}

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<JellyfinSummary | null>(null);
	let playingItem = $state<JellyfinItem | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<JellyfinSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);

	// A poster tap should play that item, not fall through to TileCard's
	// button and maximize the whole widget — stop the click here so it never
	// bubbles up.
	function playItem(event: Event, item: JellyfinItem) {
		event.stopPropagation();
		playingItem = item;
	}
</script>

<TileCard {widgetId}>
	<div class="title">Jellyfin</div>
	{#if !summary}
		<div class="condition">Loading…</div>
	{:else if !summary.connected}
		<div class="condition">Not connected</div>
	{:else if summary.recent_items.length}
		<div class="posters">
			{#each summary.recent_items as item (item.id)}
				{#if item.has_poster}
					<span
						class="poster-btn"
						role="button"
						tabindex="0"
						aria-label={`Play ${item.name}`}
						onclick={(event) => playItem(event, item)}
						onkeydown={(event) => {
							if (event.key === 'Enter' || event.key === ' ') playItem(event, item);
						}}
					>
						<img class="poster" src={api.jellyfinImageUrl(widgetId, item.id)} alt={item.name} />
					</span>
				{/if}
			{/each}
		</div>
	{:else}
		<div class="condition">No recently added items</div>
	{/if}
</TileCard>

{#if playingItem}
	<JellyfinPlayer
		src={api.jellyfinStreamUrl(widgetId, playingItem.id)}
		title={playingItem.name}
		onClose={() => (playingItem = null)}
	/>
{/if}

<style>
	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin: 0 0 0.35rem;
	}

	.posters {
		display: flex;
		gap: 0.5rem;
		overflow: hidden;
	}

	.poster-btn {
		display: block;
		cursor: pointer;
		border-radius: 0.5rem;
	}

	.poster-btn:active .poster {
		opacity: 0.7;
	}

	.poster {
		height: 4.5rem;
		border-radius: 0.5rem;
		object-fit: cover;
		display: block;
	}

	.condition {
		color: var(--color-text-muted);
	}
</style>
