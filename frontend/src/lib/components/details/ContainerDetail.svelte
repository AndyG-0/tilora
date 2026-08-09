<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api, type ContainerDetail, type NetworkIntegration } from '$lib/api';
	import { user } from '$lib/stores/user';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	const ENGINE_LABELS: Record<'docker' | 'podman', string> = { docker: 'Docker', podman: 'Podman' };

	let { data: initialData }: { data: ContainerDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from setHost's refetch.
	let container = $state(initialData);

	let hosts = $state<NetworkIntegration[]>([]);
	let switching = $state(false);
	let error = $state<string | null>(null);

	const widgetId = $derived(page.params.id!);
	const title = $derived(ENGINE_LABELS[container.engine] ?? 'Container');

	async function loadHosts() {
		try {
			hosts = await api.listContainerIntegrations();
		} catch {
			hosts = [];
		}
	}

	async function setHost(integrationId: string) {
		if (integrationId === container.network_integration_id) return;
		switching = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, { network_integration_id: integrationId });
			container = await api.widgetDetail<ContainerDetail>(widgetId);
		} catch {
			error = get(_)('common.connection_save_error');
		} finally {
			switching = false;
		}
	}

	onMount(loadHosts);
</script>

<div class="header">
	<h1>{title}</h1>
</div>

{#if $user?.role === 'admin' && hosts.length > 0}
	<label class="host-picker">
		{$_('container.detail.host_picker_label')}
		<select
			value={container.network_integration_id}
			disabled={switching}
			onchange={(e) => setHost(e.currentTarget.value)}
		>
			{#each hosts as host (host.id)}
				<option value={host.id}>{host.name}</option>
			{/each}
		</select>
	</label>
{/if}

{#if error}
	<p class="hint error">{error}</p>
{/if}

{#if !container.connected}
	<p class="hint">{$_('container.detail.not_connected_hint', { values: { title } })}</p>
{:else}
	{#if container.error}
		<p class="hint error">{container.error}</p>
	{/if}

	<div class="counts">
		<div class="count">
			<div class="count-value">{container.running_count}</div>
			<div class="count-label">{$_('container.detail.running_label')}</div>
		</div>
		<div class="count">
			<div class="count-value">{container.stopped_count}</div>
			<div class="count-label">{$_('container.detail.stopped_label')}</div>
		</div>
		<div class="count">
			<div class="count-value">{container.total_count}</div>
			<div class="count-label">{$_('container.detail.total_label')}</div>
		</div>
	</div>

	{#if container.containers.length === 0}
		<p class="hint">{$_('container.detail.empty')}</p>
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

	.host-picker {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		max-width: 20rem;
		margin: 1rem 0;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.host-picker select {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
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
