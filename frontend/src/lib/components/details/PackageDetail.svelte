<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import type { PackagesData } from '$lib/api';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	let { data: initialData }: { data: PackagesData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from add/remove refetches.
	let detail = $state(initialData);

	let trackingNumber = $state('');
	let label = $state('');
	let adding = $state(false);
	let error = $state<string | null>(null);

	async function refresh() {
		detail = await api.widgetDetail<PackagesData>(page.params.id!);
	}

	async function addPackage() {
		const trimmed = trackingNumber.trim();
		if (!trimmed) return;
		adding = true;
		error = null;
		try {
			await api.createPackage(trimmed, label.trim() || undefined);
			trackingNumber = '';
			label = '';
			await refresh();
		} catch {
			error = get(_)('packages.detail.add_error');
		} finally {
			adding = false;
		}
	}

	async function remove(id: number) {
		try {
			await api.removePackage(id);
			await refresh();
		} catch {
			error = get(_)('packages.detail.remove_error');
		}
	}
</script>

<h1>{detail.title || 'Packages'}</h1>

<form class="add" onsubmit={(e) => (e.preventDefault(), addPackage())}>
	<input type="text" placeholder={$_('packages.detail.tracking_placeholder')} bind:value={trackingNumber} />
	<input type="text" placeholder={$_('packages.detail.label_placeholder')} bind:value={label} />
	<button type="submit" disabled={adding || !trackingNumber.trim()}>{$_('common.add')}</button>
</form>

{#if error}
	<p class="hint error">{error}</p>
{/if}

<ul class="list">
	{#each detail.packages as pkg (pkg.id)}
		<li class:delivered={pkg.delivered}>
			<div class="pkg-info">
				<span class="text">{pkg.label || pkg.tracking_number}</span>
				<span class="meta">
					{#if pkg.label}{pkg.tracking_number} ·
					{/if}
					{#if pkg.carrier}{pkg.carrier} ·
					{/if}
					{#if pkg.delivered}
						{$_('packages.detail.delivered')}
					{:else if pkg.status}
						{pkg.status}
					{:else}
						{$_('packages.detail.awaiting_status')}
					{/if}
					{#if pkg.eta_date && !pkg.delivered}
						· {$_('packages.detail.eta', { values: { date: pkg.eta_date } })}
					{/if}
				</span>
				{#if pkg.last_event}
					<span class="event">{pkg.last_event}</span>
				{/if}
			</div>
			<button class="remove" onclick={() => remove(pkg.id)} aria-label={$_('packages.detail.remove_aria')}>✕</button>
		</li>
	{:else}
		<p class="hint">{$_('packages.detail.empty_hint')}</p>
	{/each}
</ul>

<style>
	.add {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		max-width: 30rem;
		margin: 1rem 0 1.5rem;
	}

	.add input {
		flex: 1;
		min-width: 8rem;
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.add button {
		flex-shrink: 0;
		background: var(--color-accent);
		color: var(--color-on-accent);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.add button:disabled {
		opacity: 0.6;
		cursor: default;
	}

	.list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		max-width: 30rem;
	}

	.list li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
	}

	.list li.delivered .text {
		color: var(--color-text-muted);
	}

	.pkg-info {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.text {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.meta,
	.event {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.remove {
		flex-shrink: 0;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		cursor: pointer;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
