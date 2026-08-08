<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import type { ChoresData } from '$lib/api';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	let { data: initialData }: { data: ChoresData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from add/complete/remove refetches.
	let detail = $state(initialData);

	let text = $state('');
	let adding = $state(false);
	let error = $state<string | null>(null);

	async function refresh() {
		detail = await api.widgetDetail<ChoresData>(page.params.id!);
	}

	async function addItem() {
		const trimmed = text.trim();
		if (!trimmed) return;
		adding = true;
		error = null;
		try {
			await api.createChore(trimmed);
			text = '';
			await refresh();
		} catch {
			error = get(_)('common.add_item_error');
		} finally {
			adding = false;
		}
	}

	async function toggleComplete(id: number) {
		try {
			await api.completeChore(id);
			await refresh();
		} catch {
			error = get(_)('common.update_item_error');
		}
	}

	async function remove(id: number) {
		try {
			await api.removeChore(id);
			await refresh();
		} catch {
			error = get(_)('common.remove_item_error');
		}
	}
</script>

<h1>{detail.title || 'To-Do'}</h1>

<form class="add" onsubmit={(e) => (e.preventDefault(), addItem())}>
	<input type="text" placeholder={$_('common.add_item_placeholder')} bind:value={text} />
	<button type="submit" disabled={adding || !text.trim()}>{$_('common.add')}</button>
</form>

{#if error}
	<p class="hint error">{error}</p>
{/if}

<ul class="list">
	{#each detail.chores as chore (chore.id)}
		<li class:completed={chore.completed}>
			<label>
				<input type="checkbox" checked={chore.completed} onchange={() => toggleComplete(chore.id)} />
				<span class="text">{chore.text}</span>
			</label>
			<button class="remove" onclick={() => remove(chore.id)} aria-label={$_('common.remove_item_aria')}>✕</button>
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

	.list li.completed .text {
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

	.text {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
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
