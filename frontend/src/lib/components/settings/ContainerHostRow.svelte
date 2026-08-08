<script lang="ts">
	import { api, type NetworkIntegration } from '$lib/api';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	const ENGINE_DEFAULTS: Record<'docker' | 'podman', { socketPath: string; host: string; port: number }> = {
		docker: { socketPath: '/var/run/docker.sock', host: 'docker.local', port: 2375 },
		podman: { socketPath: '/run/podman/podman.sock', host: 'podman.local', port: 8080 },
	};

	let {
		host,
		onUpdated,
		onDeleted,
	}: {
		host: NetworkIntegration;
		onUpdated: (updated: NetworkIntegration) => void;
		onDeleted: (id: string) => void;
	} = $props();

	let nameInput = $state(host.name);
	let engineInput = $state((host.settings.engine as 'docker' | 'podman') ?? 'docker');
	let connectionInput = $state(host.settings.connection === 'tcp' ? 'tcp' : 'socket');
	let socketPathInput = $state((host.settings.socket_path as string) ?? '');
	let hostInput = $state((host.settings.host as string) ?? '');
	let portInput = $state((host.settings.port as number) ?? 2375);

	let saving = $state(false);
	let error = $state<string | null>(null);
	let testing = $state(false);
	let testResult = $state<{ ok: boolean; detail: string | null; error: string | null } | null>(null);
	let confirmingDelete = $state(false);
	let deleting = $state(false);
	let deleteError = $state<string | null>(null);

	const enginePlaceholders = $derived(ENGINE_DEFAULTS[engineInput]);

	function onEngineChange(next: 'docker' | 'podman') {
		const previousDefaults = ENGINE_DEFAULTS[engineInput];
		const nextDefaults = ENGINE_DEFAULTS[next];
		if (socketPathInput === previousDefaults.socketPath) socketPathInput = nextDefaults.socketPath;
		if (portInput === previousDefaults.port) portInput = nextDefaults.port;
		engineInput = next;
	}

	function currentSettings(): Record<string, unknown> {
		return {
			engine: engineInput,
			connection: connectionInput,
			socket_path: socketPathInput,
			host: hostInput,
			port: portInput,
		};
	}

	async function testConnection() {
		testing = true;
		testResult = null;
		try {
			testResult = await api.testContainerIntegrationConnection(host.id, currentSettings());
		} catch {
			testResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			testing = false;
		}
	}

	async function save() {
		saving = true;
		error = null;
		try {
			const updated = await api.updateContainerIntegration(host.id, { name: nameInput, ...currentSettings() });
			onUpdated(updated);
		} catch {
			error = get(_)('network_settings.save_error');
		} finally {
			saving = false;
		}
	}

	async function deleteHost() {
		deleting = true;
		deleteError = null;
		try {
			await api.deleteContainerIntegration(host.id);
			onDeleted(host.id);
		} catch {
			deleteError = get(_)('network_settings.delete_host_error');
			confirmingDelete = false;
		} finally {
			deleting = false;
		}
	}
</script>

<div class="host-row">
	<label>
		{$_('network_settings.host_name_label')}
		<input type="text" bind:value={nameInput} />
	</label>
	<label>
		{$_('container.detail.engine_label')}
		<select value={engineInput} onchange={(e) => onEngineChange(e.currentTarget.value as 'docker' | 'podman')}>
			<option value="docker">Docker</option>
			<option value="podman">Podman</option>
		</select>
	</label>
	<label>
		{$_('container.detail.connection_label')}
		<select bind:value={connectionInput}>
			<option value="socket">{$_('container.detail.local_socket')}</option>
			<option value="tcp">{$_('container.detail.remote_tcp')}</option>
		</select>
	</label>
	{#if connectionInput === 'socket'}
		<label>
			{$_('container.detail.socket_path_label')}
			<input type="text" bind:value={socketPathInput} placeholder={enginePlaceholders.socketPath} />
		</label>
	{:else}
		<label>
			{$_('container.detail.host_label')}
			<input type="text" bind:value={hostInput} placeholder={enginePlaceholders.host} />
		</label>
		<label>
			{$_('container.detail.port_label')}
			<input type="number" min="1" max="65535" bind:value={portInput} />
		</label>
	{/if}

	<div class="test-row">
		<button class="test" disabled={testing} onclick={testConnection}>
			{testing ? $_('common.testing') : $_('common.test_connection')}
		</button>
		{#if testResult}
			{#if testResult.ok}
				<span class="test-result ok">{$_('network_settings.test_ok', { values: { detail: testResult.detail } })}</span>
			{:else}
				<span class="test-result fail">{$_('network_settings.test_fail', { values: { error: testResult.error } })}</span
				>
			{/if}
		{/if}
	</div>

	{#if error}
		<p class="hint error">{error}</p>
	{/if}
	{#if deleteError}
		<p class="hint error">{deleteError}</p>
	{/if}

	<div class="actions">
		<button class="save" disabled={saving} onclick={save}>
			{saving ? $_('common.saving') : $_('common.save')}
		</button>
		{#if confirmingDelete}
			<span class="confirm-actions">
				<button class="cancel" onclick={() => (confirmingDelete = false)} disabled={deleting}>
					{$_('network_settings.cancel_delete_host')}
				</button>
				<button class="danger" onclick={deleteHost} disabled={deleting}>
					{$_('network_settings.delete_host_button')}
				</button>
			</span>
		{:else}
			<button class="danger-link" onclick={() => (confirmingDelete = true)}>
				{$_('network_settings.delete_host_button')}
			</button>
		{/if}
	</div>
</div>

<style>
	.host-row {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem;
	}

	.host-row label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.host-row input[type='text'],
	.host-row input[type='number'],
	.host-row select {
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

	.hint.error {
		color: var(--color-error);
	}

	.actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.save {
		background: var(--color-accent);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.danger-link {
		background: none;
		border: none;
		color: var(--color-error);
		cursor: pointer;
		font-size: 0.85rem;
		padding: 0;
	}

	.confirm-actions {
		display: flex;
		gap: 0.5rem;
	}

	.cancel {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.danger {
		background: var(--color-error);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		cursor: pointer;
	}
</style>
