<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type SteamSummary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<SteamSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<SteamSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	// Presence/currently-playing should feel fairly live — matches the
	// plugin's own 60s refresh interval.
	pollWidget(refresh, 60_000);
</script>

<TileCard {widgetId}>
	<div class="title">Steam</div>
	{#if !summary}
		<div class="hint">{$_('common.loading')}</div>
	{:else if !summary.configured}
		<div class="hint">{$_('common.not_configured')}</div>
	{:else if summary.error}
		<div class="hint error">{summary.error}</div>
	{:else if !summary.player}
		<div class="hint">{$_('common.no_data')}</div>
	{:else}
		<div class="player">
			<span class="dot" class:on={summary.player.online}></span>
			<span class="name">{summary.player.name}</span>
		</div>
		<div class="status">
			{#if summary.current_game}
				{$_('steam.tile.playing_prefix')} <span class="game">{summary.current_game}</span>
			{:else}
				{summary.player.status}
			{/if}
		</div>
		{#if summary.recent_games.length > 0}
			<ul class="recent">
				{#each summary.recent_games.slice(0, 2) as game (game.appid)}
					<li>{game.name}</li>
				{/each}
			</ul>
		{/if}
		{#if summary.news.length > 0}
			<div class="latest-news">{$_('steam.tile.latest_prefix')} {summary.news[0].title}</div>
		{/if}
	{/if}
</TileCard>

<style>
	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin: 0 0 0.35rem;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}

	.player {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 600;
		overflow: hidden;
	}

	.name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		background: var(--color-text-muted);
		flex-shrink: 0;
	}

	.dot.on {
		background: var(--color-success);
	}

	.status {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin-top: 0.15rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.game {
		color: var(--color-text);
	}

	.recent {
		list-style: none;
		margin: 0.4rem 0 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		font-size: 0.8rem;
		color: var(--color-text-muted);
		overflow: hidden;
	}

	.recent li {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.latest-news {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		margin-top: 0.35rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
