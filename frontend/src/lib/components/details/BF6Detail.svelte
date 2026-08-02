<script lang="ts">
	import { page } from '$app/state';
	import { api, type BF6Detail } from '$lib/api';

	let { data: initialData }: { data: BF6Detail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let bf6 = $state(initialData);

	let editing = $state(false);
	let serverNameInput = $state('');
	let playerNameInput = $state('');
	let platformInput = $state('pc');
	let saving = $state(false);
	let error = $state<string | null>(null);

	const widgetId = $derived(page.params.id!);

	// Matches gametools.network's SantiagoPlatforms enum for /bf6/stats/.
	const PLATFORMS = ['pc', 'steam', 'ea', 'epic', 'xbox', 'xboxone', 'xboxseries', 'psn', 'ps4', 'ps5'];

	function openEditor() {
		serverNameInput = bf6.server_name;
		playerNameInput = bf6.player_name;
		platformInput = bf6.platform || 'pc';
		editing = true;
	}

	function currentFormSettings(): Record<string, unknown> {
		return {
			server_name: serverNameInput,
			player_name: playerNameInput,
			platform: platformInput,
		};
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, currentFormSettings());
			bf6 = await api.widgetDetail<BF6Detail>(widgetId);
			editing = false;
		} catch {
			error = 'Could not save the Battlefield 6 settings.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>Battlefield 6</h1>
	<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
		{editing ? 'Cancel' : 'Edit settings'}
	</button>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			Server name
			<input type="text" bind:value={serverNameInput} placeholder="e.g. Tsuru Reef" />
		</label>
		<label>
			Player name
			<input type="text" bind:value={playerNameInput} placeholder="e.g. LevelCap" />
		</label>
		<label>
			Player platform
			<select bind:value={platformInput}>
				{#each PLATFORMS as platform (platform)}
					<option value={platform}>{platform}</option>
				{/each}
			</select>
		</label>
		<p class="hint">
			Server name is matched with a fuzzy substring search against live servers — no exact match needed. Player platform
			must match the platform the player's stats are actually tracked under, or the lookup will report "player not
			found". Both fields are optional and independent — track just a server, just a player, or both. Powered by the
			free, unofficial
			<a href="https://gametools.network" target="_blank" rel="noreferrer">gametools.network</a> API.
		</p>

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
	{#if !bf6.configured}
		<p class="hint">Not configured yet — tap "Edit settings" to add a server name and/or player name to track.</p>
	{:else}
		{#if bf6.error}
			<p class="hint error">{bf6.error}</p>
		{/if}

		{#if bf6.server}
			<h2>Server</h2>
			<div class="server-card">
				<div class="server-name">{bf6.server.name}</div>
				<div class="server-stats">
					<span class="pop">{bf6.server.player_count}/{bf6.server.max_players} players</span>
					<span class="map">{bf6.server.mode} on {bf6.server.map}</span>
					<span class="region">{bf6.server.region}</span>
				</div>
			</div>
		{:else if bf6.server_name}
			<h2>Server</h2>
			<p class="hint">No server data available.</p>
		{/if}

		{#if bf6.player}
			<h2>Player</h2>
			<div class="player-card">
				{#if bf6.player.avatar}
					<img class="avatar" src={bf6.player.avatar} alt="" />
				{/if}
				<div class="player-name">{bf6.player.user_name}</div>
			</div>
			<ul class="stats-grid">
				<li><span class="stat-label">Kills</span><span class="stat-value">{bf6.player.kills}</span></li>
				<li><span class="stat-label">Deaths</span><span class="stat-value">{bf6.player.deaths}</span></li>
				<li>
					<span class="stat-label">K/D</span><span class="stat-value">{bf6.player.kill_death.toFixed(2)}</span>
				</li>
				<li><span class="stat-label">Wins</span><span class="stat-value">{bf6.player.wins}</span></li>
				<li><span class="stat-label">Losses</span><span class="stat-value">{bf6.player.loses}</span></li>
				{#if bf6.player.win_percent}
					<li>
						<span class="stat-label">Win %</span><span class="stat-value">{bf6.player.win_percent}</span>
					</li>
				{/if}
				{#if bf6.player.accuracy}
					<li>
						<span class="stat-label">Accuracy</span><span class="stat-value">{bf6.player.accuracy}</span>
					</li>
				{/if}
				{#if bf6.player.headshots}
					<li>
						<span class="stat-label">Headshots</span><span class="stat-value">{bf6.player.headshots}</span>
					</li>
				{/if}
				<li><span class="stat-label">Score</span><span class="stat-value">{bf6.player.score}</span></li>
				<li>
					<span class="stat-label">Matches</span><span class="stat-value">{bf6.player.matches_played}</span>
				</li>
				{#if bf6.player.time_played}
					<li>
						<span class="stat-label">Time played</span><span class="stat-value">{bf6.player.time_played}</span>
					</li>
				{/if}
			</ul>
		{:else if bf6.player_name}
			<h2>Player</h2>
			<p class="hint">No player stats available.</p>
		{/if}
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

	h2 {
		font-size: 1rem;
		margin: 1.5rem 0 0.5rem;
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

	.settings-form label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.settings-form input[type='text'],
	.settings-form select {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.settings-form a {
		color: var(--color-accent);
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

	.server-card {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.75rem 1rem;
		margin: 1rem 0;
	}

	.server-name {
		font-weight: 600;
	}

	.server-stats {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin-top: 0.35rem;
	}

	.player-card {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.75rem 1rem;
		margin: 1rem 0 0.75rem;
	}

	.avatar {
		width: 3rem;
		height: 3rem;
		border-radius: 0.5rem;
		flex-shrink: 0;
	}

	.player-name {
		font-weight: 600;
	}

	.stats-grid {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(8rem, 1fr));
		gap: 0.5rem;
	}

	.stats-grid li {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
	}

	.stat-label {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.stat-value {
		font-weight: 600;
	}
</style>
