<script lang="ts">
	import { page } from '$app/state';
	import { api, type BF6Detail } from '$lib/api';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

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
	let avatarFailed = $state(false);

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
			error = get(_)('bf6.detail.save_error');
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>Battlefield 6</h1>
	<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
		{editing ? $_('common.cancel') : $_('common.edit_settings')}
	</button>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			{$_('bf6.detail.server_name_label')}
			<input type="text" bind:value={serverNameInput} placeholder="e.g. Tsuru Reef" />
		</label>
		<label>
			{$_('bf6.detail.player_name_label')}
			<input type="text" bind:value={playerNameInput} placeholder="e.g. LevelCap" />
		</label>
		<label>
			{$_('bf6.detail.platform_label')}
			<select bind:value={platformInput}>
				{#each PLATFORMS as platform (platform)}
					<option value={platform}>{platform}</option>
				{/each}
			</select>
		</label>
		<p class="hint">
			{$_('bf6.detail.hint_prefix')}
			<a href="https://gametools.network" target="_blank" rel="noreferrer">gametools.network</a>
			{$_('bf6.detail.hint_suffix')}
		</p>

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={saveSettings}>
			{saving ? $_('common.saving') : $_('common.save')}
		</button>
	</div>
{:else if error}
	<p class="hint error">{error}</p>
{/if}

{#if !editing}
	{#if !bf6.configured}
		<p class="hint">{$_('bf6.detail.not_configured_hint')}</p>
	{:else}
		{#if bf6.error}
			<p class="hint error">{bf6.error}</p>
		{/if}

		{#if bf6.server}
			<h2>{$_('bf6.detail.server_heading')}</h2>
			<div class="server-card">
				<div class="server-name">{bf6.server.name}</div>
				<div class="server-stats">
					<span class="pop">
						{$_('bf6.detail.player_count', { values: { count: bf6.server.player_count, max: bf6.server.max_players } })}
					</span>
					<span class="map">
						{$_('bf6.tile.mode_on_map', { values: { mode: bf6.server.mode, map: bf6.server.map } })}
					</span>
					<span class="region">{bf6.server.region}</span>
				</div>
			</div>
		{:else if bf6.server_name}
			<h2>{$_('bf6.detail.server_heading')}</h2>
			<p class="hint">{$_('bf6.detail.no_server_data')}</p>
		{/if}

		{#if bf6.player}
			<h2>{$_('bf6.detail.player_heading')}</h2>
			<div class="player-card">
				{#if bf6.player.avatar && !avatarFailed}
					{#key bf6.player.avatar}
						<img class="avatar" src={bf6.player.avatar} alt="" onerror={() => (avatarFailed = true)} />
					{/key}
				{/if}
				<div class="player-name">{bf6.player.user_name}</div>
			</div>
			<ul class="stats-grid">
				<li>
					<span class="stat-label">{$_('bf6.detail.stat_kills')}</span><span class="stat-value">{bf6.player.kills}</span
					>
				</li>
				<li>
					<span class="stat-label">{$_('bf6.detail.stat_deaths')}</span><span class="stat-value"
						>{bf6.player.deaths}</span
					>
				</li>
				<li>
					<span class="stat-label">{$_('bf6.detail.stat_kd')}</span><span class="stat-value"
						>{bf6.player.kill_death.toFixed(2)}</span
					>
				</li>
				<li>
					<span class="stat-label">{$_('bf6.detail.stat_wins')}</span><span class="stat-value">{bf6.player.wins}</span>
				</li>
				<li>
					<span class="stat-label">{$_('bf6.detail.stat_losses')}</span><span class="stat-value"
						>{bf6.player.loses}</span
					>
				</li>
				{#if bf6.player.win_percent}
					<li>
						<span class="stat-label">{$_('bf6.detail.stat_win_percent')}</span><span class="stat-value"
							>{bf6.player.win_percent}</span
						>
					</li>
				{/if}
				{#if bf6.player.accuracy}
					<li>
						<span class="stat-label">{$_('bf6.detail.stat_accuracy')}</span><span class="stat-value"
							>{bf6.player.accuracy}</span
						>
					</li>
				{/if}
				{#if bf6.player.headshots}
					<li>
						<span class="stat-label">{$_('bf6.detail.stat_headshots')}</span><span class="stat-value"
							>{bf6.player.headshots}</span
						>
					</li>
				{/if}
				<li>
					<span class="stat-label">{$_('bf6.detail.stat_score')}</span><span class="stat-value">{bf6.player.score}</span
					>
				</li>
				<li>
					<span class="stat-label">{$_('bf6.detail.stat_matches')}</span><span class="stat-value"
						>{bf6.player.matches_played}</span
					>
				</li>
				{#if bf6.player.time_played}
					<li>
						<span class="stat-label">{$_('bf6.detail.stat_time_played')}</span><span class="stat-value"
							>{bf6.player.time_played}</span
						>
					</li>
				{/if}
			</ul>
		{:else if bf6.player_name}
			<h2>{$_('bf6.detail.player_heading')}</h2>
			<p class="hint">{$_('bf6.detail.no_player_stats')}</p>
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
