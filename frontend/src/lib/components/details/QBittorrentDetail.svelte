<script lang="ts">
	import { page } from '$app/state';
	import { api, type QBittorrentDetail, type QBittorrentTestConnectionResult } from '$lib/api';
	import { user } from '$lib/stores/user';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	let { data: initialData }: { data: QBittorrentDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let qbittorrent = $state(initialData);

	let editing = $state(false);
	let hostInput = $state('');
	let portInput = $state(8080);
	let useHttpsInput = $state(false);
	let usernameInput = $state('');
	let passwordInput = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);
	let testing = $state(false);
	let testResult = $state<QBittorrentTestConnectionResult | null>(null);

	const widgetId = $derived(page.params.id!);

	function openEditor() {
		hostInput = qbittorrent.host;
		portInput = qbittorrent.port;
		useHttpsInput = qbittorrent.use_https;
		usernameInput = qbittorrent.username;
		passwordInput = '';
		testResult = null;
		editing = true;
	}

	function currentFormSettings(): Record<string, unknown> {
		const settings: Record<string, unknown> = {
			host: hostInput,
			port: portInput,
			use_https: useHttpsInput,
			username: usernameInput,
		};
		if (passwordInput) settings.password = passwordInput;
		return settings;
	}

	async function testConnection() {
		testing = true;
		testResult = null;
		try {
			testResult = await api.qbittorrentTestConnection(widgetId, currentFormSettings());
		} catch {
			testResult = { ok: false, version: null, error: get(_)('common.backend_unreachable') };
		} finally {
			testing = false;
		}
	}

	async function refetch() {
		qbittorrent = await api.widgetDetail<QBittorrentDetail>(widgetId);
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, currentFormSettings());
			await refetch();
			editing = false;
		} catch {
			error = get(_)('common.connection_save_error');
		} finally {
			saving = false;
		}
	}

	async function clearPassword() {
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, { password: '' });
			await refetch();
		} catch {
			error = get(_)('qbittorrent.detail.clear_password_error');
		}
	}

	function formatSpeed(bps: number): string {
		const mbps = (bps * 8) / 1_000_000;
		return `${mbps.toFixed(1)} Mbps`;
	}

	function formatSize(bytes: number): string {
		const gb = bytes / 1_000_000_000;
		return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / 1_000_000).toFixed(0)} MB`;
	}

	function formatEta(seconds: number | null): string {
		if (seconds === null || seconds < 0 || seconds >= 8640000) return '∞';
		const hours = Math.floor(seconds / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
	}
</script>

<div class="header">
	<h1>qBittorrent</h1>
	{#if $user?.role === 'admin'}
		<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
			{editing ? $_('common.cancel') : $_('common.edit_connection')}
		</button>
	{/if}
</div>

{#if editing}
	<div class="settings-form">
		<label>
			{$_('qbittorrent.detail.host_label')}
			<input type="text" bind:value={hostInput} placeholder="192.168.1.10" />
		</label>
		<label>
			{$_('qbittorrent.detail.port_label')}
			<input type="number" min="1" max="65535" bind:value={portInput} />
		</label>
		<label class="checkbox">
			<input type="checkbox" bind:checked={useHttpsInput} />
			{$_('qbittorrent.detail.use_https_label')}
		</label>
		<label>
			{$_('qbittorrent.detail.username_label')}
			<input type="text" bind:value={usernameInput} placeholder="admin" />
		</label>
		<label>
			{$_('qbittorrent.detail.password_label')}
			<input
				type="password"
				bind:value={passwordInput}
				placeholder={qbittorrent.has_password ? $_('common.password_set_hint') : $_('common.password_not_set')}
			/>
		</label>
		{#if qbittorrent.has_password}
			<button class="clear" onclick={clearPassword}>{$_('qbittorrent.detail.clear_password')}</button>
		{/if}

		<div class="test-row">
			<button class="test" disabled={testing} onclick={testConnection}>
				{testing ? $_('common.testing') : $_('common.test_connection')}
			</button>
			{#if testResult}
				{#if testResult.ok}
					<span class="test-result ok">
						✓ {$_('qbittorrent.detail.test_ok', { values: { version: testResult.version } })}
					</span>
				{:else}
					<span class="test-result fail">✗ {testResult.error}</span>
				{/if}
			{/if}
		</div>

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
	{#if !qbittorrent.connected}
		<p class="hint">{$_('qbittorrent.detail.not_connected_hint')}</p>
	{:else}
		{#if qbittorrent.error}
			<p class="hint error">{qbittorrent.error}</p>
		{/if}

		<div class="stats">
			<div class="stat">
				<div class="stat-value">{qbittorrent.torrent_count ?? 0}</div>
				<div class="stat-label">{$_('qbittorrent.detail.stat_torrents')}</div>
			</div>
			<div class="stat">
				<div class="stat-value">{qbittorrent.downloading_count ?? 0}</div>
				<div class="stat-label">{$_('qbittorrent.detail.stat_downloading')}</div>
			</div>
			<div class="stat">
				<div class="stat-value">{qbittorrent.seeding_count ?? 0}</div>
				<div class="stat-label">{$_('qbittorrent.detail.stat_seeding')}</div>
			</div>
			<div class="stat">
				<div class="stat-value">{formatSpeed(qbittorrent.download_speed_bps ?? 0)}</div>
				<div class="stat-label">{$_('qbittorrent.detail.stat_download_speed')}</div>
			</div>
			<div class="stat">
				<div class="stat-value">{formatSpeed(qbittorrent.upload_speed_bps ?? 0)}</div>
				<div class="stat-label">{$_('qbittorrent.detail.stat_upload_speed')}</div>
			</div>
		</div>

		<h2>{$_('qbittorrent.detail.torrents_heading')}</h2>
		{#if qbittorrent.torrents.length === 0}
			<p class="hint">{$_('qbittorrent.detail.no_torrents')}</p>
		{:else}
			<ul class="torrents">
				{#each qbittorrent.torrents as torrent (torrent.hash)}
					<li class="torrent">
						<div class="torrent-row">
							<span class="torrent-name">{torrent.name}</span>
							<span class="torrent-state">{torrent.state}</span>
						</div>
						<div class="progress-bar">
							<div class="progress-fill" style:width="{Math.round(torrent.progress * 100)}%"></div>
						</div>
						<div class="torrent-row">
							<span class="torrent-meta">
								{$_('qbittorrent.detail.progress_of_size', {
									values: { percent: Math.round(torrent.progress * 100), size: formatSize(torrent.size_bytes) },
								})}
							</span>
							<span class="torrent-meta">
								{$_('qbittorrent.detail.torrent_speed_eta', {
									values: {
										download: formatSpeed(torrent.download_speed_bps),
										upload: formatSpeed(torrent.upload_speed_bps),
										eta: formatEta(torrent.eta_seconds),
									},
								})}
							</span>
						</div>
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

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
		gap: 1rem;
		margin: 1rem 0;
	}

	.stat {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.75rem 1rem;
	}

	.stat-value {
		font-size: 1.5rem;
		font-weight: 600;
	}

	.stat-label {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	h2 {
		font-size: 1rem;
		margin: 1.5rem 0 0.5rem;
	}

	.torrents {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.torrent {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.6rem 0.75rem;
	}

	.torrent-row {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		font-size: 0.85rem;
	}

	.torrent-name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: 600;
	}

	.torrent-state {
		color: var(--color-text-muted);
		flex-shrink: 0;
	}

	.torrent-meta {
		color: var(--color-text-muted);
	}

	.progress-bar {
		height: 0.4rem;
		border-radius: 0.2rem;
		background: var(--color-border);
		margin: 0.35rem 0;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: var(--color-accent);
	}
</style>
