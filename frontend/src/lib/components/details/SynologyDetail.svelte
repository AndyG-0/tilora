<script lang="ts">
	import { page } from '$app/state';
	import { api, type SynologyDetail, type SynologyTestConnectionResult } from '$lib/api';

	let { data: initialData }: { data: SynologyDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let synology = $state(initialData);

	let editing = $state(false);
	let hostInput = $state('');
	let portInput = $state(5000);
	let useHttpsInput = $state(false);
	let usernameInput = $state('');
	let passwordInput = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);
	let testing = $state(false);
	let testResult = $state<SynologyTestConnectionResult | null>(null);

	const widgetId = $derived(page.params.id!);

	function openEditor() {
		hostInput = synology.host;
		portInput = synology.port;
		useHttpsInput = synology.use_https;
		usernameInput = synology.username;
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
			testResult = await api.synologyTestConnection(widgetId, currentFormSettings());
		} catch {
			testResult = { ok: false, model: null, error: 'Could not reach the backend.' };
		} finally {
			testing = false;
		}
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, currentFormSettings());
			synology = await api.widgetDetail<SynologyDetail>(widgetId);
			editing = false;
		} catch {
			error = 'Could not save the connection settings.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>Synology</h1>
	<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
		{editing ? 'Cancel' : 'Edit connection'}
	</button>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			Host
			<input type="text" bind:value={hostInput} placeholder="synology.local" />
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
				placeholder={synology.has_password ? 'Set — enter a new value to replace it' : 'Not set'}
			/>
		</label>

		<div class="test-row">
			<button class="test" disabled={testing} onclick={testConnection}>
				{testing ? 'Testing…' : 'Test connection'}
			</button>
			{#if testResult}
				{#if testResult.ok}
					<span class="test-result ok">✓ Connected ({testResult.model})</span>
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
	{#if !synology.connected}
		<p class="hint">Not connected yet — tap "Edit connection" to set up Synology.</p>
	{:else}
		{#if synology.error}
			<p class="hint error">{synology.error}</p>
		{/if}

		<div class="system-info">
			<div class="stat">
				<div class="stat-value">{synology.model ?? 'Unknown'}</div>
				<div class="stat-label">Model</div>
			</div>
			<div class="stat">
				<div class="stat-value">{synology.uptime ?? 'Unknown'}</div>
				<div class="stat-label">Uptime</div>
			</div>
			<div class="stat">
				<div class="stat-value">
					{synology.temperature_celsius != null ? `${synology.temperature_celsius}°C` : 'Unknown'}
				</div>
				<div class="stat-label">CPU temperature</div>
				{#if synology.temperature_celsius == null}
					<div class="stat-hint">DSM may be withholding this from a non-admin account</div>
				{/if}
			</div>
		</div>

		{#if synology.volumes.length === 0}
			<p class="hint">No volumes found.</p>
		{:else}
			<ul class="volumes">
				{#each synology.volumes as volume (volume.name)}
					<li>
						<span class="dot" class:warn={volume.status !== 'normal'}></span>
						<span class="name">{volume.name}</span>
						<span class="status">{volume.status}</span>
						<span class="percent">{volume.used_percent}%</span>
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

	.stat-hint {
		color: var(--color-text-muted);
		font-size: 0.7rem;
		margin-top: 0.2rem;
	}

	.volumes {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.volumes li {
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

	.status {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.percent {
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

	.dot.warn {
		background: var(--color-warning);
	}
</style>
