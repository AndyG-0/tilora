<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type SportsSummary, type SportsTrendingGame } from '$lib/api';
	import { scrollFade } from '$lib/scrollFade';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<SportsSummary | null>(null);

	const showToday = $derived(!!summary && summary.configured && summary.todays_games.length > 0);
	const showTrending = $derived(!!summary && summary.trending.length > 0);
	const showUpcoming = $derived(!!summary && summary.configured);
	const visibleSections = $derived([showToday, showTrending, showUpcoming].filter(Boolean).length);

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

	function awayLabel(game: SportsTrendingGame): string {
		return game.away_rank ? `#${game.away_rank} ${game.away_team}` : game.away_team;
	}

	function homeLabel(game: SportsTrendingGame): string {
		return game.home_rank ? `#${game.home_rank} ${game.home_team}` : game.home_team;
	}

	// A team-link tap should open ESPN, not fall through to TileCard's button
	// and open the widget's own detail view — stop the click here so it
	// never bubbles up.
	function stopPropagation(event: Event) {
		event.stopPropagation();
	}
</script>

<TileCard {widgetId}>
	<div class="frame">
		<div class="title">{$_('sports.tile_title')}</div>
		{#if !summary}
			<div class="hint">{$_('sports.loading')}</div>
		{:else if !summary.configured && summary.trending.length === 0}
			<div class="hint">{$_('sports.not_configured')}</div>
		{:else}
			<div class="scroll-wrap">
				<div class="sections" use:scrollFade={summary}>
					{#if showToday}
						<div class="section">
							{#if visibleSections > 1}
								<div class="section-label">{$_('sports.today_title')}</div>
							{/if}
							<ul class="games">
								{#each summary.todays_games as game (game.league + game.team + game.id)}
									<li>
										<div class="matchup">
											<span class="league">{game.league_label}</span>
											<span class="teams">
												{#if game.team_espn_url}
													<a
														href={game.team_espn_url}
														target="_blank"
														rel="noopener noreferrer"
														onclick={stopPropagation}>{game.team}</a
													>
												{:else}
													{game.team}
												{/if}{' ' + (game.is_home ? $_('sports.vs') : '@') + ' ' + game.opponent}
											</span>
										</div>
										<div class="meta">
											<span class="when">
												{game.state === 'in'
													? $_('sports.live_status', { values: { status: game.status_detail } })
													: formatDate(game.date)}
											</span>
											{#if game.broadcast_links.length > 0}
												<span class="broadcast">
													{#each game.broadcast_links as link, i (link.name)}
														{#if i > 0}<span>, </span>{/if}
														{#if link.url}
															<a href={link.url} target="_blank" rel="noopener noreferrer">{link.name}</a>
														{:else}
															{link.name}
														{/if}
													{/each}
												</span>
											{/if}
										</div>
									</li>
								{/each}
							</ul>
						</div>
					{/if}
					{#if showTrending}
						<div class="section">
							{#if visibleSections > 1}
								<div class="section-label">{$_('sports.trending_title')}</div>
							{/if}
							<ul class="games">
								{#each summary.trending as game (game.league + game.id)}
									<li>
										<div class="matchup">
											<span class="league">{game.league_label}</span>
											<span class="teams">
												{#if game.away_espn_url}
													<a
														href={game.away_espn_url}
														target="_blank"
														rel="noopener noreferrer"
														onclick={stopPropagation}>{awayLabel(game)}</a
													>
												{:else}
													{awayLabel(game)}
												{/if} @ {#if game.home_espn_url}
													<a
														href={game.home_espn_url}
														target="_blank"
														rel="noopener noreferrer"
														onclick={stopPropagation}>{homeLabel(game)}</a
													>
												{:else}
													{homeLabel(game)}
												{/if}
											</span>
										</div>
										<div class="meta">
											<span class="when">
												{game.state === 'in'
													? $_('sports.live_status', { values: { status: game.status_detail } })
													: formatDate(game.date)}
											</span>
											{#if game.broadcast_links.length > 0}
												<span class="broadcast">
													{#each game.broadcast_links as link, i (link.name)}
														{#if i > 0}<span>, </span>{/if}
														{#if link.url}
															<a href={link.url} target="_blank" rel="noopener noreferrer">{link.name}</a>
														{:else}
															{link.name}
														{/if}
													{/each}
												</span>
											{/if}
										</div>
									</li>
								{/each}
							</ul>
						</div>
					{/if}
					{#if showUpcoming}
						<div class="section">
							{#if visibleSections > 1}
								<div class="section-label">{$_('sports.upcoming_title')}</div>
							{/if}
							{#if summary.upcoming_games.length === 0}
								<div class="hint">{$_('sports.no_upcoming')}</div>
							{:else}
								<ul class="games">
									{#each summary.upcoming_games as game (game.league + game.team + game.id)}
										<li>
											<div class="matchup">
												<span class="league">{game.league_label}</span>
												<span class="teams">
													{#if game.team_espn_url}
														<a
															href={game.team_espn_url}
															target="_blank"
															rel="noopener noreferrer"
															onclick={stopPropagation}>{game.team}</a
														>
													{:else}
														{game.team}
													{/if}{' ' + (game.is_home ? $_('sports.vs') : '@') + ' ' + game.opponent}
												</span>
											</div>
											<div class="meta">
												<span class="when">
													{game.state === 'in'
														? $_('sports.live_status', { values: { status: game.status_detail } })
														: formatDate(game.date)}
												</span>
												{#if game.broadcast_links.length > 0}
													<span class="broadcast">
														{#each game.broadcast_links as link, i (link.name)}
															{#if i > 0}<span>, </span>{/if}
															{#if link.url}
																<a href={link.url} target="_blank" rel="noopener noreferrer">{link.name}</a>
															{:else}
																{link.name}
															{/if}
														{/each}
													</span>
												{/if}
											</div>
										</li>
									{/each}
								</ul>
							{/if}
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

	.broadcast a {
		color: var(--color-accent);
	}

	.teams a {
		color: inherit;
		text-decoration: underline dotted;
	}
</style>
