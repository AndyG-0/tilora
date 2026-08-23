<script lang="ts">
	import { page } from '$app/state';
	import { api, type PiholeDetail } from '$lib/api';
	import { user } from '$lib/stores/user';
	import { _, locale } from 'svelte-i18n';
	import { get } from 'svelte/store';

	let { data: initialData }: { data: PiholeDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from setBlocking's refetch.
	let pihole = $state(initialData);

	const isAdmin = $derived($user?.role === 'admin');

	let error = $state<string | null>(null);
	let blockingBusy = $state(false);

	const widgetId = $derived(page.params.id!);

	async function refetch() {
		pihole = await api.widgetDetail<PiholeDetail>(widgetId);
	}

	async function setBlocking(enabled: boolean, timer: number | null = null) {
		blockingBusy = true;
		error = null;
		try {
			await api.piholeSetBlocking(widgetId, enabled, timer);
			await refetch();
		} catch {
			error = get(_)('pihole.detail.blocking_error');
		} finally {
			blockingBusy = false;
		}
	}

	function formatTimestamp(unixSeconds: number | null): string {
		if (!unixSeconds) return get(_)('pihole.detail.unknown_timestamp');
		return new Date(unixSeconds * 1000).toLocaleString(get(locale) ?? undefined);
	}
</script>

<div class="header">
	<h1>Pi-hole</h1>
</div>

{#if error}
	<p class="hint error">{error}</p>
{/if}

{#if !pihole.connected}
	<p class="hint">{$_('pihole.detail.not_connected_hint')}</p>
{:else}
	{#if pihole.error}
		<p class="hint error">{pihole.error}</p>
	{/if}

	<div class="blocking-row">
		<span class="blocking-status" class:on={pihole.blocking_enabled} class:off={!pihole.blocking_enabled}>
			{pihole.blocking_enabled ? $_('pihole.detail.blocking_enabled') : $_('pihole.detail.blocking_paused')}
		</span>
		<div class="blocking-actions">
			{#if isAdmin}
				{#if pihole.blocking_enabled}
					<button disabled={blockingBusy} onclick={() => setBlocking(false, 30)}>{$_('pihole.detail.pause_30s')}</button
					>
					<button disabled={blockingBusy} onclick={() => setBlocking(false, 300)}>{$_('pihole.detail.pause_5m')}</button
					>
					<button disabled={blockingBusy} onclick={() => setBlocking(false)}>{$_('pihole.detail.disable')}</button>
				{:else}
					<button disabled={blockingBusy} onclick={() => setBlocking(true)}>{$_('pihole.detail.enable')}</button>
				{/if}
			{:else}
				<span class="hint">{$_('pihole.detail.admin_only_hint')}</span>
			{/if}
		</div>
	</div>

	<div class="stats">
		<div class="stat">
			<div class="stat-value">{(pihole.queries_today ?? 0).toLocaleString()}</div>
			<div class="stat-label">{$_('pihole.detail.stat_queries_today')}</div>
		</div>
		<div class="stat">
			<div class="stat-value">{(pihole.blocked_today ?? 0).toLocaleString()}</div>
			<div class="stat-label">{$_('pihole.detail.stat_blocked_today')}</div>
		</div>
		<div class="stat">
			<div class="stat-value">{Math.round(pihole.percent_blocked ?? 0)}%</div>
			<div class="stat-label">{$_('pihole.detail.stat_percent_blocked')}</div>
		</div>
		<div class="stat">
			<div class="stat-value">{pihole.unique_clients} / {pihole.clients_total}</div>
			<div class="stat-label">{$_('pihole.detail.stat_active_clients')}</div>
		</div>
		<div class="stat">
			<div class="stat-value">{pihole.domains_blocked.toLocaleString()}</div>
			<div class="stat-label">{$_('pihole.detail.stat_domains_blocked')}</div>
		</div>
	</div>
	<p class="hint">
		{$_('pihole.detail.blocklist_updated', { values: { timestamp: formatTimestamp(pihole.gravity_last_update) } })}
	</p>

	<div class="domain-lists">
		<div class="domain-list">
			<h2>{$_('pihole.detail.top_blocked')}</h2>
			{#if pihole.top_blocked_domains.length === 0}
				<p class="hint">{$_('common.no_data')}</p>
			{:else}
				<ul>
					{#each pihole.top_blocked_domains as entry (entry.domain)}
						<li><span class="domain">{entry.domain}</span><span class="count">{entry.count}</span></li>
					{/each}
				</ul>
			{/if}
		</div>
		<div class="domain-list">
			<h2>{$_('pihole.detail.top_permitted')}</h2>
			{#if pihole.top_permitted_domains.length === 0}
				<p class="hint">{$_('common.no_data')}</p>
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
