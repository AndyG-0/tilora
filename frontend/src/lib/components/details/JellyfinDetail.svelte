<script lang="ts">
	import { page } from '$app/state';
	import { api, type JellyfinItem, type JellyfinTestConnectionResult } from '$lib/api';
	import JellyfinPlayer from '$lib/components/JellyfinPlayer.svelte';
	import { user } from '$lib/stores/user';

	interface JellyfinDetailData {
		connected: boolean;
		host: string;
		port: number;
		use_https: boolean;
		auth_mode: 'api_key' | 'password';
		username: string;
		library_ids: string[];
		has_api_key: boolean;
		has_password: boolean;
		playback_mode: 'compatible' | 'direct';
	}

	let { data: initialData }: { data: JellyfinDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let jellyfin = $state(initialData);

	let editing = $state(false);
	let hostInput = $state('');
	let portInput = $state(8096);
	let useHttpsInput = $state(false);
	let authModeInput = $state<'api_key' | 'password'>('api_key');
	let apiKeyInput = $state('');
	let usernameInput = $state('');
	let passwordInput = $state('');
	let playbackModeInput = $state<'compatible' | 'direct'>('compatible');
	let saving = $state(false);
	let error = $state<string | null>(null);
	let testing = $state(false);
	let testResult = $state<JellyfinTestConnectionResult | null>(null);

	let path = $state<{ id: string; name: string }[]>([]);
	let items = $state<JellyfinItem[]>([]);
	let itemsLoading = $state(false);
	let itemsError = $state<string | null>(null);
	let playingItem = $state<JellyfinItem | null>(null);

	const widgetId = $derived(page.params.id!);

	function openEditor() {
		hostInput = jellyfin.host;
		portInput = jellyfin.port;
		useHttpsInput = jellyfin.use_https;
		authModeInput = jellyfin.auth_mode;
		usernameInput = jellyfin.username;
		apiKeyInput = '';
		passwordInput = '';
		playbackModeInput = jellyfin.playback_mode;
		testResult = null;
		editing = true;
	}

	function currentFormSettings(): Record<string, unknown> {
		const settings: Record<string, unknown> = {
			host: hostInput,
			port: portInput,
			use_https: useHttpsInput,
			auth_mode: authModeInput,
			username: usernameInput,
			playback_mode: playbackModeInput,
		};
		if (apiKeyInput) settings.api_key = apiKeyInput;
		if (passwordInput) settings.password = passwordInput;
		return settings;
	}

	async function testConnection() {
		testing = true;
		testResult = null;
		try {
			testResult = await api.jellyfinTestConnection(widgetId, currentFormSettings());
		} catch {
			testResult = { ok: false, server_name: null, error: 'Could not reach the backend.' };
		} finally {
			testing = false;
		}
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, currentFormSettings());
			jellyfin = await api.widgetDetail<JellyfinDetailData>(widgetId);
			editing = false;
			path = [];
			await loadItems();
		} catch {
			error = 'Could not save the connection settings.';
		} finally {
			saving = false;
		}
	}

	async function clearSecret(key: 'api_key' | 'password') {
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, { [key]: '' });
			jellyfin = await api.widgetDetail<JellyfinDetailData>(widgetId);
		} catch {
			error = 'Could not clear the credential.';
		}
	}

	async function loadItems() {
		if (!jellyfin.connected) return;
		itemsLoading = true;
		itemsError = null;
		try {
			items = await api.jellyfinChildren(widgetId, path.at(-1)?.id);
		} catch {
			itemsError = 'Could not load library items.';
			items = [];
		} finally {
			itemsLoading = false;
		}
	}

	function openItem(item: JellyfinItem) {
		if (item.is_folder) {
			path = [...path, { id: item.id, name: item.name }];
			loadItems();
		} else {
			playingItem = item;
		}
	}

	function goToBreadcrumb(index: number) {
		path = path.slice(0, index + 1);
		loadItems();
	}

	function goToRoot() {
		path = [];
		loadItems();
	}

	$effect(() => {
		if (!editing) loadItems();
	});
</script>

<div class="header">
	<h1>Jellyfin</h1>
	{#if $user?.role === 'admin'}
		<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
			{editing ? 'Cancel' : 'Edit connection'}
		</button>
	{/if}
</div>

{#if editing}
	<div class="settings-form">
		<label>
			Host
			<input type="text" bind:value={hostInput} placeholder="jellyfin.local" />
		</label>
		<label>
			Port
			<input type="number" min="1" max="65535" bind:value={portInput} />
		</label>
		<label class="checkbox">
			<input type="checkbox" bind:checked={useHttpsInput} />
			Use HTTPS
		</label>

		<div class="auth-mode">
			<button type="button" class:active={authModeInput === 'api_key'} onclick={() => (authModeInput = 'api_key')}>
				API key
			</button>
			<button type="button" class:active={authModeInput === 'password'} onclick={() => (authModeInput = 'password')}>
				Username / password
			</button>
		</div>

		{#if authModeInput === 'api_key'}
			<label>
				API key
				<input
					type="password"
					bind:value={apiKeyInput}
					placeholder={jellyfin.has_api_key ? 'Set — enter a new value to replace it' : 'Not set'}
				/>
			</label>
			{#if jellyfin.has_api_key}
				<button class="clear" onclick={() => clearSecret('api_key')}>Clear key</button>
			{/if}
		{:else}
			<label>
				Username
				<input type="text" bind:value={usernameInput} />
			</label>
			<label>
				Password
				<input
					type="password"
					bind:value={passwordInput}
					placeholder={jellyfin.has_password ? 'Set — enter a new value to replace it' : 'Not set'}
				/>
			</label>
			{#if jellyfin.has_password}
				<button class="clear" onclick={() => clearSecret('password')}>Clear password</button>
			{/if}
		{/if}

		<div class="auth-mode">
			<button
				type="button"
				class:active={playbackModeInput === 'compatible'}
				onclick={() => (playbackModeInput = 'compatible')}
			>
				Compatible audio
			</button>
			<button
				type="button"
				class:active={playbackModeInput === 'direct'}
				onclick={() => (playbackModeInput = 'direct')}
			>
				Direct play
			</button>
		</div>
		<p class="hint">
			{#if playbackModeInput === 'compatible'}
				Jellyfin transcodes just the audio track to AAC so sound always works, even for files with surround/lossless
				audio the browser can't decode. Video is copied without re-encoding, so this stays cheap on the server.
			{:else}
				Streams the source file as-is — zero transcoding cost on the Jellyfin server, but playback may be silent for
				files whose audio codec your browser can't decode.
			{/if}
		</p>

		<div class="test-row">
			<button class="test" disabled={testing} onclick={testConnection}>
				{testing ? 'Testing…' : 'Test connection'}
			</button>
			{#if testResult}
				{#if testResult.ok}
					<span class="test-result ok">✓ Connected to {testResult.server_name}</span>
				{:else}
					<span class="test-result fail">✗ {testResult.error}</span>
				{/if}
			{/if}
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
	{#if !jellyfin.connected}
		<p class="hint">Not connected yet — tap "Edit connection" to set up Jellyfin.</p>
	{:else}
		<div class="breadcrumbs">
			<button class="crumb" onclick={goToRoot}>Libraries</button>
			{#each path as segment, index (segment.id)}
				<span class="sep">/</span>
				<button class="crumb" onclick={() => goToBreadcrumb(index)}>{segment.name}</button>
			{/each}
		</div>

		{#if itemsLoading}
			<p class="hint">Loading…</p>
		{:else if itemsError}
			<p class="hint error">{itemsError}</p>
		{:else if items.length === 0}
			<p class="hint">Nothing here.</p>
		{:else}
			<div class="grid">
				{#each items as item (item.id)}
					<button class="movie" onclick={() => openItem(item)}>
						{#if item.has_poster}
							<img class="poster" src={api.jellyfinImageUrl(widgetId, item.id)} alt={item.name} />
						{:else}
							<div class="poster placeholder"></div>
						{/if}
						<div class="info">
							<h2>{item.name}</h2>
							<p class="meta">
								{#if item.year}{item.year}{/if}
								{#if item.runtime_minutes}· {item.runtime_minutes} min{/if}
							</p>
							{#if item.overview}
								<p class="overview">{item.overview}</p>
							{/if}
						</div>
					</button>
				{/each}
			</div>
		{/if}
	{/if}
{/if}

{#if playingItem}
	<JellyfinPlayer
		src={api.jellyfinStreamUrl(widgetId, playingItem.id)}
		title={playingItem.name}
		onClose={() => (playingItem = null)}
	/>
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

	.settings-form label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.settings-form label.checkbox {
		flex-direction: row;
		align-items: center;
		gap: 0.5rem;
	}

	.settings-form input[type='text'],
	.settings-form input[type='number'],
	.settings-form input[type='password'] {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.auth-mode {
		display: flex;
		gap: 0.5rem;
	}

	.auth-mode button {
		flex: 1;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.auth-mode button.active {
		border-color: var(--color-accent);
		color: var(--color-accent);
	}

	.clear {
		align-self: flex-start;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.3rem 0.6rem;
		font-size: 0.85rem;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.test-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.test {
		align-self: flex-start;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.test-result {
		font-size: 0.85rem;
	}

	.test-result.ok {
		color: var(--color-success);
	}

	.test-result.fail {
		color: var(--color-error);
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

	.breadcrumbs {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin: 1rem 0;
	}

	.crumb {
		background: none;
		border: none;
		color: var(--color-accent);
		cursor: pointer;
		padding: 0.15rem 0.25rem;
		font: inherit;
	}

	.sep {
		color: var(--color-text-muted);
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
		gap: 1rem;
	}

	.movie {
		display: flex;
		gap: 1rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1rem;
		text-align: left;
		color: inherit;
		cursor: pointer;
	}

	.movie:active {
		background: var(--color-surface-hover);
	}

	.poster {
		width: 6rem;
		height: 9rem;
		object-fit: cover;
		border-radius: 0.5rem;
		flex-shrink: 0;
	}

	.poster.placeholder {
		background: var(--color-border);
	}

	.info {
		min-width: 0;
	}

	.info h2 {
		margin: 0 0 0.25rem;
		font-size: 1.1rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.meta {
		color: var(--color-text-muted);
		margin: 0 0 0.5rem;
	}

	.overview {
		margin: 0;
		overflow: hidden;
		display: -webkit-box;
		-webkit-line-clamp: 3;
		-webkit-box-orient: vertical;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
