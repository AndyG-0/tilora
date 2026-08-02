<script lang="ts">
	import { page } from '$app/state';
	import { api, type SportsDetail, type SportsTeamEntry, type SportsTeamOption } from '$lib/api';

	const LEAGUE_OPTIONS: { value: string; label: string }[] = [
		{ value: 'nfl', label: 'NFL' },
		{ value: 'nba', label: 'NBA' },
		{ value: 'mlb', label: 'MLB' },
		{ value: 'nhl', label: 'NHL' },
		{ value: 'college-football', label: 'College Football' },
		{ value: 'wnba', label: 'WNBA' },
		{ value: 'college-basketball-men', label: 'College Basketball (Men)' },
		{ value: 'college-basketball-women', label: 'College Basketball (Women)' },
	];

	let { data: initialData }: { data: SportsDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let sports = $state(initialData);

	let editing = $state(false);
	let teamInputs = $state<SportsTeamEntry[]>([]);
	let trendingLeagueInputs = $state<Set<string>>(new Set());
	let saving = $state(false);
	let error = $state<string | null>(null);

	let teamOptionsByLeague = $state<Record<string, SportsTeamOption[]>>({});
	let loadingLeagues = $state(new Set<string>());

	const widgetId = $derived(page.params.id!);

	async function ensureTeamOptions(league: string) {
		if (teamOptionsByLeague[league] || loadingLeagues.has(league)) return;
		loadingLeagues = new Set(loadingLeagues).add(league);
		try {
			// Mutate the key in place rather than spreading a new object —
			// several leagues load concurrently, and reassigning the whole
			// object from a stale read would drop sibling leagues' results.
			teamOptionsByLeague[league] = await api.sportsTeams(league);
		} catch {
			teamOptionsByLeague[league] = [];
		} finally {
			const next = new Set(loadingLeagues);
			next.delete(league);
			loadingLeagues = next;
		}
	}

	function openEditor() {
		teamInputs = sports.teams.map((team) => ({ league: team.league, team: team.team }));
		trendingLeagueInputs = new Set(sports.trending_leagues);
		editing = true;
		for (const league of new Set(teamInputs.map((team) => team.league))) {
			ensureTeamOptions(league);
		}
	}

	function toggleTrendingLeague(league: string) {
		const next = new Set(trendingLeagueInputs);
		if (next.has(league)) {
			next.delete(league);
		} else {
			next.add(league);
		}
		trendingLeagueInputs = next;
	}

	function addTeamRow() {
		teamInputs = [...teamInputs, { league: 'nfl', team: '' }];
		ensureTeamOptions('nfl');
	}

	function removeTeamRow(index: number) {
		teamInputs = teamInputs.filter((_, i) => i !== index);
	}

	function onLeagueChange(index: number, league: string) {
		teamInputs[index] = { league, team: '' };
		ensureTeamOptions(league);
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			const teams = teamInputs
				.map((team) => ({ league: team.league, team: team.team.trim().toUpperCase() }))
				.filter((team) => team.team.length > 0);
			const trending_leagues = [...trendingLeagueInputs];
			await api.updateWidgetSettings(widgetId, { teams, trending_leagues });
			sports = await api.widgetDetail<SportsDetail>(widgetId);
			editing = false;
		} catch {
			error = 'Could not update sports settings.';
		} finally {
			saving = false;
		}
	}

	function formatDate(iso: string | null): string {
		if (!iso) return '';
		return new Date(iso).toLocaleString(undefined, {
			weekday: 'short',
			month: 'short',
			day: 'numeric',
			hour: 'numeric',
			minute: '2-digit',
		});
	}
</script>

<div class="header">
	<h1>Sports Schedule</h1>
	<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
		{editing ? 'Cancel' : 'Edit settings'}
	</button>
</div>

{#if editing}
	<div class="settings-form">
		<div class="teams-editor">
			{#each teamInputs as team, index (index)}
				<div class="team-row">
					<select value={team.league} onchange={(e) => onLeagueChange(index, e.currentTarget.value)}>
						{#each LEAGUE_OPTIONS as option (option.value)}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
					<select bind:value={team.team} disabled={loadingLeagues.has(team.league)}>
						<option value="">{loadingLeagues.has(team.league) ? 'Loading teams…' : 'Select a team'}</option>
						{#each teamOptionsByLeague[team.league] ?? [] as option (option.abbreviation)}
							<option value={option.abbreviation}>{option.display_name}</option>
						{/each}
					</select>
					<button class="remove-team" onclick={() => removeTeamRow(index)} aria-label="Remove team"> ✕ </button>
				</div>
			{:else}
				<p class="hint">No teams yet — add one below.</p>
			{/each}
			<button class="add-team" onclick={addTeamRow}>+ Add team</button>
		</div>

		<div class="trending-editor">
			<h3>Track for trending</h3>
			<p class="hint">Leagues shown in "Top Games Today", regardless of followed teams.</p>
			<div class="trending-leagues">
				{#each LEAGUE_OPTIONS as option (option.value)}
					<label class="trending-league">
						<input
							type="checkbox"
							checked={trendingLeagueInputs.has(option.value)}
							onchange={() => toggleTrendingLeague(option.value)}
						/>
						{option.label}
					</label>
				{/each}
			</div>
		</div>

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={saveSettings}>
			{saving ? 'Saving…' : 'Save'}
		</button>
	</div>
{:else if error}
	<p class="hint error">{error}</p>
{/if}

{#if !editing}
	{#if !sports.configured || sports.teams.length === 0}
		<p class="hint">No teams configured yet — tap "Edit teams" to follow one.</p>
	{:else}
		<div class="teams">
			{#each sports.teams as team (team.league + team.team)}
				<div class="team-section">
					<h2>
						{team.team_name || team.team}
						<span class="league-badge">{team.league_label}</span>
					</h2>
					{#if team.error}
						<p class="hint error">{team.error}</p>
					{:else if team.games.length === 0}
						<p class="hint">No upcoming games scheduled.</p>
					{:else}
						<ul class="games">
							{#each team.games as game (game.id)}
								<li>
									<div class="matchup">
										<span class="teams-line">
											{game.is_home ? `vs ${game.opponent}` : `@ ${game.opponent}`}
										</span>
										{#if game.state !== 'pre'}
											<span class="score">
												{game.away_abbreviation}
												{game.away_score ?? '-'} · {game.home_abbreviation}
												{game.home_score ?? '-'}
											</span>
										{/if}
									</div>
									<div class="meta">
										<span class="when">
											{game.state === 'in' ? `Live — ${game.status_detail}` : formatDate(game.date)}
										</span>
										{#if game.venue}
											<span class="venue">{game.venue}</span>
										{/if}
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
			{/each}
		</div>
	{/if}

	{#if sports.trending.length > 0}
		<div class="trending">
			<h2>Top Games Today</h2>
			{#if sports.trending_errors && sports.trending_errors.length > 0}
				<p class="hint error">
					Couldn't load: {sports.trending_errors.map((e) => e.league).join(', ')}
				</p>
			{/if}
			<ul class="games">
				{#each sports.trending as game (game.league + game.id)}
					<li>
						<div class="matchup">
							<span class="teams-line">
								<span class="league-badge">{game.league_label}</span>
								{game.away_rank ? `#${game.away_rank} ` : ''}{game.away_team} @ {game.home_rank
									? `#${game.home_rank} `
									: ''}{game.home_team}
							</span>
							{#if game.state !== 'pre'}
								<span class="score">
									{game.away_abbreviation}
									{game.away_score ?? '-'} · {game.home_abbreviation}
									{game.home_score ?? '-'}
								</span>
							{/if}
						</div>
						<div class="meta">
							<span class="when">
								{game.state === 'in' ? `Live — ${game.status_detail}` : formatDate(game.date)}
							</span>
							{#if game.venue}
								<span class="venue">{game.venue}</span>
							{/if}
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
{/if}

<style>
	.header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
	}

	.header h1 {
		margin: 0;
	}

	.edit-settings {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.settings-form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		max-width: 30rem;
		margin: 1rem 0 1.5rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem;
	}

	.teams-editor {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.team-row {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.team-row select {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.team-row select:last-of-type {
		flex: 1;
		min-width: 0;
	}

	.remove-team {
		flex-shrink: 0;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		cursor: pointer;
	}

	.add-team {
		align-self: flex-start;
		background: none;
		border: 1px dashed var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.trending-editor h3 {
		font-size: 0.95rem;
		margin: 0 0 0.25rem;
	}

	.trending-editor .hint {
		margin: 0 0 0.5rem;
		font-size: 0.85rem;
	}

	.trending-leagues {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 0.4rem 1rem;
	}

	.trending-league {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.9rem;
	}

	.save {
		align-self: flex-start;
		background: var(--color-accent);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}

	.teams {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		margin-top: 1rem;
	}

	.team-section h2 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 1.1rem;
		margin: 0 0 0.5rem;
	}

	.league-badge {
		font-size: 0.7rem;
		font-weight: 400;
		color: var(--color-text-muted);
		border: 1px solid var(--color-border);
		border-radius: 0.3rem;
		padding: 0.1rem 0.4rem;
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
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.6rem 0.9rem;
	}

	.matchup {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.75rem;
		font-weight: 600;
	}

	.score {
		font-weight: 400;
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin-top: 0.2rem;
	}

	.broadcast a {
		color: var(--color-accent);
	}

	.trending {
		margin-top: 1.5rem;
	}

	.trending h2 {
		font-size: 1.1rem;
		margin: 0 0 0.5rem;
	}

	.teams-line {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
</style>
