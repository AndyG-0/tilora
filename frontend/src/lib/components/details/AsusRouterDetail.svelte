<script lang="ts">
	import { page } from '$app/state';
	import { api, type AsusRouterDetail, type AsusRouterTestConnectionResult } from '$lib/api';
	import { user } from '$lib/stores/user';

	let { data: initialData }: { data: AsusRouterDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let router = $state(initialData);

	let editing = $state(false);
	let hostInput = $state('');
	let portInput = $state(443);
	let useHttpsInput = $state(true);
	let usernameInput = $state('');
	let passwordInput = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);
	let testing = $state(false);
	let testResult = $state<AsusRouterTestConnectionResult | null>(null);

	const widgetId = $derived(page.params.id!);

	function openEditor() {
		hostInput = router.host;
		portInput = router.port;
		useHttpsInput = router.use_https;
		usernameInput = router.username;
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
			testResult = await api.asusRouterTestConnection(widgetId, currentFormSettings());
		} catch {
			testResult = { ok: false, product_id: null, error: 'Could not reach the backend.' };
		} finally {
			testing = false;
		}
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, currentFormSettings());
			router = await api.widgetDetail<AsusRouterDetail>(widgetId);
			editing = false;
		} catch {
			error = 'Could not save the connection settings.';
		} finally {
			saving = false;
		}
	}

	function formatBytes(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		const units = ['KB', 'MB', 'GB', 'TB'];
		let value = bytes / 1024;
		let unitIndex = 0;
		while (value >= 1024 && unitIndex < units.length - 1) {
			value /= 1024;
			unitIndex++;
		}
		return `${value.toFixed(1)} ${units[unitIndex]}`;
	}
</script>

<div class="header">
	<h1>Asus Router</h1>
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
			<input type="text" bind:value={hostInput} placeholder="router.asus.com" />
		</label>
		<label>
			Port
			<input type="number" min="1" max="65535" bind:value={portInput} />
		</label>
		<label class="checkbox">
			<input type="checkbox" bind:checked={useHttpsInput} />
			Use HTTPS
		</label>
		<label>
			Username
			<input type="text" bind:value={usernameInput} placeholder="admin" />
		</label>
		<label>
			Password
			<input
				type="password"
				bind:value={passwordInput}
				placeholder={router.has_password ? 'Set — enter a new value to replace it' : 'Not set'}
			/>
		</label>

		<div class="test-row">
			<button class="test" disabled={testing} onclick={testConnection}>
				{testing ? 'Testing…' : 'Test connection'}
			</button>
			{#if testResult}
				{#if testResult.ok}
					<span class="test-result ok">✓ Connected ({testResult.product_id})</span>
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
	{#if !router.connected}
		<p class="hint">Not connected yet — tap "Edit connection" to set up your router.</p>
	{:else}
		{#if router.error}
			<p class="hint error">{router.error}</p>
		{/if}

		<div class="system-info">
			<div class="stat">
				<div class="stat-value">{router.wan_connected ? 'Connected' : 'Down'}</div>
				<div class="stat-label">WAN status</div>
			</div>
			<div class="stat">
				<div class="stat-value">{router.wan_ip ?? 'Unknown'}</div>
				<div class="stat-label">WAN IP</div>
			</div>
			<div class="stat">
				<div class="stat-value">{formatBytes(router.rx_bytes)}</div>
				<div class="stat-label">Download</div>
			</div>
			<div class="stat">
				<div class="stat-value">{formatBytes(router.tx_bytes)}</div>
				<div class="stat-label">Upload</div>
			</div>
		</div>

		{#if router.clients.length === 0}
			<p class="hint">No connected clients found.</p>
		{:else}
			<ul class="clients">
				{#each router.clients as client (client.name + client.ip)}
					<li>
						<span class="dot" class:offline={!client.online}></span>
						<span class="name">{client.name}</span>
						<span class="ip">{client.ip}</span>
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

	.system-info {
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
		font-size: 1.25rem;
		font-weight: 600;
	}

	.stat-label {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.clients {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.clients li {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
	}

	.name {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.ip {
		margin-left: auto;
		color: var(--color-text-muted);
		font-size: 0.85rem;
		flex-shrink: 0;
	}

	.dot {
		width: 0.6rem;
		height: 0.6rem;
		border-radius: 50%;
		background: var(--color-success);
		flex-shrink: 0;
	}

	.dot.offline {
		background: var(--color-text-muted);
	}
</style>
