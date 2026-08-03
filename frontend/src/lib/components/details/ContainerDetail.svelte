<script lang="ts">
	import { page } from '$app/state';
	import { api, type ContainerDetail } from '$lib/api';
	import { user } from '$lib/stores/user';

	let { data: initialData }: { data: ContainerDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let container = $state(initialData);

	const ENGINE_LABELS: Record<'docker' | 'podman', string> = { docker: 'Docker', podman: 'Podman' };
	const ENGINE_DEFAULTS: Record<'docker' | 'podman', { socketPath: string; host: string; port: number }> = {
		docker: { socketPath: '/var/run/docker.sock', host: 'docker.local', port: 2375 },
		podman: { socketPath: '/run/podman/podman.sock', host: 'podman.local', port: 8080 },
	};

	let editing = $state(false);
	let engineInput = $state<'docker' | 'podman'>('docker');
	let connectionInput = $state<'socket' | 'tcp'>('socket');
	let socketPathInput = $state('/var/run/docker.sock');
	let hostInput = $state('');
	let portInput = $state(2375);
	let saving = $state(false);
	let error = $state<string | null>(null);

	const widgetId = $derived(page.params.id!);
	const title = $derived(ENGINE_LABELS[container.engine] ?? 'Container');
	const enginePlaceholders = $derived(ENGINE_DEFAULTS[engineInput]);

	function openEditor() {
		engineInput = container.engine;
		connectionInput = container.connection === 'tcp' ? 'tcp' : 'socket';
		socketPathInput = container.socket_path;
		hostInput = container.host;
		portInput = container.port;
		editing = true;
	}

	function onEngineChange(next: 'docker' | 'podman') {
		const previousDefaults = ENGINE_DEFAULTS[engineInput];
		const nextDefaults = ENGINE_DEFAULTS[next];
		if (socketPathInput === previousDefaults.socketPath) socketPathInput = nextDefaults.socketPath;
		if (portInput === previousDefaults.port) portInput = nextDefaults.port;
		engineInput = next;
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, {
				engine: engineInput,
				connection: connectionInput,
				socket_path: socketPathInput,
				host: hostInput,
				port: portInput,
			});
			container = await api.widgetDetail<ContainerDetail>(widgetId);
			editing = false;
		} catch {
			error = 'Could not save the connection settings.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>{title}</h1>
	{#if $user?.role === 'admin'}
		<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
			{editing ? 'Cancel' : 'Edit connection'}
		</button>
	{/if}
</div>

{#if editing}
	<div class="settings-form">
		<label>
			Engine
			<select value={engineInput} onchange={(e) => onEngineChange(e.currentTarget.value as 'docker' | 'podman')}>
				<option value="docker">Docker</option>
				<option value="podman">Podman</option>
			</select>
		</label>
		<label>
			Connection
			<select bind:value={connectionInput}>
				<option value="socket">Local socket</option>
				<option value="tcp">Remote (TCP)</option>
			</select>
		</label>
		{#if connectionInput === 'socket'}
			<label>
				Socket path
				<input type="text" bind:value={socketPathInput} placeholder={enginePlaceholders.socketPath} />
			</label>
		{:else}
			<label>
				Host
				<input type="text" bind:value={hostInput} placeholder={enginePlaceholders.host} />
			</label>
			<label>
				Port
				<input type="number" min="1" max="65535" bind:value={portInput} />
			</label>
		{/if}

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
	{#if !container.connected}
		<p class="hint">Not connected yet — tap "Edit connection" to set up {title}.</p>
	{:else}
		{#if container.error}
			<p class="hint error">{container.error}</p>
		{/if}

		<div class="counts">
			<div class="count">
				<div class="count-value">{container.running_count}</div>
				<div class="count-label">Running</div>
			</div>
			<div class="count">
				<div class="count-value">{container.stopped_count}</div>
				<div class="count-label">Stopped</div>
			</div>
			<div class="count">
				<div class="count-value">{container.total_count}</div>
				<div class="count-label">Total</div>
			</div>
		</div>

		{#if container.containers.length === 0}
			<p class="hint">No containers found.</p>
		{:else}
			<ul class="containers">
				{#each container.containers as item (item.id)}
					<li>
						<span class="dot" class:on={item.state === 'running'}></span>
						<span class="name">{item.name}</span>
						<span class="image">{item.image}</span>
						<span class="status">{item.status}</span>
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

	.settings-form input[type='text'],
	.settings-form input[type='number'],
	.settings-form select {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
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

	.counts {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(7rem, 1fr));
		gap: 1rem;
		margin: 1rem 0;
	}

	.count {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.75rem 1rem;
	}

	.count-value {
		font-size: 1.5rem;
		font-weight: 600;
	}

	.count-label {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.containers {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.containers li {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
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

	.name {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.image {
		color: var(--color-text-muted);
		font-size: 0.85rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.status {
		margin-left: auto;
		color: var(--color-text-muted);
		font-size: 0.85rem;
		flex-shrink: 0;
	}
</style>
