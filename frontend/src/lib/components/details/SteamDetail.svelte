<script lang="ts">
	import { page } from '$app/state';
	import { api, type SteamDetail } from '$lib/api';

	let { data: initialData }: { data: SteamDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let steam = $state(initialData);

	let editing = $state(false);
	let steamidInput = $state('');
	let apiKeyInput = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);

	const widgetId = $derived(page.params.id!);

	function openEditor() {
		steamidInput = steam.steamid;
		// Never pre-fill the real key — it's write-only. An empty field on
		// save means "leave the stored key unchanged".
		apiKeyInput = '';
		editing = true;
	}

	function currentFormSettings(): Record<string, unknown> {
		const settings: Record<string, unknown> = { steamid: steamidInput };
		if (apiKeyInput) settings.api_key = apiKeyInput;
		return settings;
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, currentFormSettings());
			steam = await api.widgetDetail<SteamDetail>(widgetId);
			editing = false;
		} catch {
			error = 'Could not save the Steam settings.';
		} finally {
			saving = false;
		}
	}

	function formatPlaytime(minutes: number): string {
		const hours = minutes / 60;
		return hours >= 1 ? `${hours.toFixed(1)} hrs` : `${minutes} min`;
	}
</script>

<div class="header">
	<h1>Steam</h1>
	<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
		{editing ? 'Cancel' : 'Edit settings'}
	</button>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			SteamID64
			<input type="text" bind:value={steamidInput} placeholder="76561197960435530" />
		</label>
		<label>
			API key
			<input
				type="password"
				bind:value={apiKeyInput}
				placeholder={steam.has_api_key ? 'Set — enter a new value to replace it' : 'Not set'}
			/>
		</label>
		<p class="hint">
			Get a free API key from
			<a href="https://steamcommunity.com/dev/apikey" target="_blank" rel="noreferrer">steamcommunity.com/dev/apikey</a
			>. Friends' status requires the profile's "Game details" privacy set to Public.
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
	{#if !steam.configured}
		<p class="hint">Not configured yet — tap "Edit settings" to add a Steam API key and SteamID64.</p>
	{:else}
		{#if steam.error}
			<p class="hint error">{steam.error}</p>
		{/if}

		{#if steam.player}
			<div class="player-card">
				{#if steam.player.avatar}
					<img class="avatar" src={steam.player.avatar} alt="" />
				{/if}
				<div>
					<div class="player-name">
						<span class="dot" class:on={steam.player.online}></span>
						{steam.player.name}
					</div>
					<div class="player-status">
						{#if steam.current_game}
							Playing <span class="game">{steam.current_game}</span>
						{:else}
							{steam.player.status}
						{/if}
					</div>
				</div>
			</div>
		{/if}

		<h2>Recently played</h2>
		{#if steam.recent_games.length === 0}
			<p class="hint">No recently played games.</p>
		{:else}
			<ul class="games">
				{#each steam.recent_games as game (game.appid)}
					<li>
						{#if game.icon_url}
							<img class="icon" src={game.icon_url} alt="" />
						{/if}
						<span class="game-name">{game.name}</span>
						<span class="playtime">{formatPlaytime(game.playtime_2weeks_minutes)} / 2 wks</span>
						<span class="playtime total">{formatPlaytime(game.playtime_forever_minutes)} total</span>
					</li>
				{/each}
			</ul>
		{/if}

		<h2>Friends</h2>
		{#if steam.friends.length === 0}
			<p class="hint">No friends data available.</p>
		{:else}
			<ul class="friends">
				{#each steam.friends as friend (friend.steamid)}
					<li>
						{#if friend.avatar}
							<img class="icon" src={friend.avatar} alt="" />
						{/if}
						<span class="dot" class:on={friend.online}></span>
						<span class="friend-name">{friend.name}</span>
						<span class="friend-status">{friend.current_game ?? friend.status}</span>
					</li>
				{/each}
			</ul>
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
	.settings-form input[type='password'] {
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

	.player-card {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.75rem 1rem;
		margin: 1rem 0;
	}

	.avatar {
		width: 3rem;
		height: 3rem;
		border-radius: 0.5rem;
		flex-shrink: 0;
	}

	.player-name {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 600;
	}

	.player-status {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.game {
		color: var(--color-text);
		font-weight: 600;
	}

	.dot {
		width: 0.6rem;
		height: 0.6rem;
		border-radius: 50%;
		background: var(--color-text-muted);
		flex-shrink: 0;
	}

	.dot.on {
		background: var(--color-success);
	}

	.games,
	.friends {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.games li,
	.friends li {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
	}

	.icon {
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 0.25rem;
		flex-shrink: 0;
	}

	.game-name,
	.friend-name {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.friend-name {
		flex: 1;
	}

	.playtime {
		margin-left: auto;
		color: var(--color-text-muted);
		font-size: 0.85rem;
		flex-shrink: 0;
	}

	.playtime.total {
		margin-left: 0.5rem;
	}

	.friend-status {
		color: var(--color-text-muted);
		font-size: 0.85rem;
		flex-shrink: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
