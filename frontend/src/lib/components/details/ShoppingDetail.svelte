<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import type { ShoppingData } from '$lib/api';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	let { data: initialData }: { data: ShoppingData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from add/check/remove refetches.
	let detail = $state(initialData);

	let text = $state('');
	let adding = $state(false);
	let error = $state<string | null>(null);

	async function refresh() {
		detail = await api.widgetDetail<ShoppingData>(page.params.id!);
	}

	async function addItem() {
		const trimmed = text.trim();
		if (!trimmed) return;
		adding = true;
		error = null;
		try {
			await api.createShoppingItem(page.params.id!, trimmed);
			text = '';
			await refresh();
		} catch {
			error = get(_)('common.add_item_error');
		} finally {
			adding = false;
		}
	}

	async function toggleChecked(id: number) {
		try {
			await api.checkShoppingItem(id);
			await refresh();
		} catch {
			error = get(_)('common.update_item_error');
		}
	}

	async function remove(id: number) {
		try {
			await api.removeShoppingItem(id);
			await refresh();
		} catch {
			error = get(_)('common.remove_item_error');
		}
	}
</script>

<h1>{detail.title || $_('shopping.default_title')}</h1>

<form class="add" onsubmit={(e) => (e.preventDefault(), addItem())}>
	<input type="text" placeholder={$_('common.add_item_placeholder')} bind:value={text} />
	<button type="submit" disabled={adding || !text.trim()}>{$_('common.add')}</button>
</form>

{#if error}
	<p class="hint error">{error}</p>
{/if}

<ul class="list">
	{#each detail.items as item (item.id)}
		<li class:checked={item.checked}>
			<label>
				<input type="checkbox" checked={item.checked} onchange={() => toggleChecked(item.id)} />
				<span class="item-info">
					<span class="text">{item.text}</span>
					<span class="attribution">
						{#if item.checked}
							{$_('shopping.detail.checked_by', { values: { name: item.checked_by } })}
						{:else}
							{$_('shopping.detail.added_by', { values: { name: item.added_by } })}
						{/if}
					</span>
				</span>
			</label>
			<button class="remove" onclick={() => remove(item.id)} aria-label={$_('common.remove_item_aria')}>✕</button>
		</li>
	{:else}
		<p class="hint">{$_('common.no_items_hint')}</p>
	{/each}
</ul>

<style>
	.add {
		display: flex;
		gap: 0.5rem;
		max-width: 24rem;
		margin: 1rem 0 1.5rem;
	}

	.add input {
		flex: 1;
		min-width: 0;
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
		max-width: 24rem;
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

	.list li.checked .text {
		color: var(--color-text-muted);
		text-decoration: line-through;
	}

	.list label {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		min-width: 0;
		cursor: pointer;
	}

	.item-info {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.text {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.attribution {
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
