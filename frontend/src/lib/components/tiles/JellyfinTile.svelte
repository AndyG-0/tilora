<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import { scrollFade } from '$lib/scrollFade';
	import TileCard from '$lib/components/TileCard.svelte';
	import JellyfinPlayer from '$lib/components/JellyfinPlayer.svelte';
	import type { JellyfinItem, JellyfinSection } from '$lib/api';
	import { _ } from 'svelte-i18n';

	interface JellyfinSummary {
		connected: boolean;
		sections: JellyfinSection[];
	}

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<JellyfinSummary | null>(null);
	let playingItem = $state<JellyfinItem | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<JellyfinSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);

	// A poster tap should play that item, not fall through to TileCard's
	// button and maximize the whole widget — stop the click here so it never
	// bubbles up.
	function playItem(event: Event, item: JellyfinItem) {
		event.stopPropagation();
		playingItem = item;
	}
</script>

<TileCard {widgetId}>
	<div class="widget">
		<div class="title">Jellyfin</div>
		{#if !summary}
			<div class="condition">{$_('common.loading')}</div>
		{:else if !summary.connected}
			<div class="condition">{$_('common.not_connected')}</div>
		{:else if summary.sections.some((section) => section.items.length > 0)}
			<div class="scroll-wrap">
				<div class="sections" use:scrollFade={summary}>
					{#each summary.sections as section (section.label)}
						{#if section.items.length > 0}
							<div class="section">
								{#if summary.sections.length > 1}
									<div class="section-label">{section.label}</div>
								{/if}
								<div class="posters">
									{#each section.items as item (item.id)}
										{#if item.has_poster}
											<span
												class="poster-btn"
												role="button"
												tabindex="0"
												aria-label={$_('jellyfin.tile.play_aria', { values: { name: item.name } })}
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
							</div>
						{/if}
					{/each}
				</div>
			</div>
		{:else}
			<div class="condition">{$_('jellyfin.tile.nothing_to_show')}</div>
		{/if}
	</div>
</TileCard>

{#if playingItem}
	<JellyfinPlayer
		{widgetId}
		itemId={playingItem.id}
		src={api.jellyfinStreamUrl(widgetId, playingItem.id)}
		title={playingItem.name}
		onClose={() => (playingItem = null)}
	/>
{/if}

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
		margin: 0 0 0.35rem;
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

	.sections {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		height: 100%;
		overflow-y: auto;
	}

	.sections::-webkit-scrollbar {
		width: 4px;
	}

	.sections::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 2px;
	}

	.section-label {
		font-size: 0.7rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-text-muted);
		margin: 0 0 0.3rem;
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

	.poster-btn {
		display: block;
		flex-shrink: 0;
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
