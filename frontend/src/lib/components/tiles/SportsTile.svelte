<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type SportsSummary, type SportsTrendingGame } from '$lib/api';
	import { scrollFade } from '$lib/scrollFade';
	import TileCard from '$lib/components/TileCard.svelte';

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<SportsSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<SportsSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	// Schedules/broadcasts don't change minute to minute — matches the
	// plugin's own 15-minute cache TTL, no point polling more often.
	pollWidget(refresh, 15 * 60_000);

	function formatDate(iso: string | null): string {
		if (!iso) return '';
		return new Date(iso).toLocaleString(undefined, {
			weekday: 'short',
			month: 'numeric',
			day: 'numeric',
			hour: 'numeric',
			minute: '2-digit',
		});
	}

	function trendingMatchup(game: SportsTrendingGame): string {
		const away = game.away_rank ? `#${game.away_rank} ${game.away_team}` : game.away_team;
		const home = game.home_rank ? `#${game.home_rank} ${game.home_team}` : game.home_team;
		return `${away} @ ${home}`;
	}
</script>

<TileCard {widgetId}>
	<div class="frame">
		<div class="title">Sports</div>
		{#if !summary}
			<div class="hint">Loading…</div>
		{:else if !summary.configured && summary.trending.length === 0}
			<div class="hint">No teams configured</div>
		{:else}
			<div class="scroll-wrap">
				<div class="sections" use:scrollFade={summary}>
					{#if summary.configured}
						<div class="section">
							{#if summary.trending.length > 0}
								<div class="section-label">Your Teams</div>
							{/if}
							{#if summary.games.length === 0}
								<div class="hint">No upcoming games</div>
							{:else}
								<ul class="games">
									{#each summary.games as game (game.league + game.team + game.id)}
										<li>
											<div class="matchup">
												<span class="league">{game.league_label}</span>
												<span class="teams">{game.team} {game.is_home ? 'vs' : '@'} {game.opponent}</span>
											</div>
											<div class="meta">
												<span class="when">
													{game.state === 'in' ? `Live — ${game.status_detail}` : formatDate(game.date)}
												</span>
												{#if game.broadcasts.length > 0}
													<span class="broadcast">{game.broadcasts.join(', ')}</span>
												{/if}
											</div>
										</li>
									{/each}
								</ul>
							{/if}
						</div>
					{/if}
					{#if summary.trending.length > 0}
						<div class="section">
							{#if summary.configured}
								<div class="section-label">Top Games Today</div>
							{/if}
							<ul class="games">
								{#each summary.trending as game (game.league + game.id)}
									<li>
										<div class="matchup">
											<span class="league">{game.league_label}</span>
											<span class="teams">{trendingMatchup(game)}</span>
										</div>
										<div class="meta">
											<span class="when">
												{game.state === 'in' ? `Live — ${game.status_detail}` : formatDate(game.date)}
											</span>
											{#if game.broadcast_links.length > 0}
												<span class="broadcast">{game.broadcast_links.map((link) => link.name).join(', ')}</span>
											{/if}
										</div>
									</li>
								{/each}
							</ul>
						</div>
					{/if}
				</div>
			</div>
		{/if}
	</div>
</TileCard>

<style>
	.frame {
		display: flex;
		flex-direction: column;
		width: 100%;
		height: 100%;
		overflow: hidden;
	}

	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin: 0 0 0.35rem;
	}

	.hint {
		color: var(--color-text-muted);
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
		gap: 0.75rem;
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

	.games {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.games li {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.matchup {
		display: flex;
		align-items: baseline;
		gap: 0.4rem;
		overflow: hidden;
	}

	.league {
		flex-shrink: 0;
		font-size: 0.7rem;
		color: var(--color-text-muted);
		border: 1px solid var(--color-border);
		border-radius: 0.3rem;
		padding: 0.05rem 0.3rem;
	}

	.teams {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.meta {
		display: flex;
		gap: 0.5rem;
		font-size: 0.8rem;
		color: var(--color-text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
