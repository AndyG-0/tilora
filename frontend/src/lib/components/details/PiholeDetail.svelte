<script lang="ts">
	import { page } from '$app/state';
	import { api, type PiholeDetail, type PiholeTestConnectionResult } from '$lib/api';
	import { user } from '$lib/stores/user';

	let { data: initialData }: { data: PiholeDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings/setBlocking's refetch.
	let pihole = $state(initialData);

	let editing = $state(false);
	let hostInput = $state('');
	let portInput = $state(80);
	let useHttpsInput = $state(false);
	let passwordInput = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);
	let testing = $state(false);
	let testResult = $state<PiholeTestConnectionResult | null>(null);
	let blockingBusy = $state(false);

	const widgetId = $derived(page.params.id!);

	function openEditor() {
		hostInput = pihole.host;
		portInput = pihole.port;
		useHttpsInput = pihole.use_https;
		passwordInput = '';
		testResult = null;
		editing = true;
	}

	function currentFormSettings(): Record<string, unknown> {
		const settings: Record<string, unknown> = {
			host: hostInput,
			port: portInput,
			use_https: useHttpsInput,
		};
		if (passwordInput) settings.password = passwordInput;
		return settings;
	}

	async function testConnection() {
		testing = true;
		testResult = null;
		try {
			testResult = await api.piholeTestConnection(widgetId, currentFormSettings());
		} catch {
			testResult = { ok: false, version: null, error: 'Could not reach the backend.' };
		} finally {
			testing = false;
		}
	}

	async function refetch() {
		pihole = await api.widgetDetail<PiholeDetail>(widgetId);
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, currentFormSettings());
			await refetch();
			editing = false;
		} catch {
			error = 'Could not save the connection settings.';
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
			error = 'Could not clear the password.';
		}
	}

	async function setBlocking(enabled: boolean, timer: number | null = null) {
		blockingBusy = true;
		error = null;
		try {
			await api.piholeSetBlocking(widgetId, enabled, timer);
			await refetch();
		} catch {
			error = 'Could not change the blocking state.';
		} finally {
			blockingBusy = false;
		}
	}

	function formatTimestamp(unixSeconds: number | null): string {
		if (!unixSeconds) return 'unknown';
		return new Date(unixSeconds * 1000).toLocaleString();
	}
</script>

<div class="header">
	<h1>Pi-hole</h1>
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
			<input type="text" bind:value={hostInput} placeholder="pi.hole" />
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
			Password
			<input
				type="password"
				bind:value={passwordInput}
				placeholder={pihole.has_password ? 'Set — enter a new value to replace it' : 'Not set'}
			/>
		</label>
		{#if pihole.has_password}
			<button class="clear" onclick={clearPassword}>Clear password</button>
		{/if}

		<div class="test-row">
			<button class="test" disabled={testing} onclick={testConnection}>
				{testing ? 'Testing…' : 'Test connection'}
			</button>
			{#if testResult}
				{#if testResult.ok}
					<span class="test-result ok">✓ Connected (Pi-hole {testResult.version})</span>
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
	{#if !pihole.connected}
		<p class="hint">Not connected yet — tap "Edit connection" to set up Pi-hole.</p>
	{:else}
		{#if pihole.error}
			<p class="hint error">{pihole.error}</p>
		{/if}

		<div class="blocking-row">
			<span class="blocking-status" class:on={pihole.blocking_enabled} class:off={!pihole.blocking_enabled}>
				{pihole.blocking_enabled ? '● Blocking enabled' : '⏸ Blocking paused'}
			</span>
			<div class="blocking-actions">
				{#if pihole.blocking_enabled}
					<button disabled={blockingBusy} onclick={() => setBlocking(false, 30)}>Pause 30s</button>
					<button disabled={blockingBusy} onclick={() => setBlocking(false, 300)}>Pause 5m</button>
					<button disabled={blockingBusy} onclick={() => setBlocking(false)}>Disable</button>
				{:else}
					<button disabled={blockingBusy} onclick={() => setBlocking(true)}>Enable</button>
				{/if}
			</div>
		</div>

		<div class="stats">
			<div class="stat">
				<div class="stat-value">{(pihole.queries_today ?? 0).toLocaleString()}</div>
				<div class="stat-label">Queries today</div>
			</div>
			<div class="stat">
				<div class="stat-value">{(pihole.blocked_today ?? 0).toLocaleString()}</div>
				<div class="stat-label">Blocked today</div>
			</div>
			<div class="stat">
				<div class="stat-value">{Math.round(pihole.percent_blocked ?? 0)}%</div>
				<div class="stat-label">Percent blocked</div>
			</div>
			<div class="stat">
				<div class="stat-value">{pihole.unique_clients} / {pihole.clients_total}</div>
				<div class="stat-label">Active clients</div>
			</div>
			<div class="stat">
				<div class="stat-value">{pihole.domains_blocked.toLocaleString()}</div>
				<div class="stat-label">Domains on blocklist</div>
			</div>
		</div>
		<p class="hint">Blocklist last updated {formatTimestamp(pihole.gravity_last_update)}.</p>

		<div class="domain-lists">
			<div class="domain-list">
				<h2>Top blocked domains</h2>
				{#if pihole.top_blocked_domains.length === 0}
					<p class="hint">No data yet.</p>
				{:else}
					<ul>
						{#each pihole.top_blocked_domains as entry (entry.domain)}
							<li><span class="domain">{entry.domain}</span><span class="count">{entry.count}</span></li>
						{/each}
					</ul>
				{/if}
			</div>
			<div class="domain-list">
				<h2>Top permitted domains</h2>
				{#if pihole.top_permitted_domains.length === 0}
					<p class="hint">No data yet.</p>
				{:else}
					<ul>
						{#each pihole.top_permitted_domains as entry (entry.domain)}
							<li><span class="domain">{entry.domain}</span><span class="count">{entry.count}</span></li>
						{/each}
					</ul>
				{/if}
			</div>
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

	.blocking-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 0.75rem;
		margin: 1rem 0;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem;
	}

	.blocking-status {
		font-weight: 600;
	}

	.blocking-status.on {
		color: var(--color-success);
	}

	.blocking-status.off {
		color: var(--color-warning);
	}

	.blocking-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.blocking-actions button {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
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

	.domain-lists {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
		gap: 1.5rem;
		margin-top: 1.5rem;
	}

	.domain-list h2 {
		font-size: 1rem;
		margin: 0 0 0.5rem;
	}

	.domain-list ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.domain-list li {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
	}

	.domain {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.count {
		color: var(--color-text-muted);
		flex-shrink: 0;
	}
</style>
