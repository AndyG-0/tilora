<script lang="ts">
	import { page } from '$app/state';
	import { api, type SteamDetail } from '$lib/api';
	import { _, locale } from 'svelte-i18n';
	import { get } from 'svelte/store';

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
			error = get(_)('steam.detail.save_error');
		} finally {
			saving = false;
		}
	}

	function formatPlaytime(minutes: number): string {
		const hours = minutes / 60;
		const time =
			hours >= 1
				? get(_)('steam.detail.hours_value', { values: { hours: hours.toFixed(1) } })
				: get(_)('steam.detail.minutes_value', { values: { minutes } });
		return time;
	}

	function formatNewsDate(unixSeconds: number): string {
		return new Date(unixSeconds * 1000).toLocaleString(get(locale) ?? undefined, {
			month: 'short',
			day: 'numeric',
			hour: 'numeric',
			minute: '2-digit',
		});
	}
</script>

<div class="header">
	<h1>Steam</h1>
	<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
		{editing ? $_('common.cancel') : $_('common.edit_settings')}
	</button>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			{$_('steam.detail.steamid_label')}
			<input type="text" bind:value={steamidInput} placeholder="76561197960435530" />
		</label>
		<label>
			{$_('steam.detail.api_key_label')}
			<input
				type="password"
				bind:value={apiKeyInput}
				placeholder={steam.has_api_key ? $_('common.password_set_hint') : $_('common.password_not_set')}
			/>
		</label>
		<p class="hint">
			{$_('steam.detail.api_key_hint_prefix')}
			<a href="https://steamcommunity.com/dev/apikey" target="_blank" rel="noreferrer">steamcommunity.com/dev/apikey</a
			>. {$_('steam.detail.api_key_hint_suffix')}
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
	{#if !steam.configured}
		<p class="hint">{$_('steam.detail.not_configured_hint')}</p>
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
							{$_('steam.tile.playing_prefix')} <span class="game">{steam.current_game}</span>
						{:else}
							{steam.player.status}
						{/if}
					</div>
				</div>
			</div>
		{/if}

		<h2>{$_('steam.detail.recently_played')}</h2>
		{#if steam.recent_games.length === 0}
			<p class="hint">{$_('steam.detail.no_recent_games')}</p>
		{:else}
			<ul class="games">
				{#each steam.recent_games as game (game.appid)}
					<li>
						{#if game.icon_url}
							<img class="icon" src={game.icon_url} alt="" />
						{/if}
						<span class="game-name">{game.name}</span>
						<span class="playtime">
							{$_('steam.detail.playtime_2weeks', { values: { time: formatPlaytime(game.playtime_2weeks_minutes) } })}
						</span>
						<span class="playtime total">
							{$_('steam.detail.playtime_total', { values: { time: formatPlaytime(game.playtime_forever_minutes) } })}
						</span>
					</li>
				{/each}
			</ul>
		{/if}

		<h2>{$_('steam.detail.friends')}</h2>
		{#if steam.friends.length === 0}
			<p class="hint">{$_('steam.detail.no_friends_data')}</p>
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

		<h2>{$_('steam.detail.news')}</h2>
		{#if steam.news.length === 0}
			<p class="hint">{$_('steam.detail.no_news')}</p>
		{:else}
			<ul class="news">
				{#each steam.news as item (item.gid)}
					<li>
						<div class="news-header">
							<span class="news-game">{item.game_name}</span>
							<span class="news-date">{formatNewsDate(item.date)}</span>
						</div>
						<a class="news-title" href={item.url} target="_blank" rel="noreferrer">{item.title}</a>
						{#if item.contents}
							<p class="news-contents">{item.contents}</p>
						{/if}
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

	.news {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.news li {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.6rem 0.75rem;
	}

	.news-header {
		display: flex;
		justify-content: space-between;
		gap: 0.6rem;
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}

	.news-title {
		display: block;
		font-weight: 600;
		color: var(--color-accent);
		margin-top: 0.2rem;
	}

	.news-contents {
		margin: 0.3rem 0 0;
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}
</style>
