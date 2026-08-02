<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import type { GoodreadsDetail } from '$lib/api';

	let { data: initialData }: { data: GoodreadsDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let goodreads = $state(initialData);

	let editing = $state(false);
	let userIdInput = $state('');
	let shelfInput = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);

	function openEditor() {
		userIdInput = goodreads.user_id;
		shelfInput = goodreads.shelf;
		editing = true;
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(page.params.id!, {
				user_id: userIdInput.trim(),
				shelf: shelfInput.trim(),
			});
			goodreads = await api.widgetDetail<GoodreadsDetail>(page.params.id!);
			editing = false;
		} catch {
			error = 'Could not update the shelf settings.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>{goodreads.shelf || 'Goodreads'}</h1>
	<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
		{editing ? 'Cancel' : 'Edit shelf'}
	</button>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			Goodreads user id
			<input type="text" placeholder="12345678" bind:value={userIdInput} />
		</label>
		<label>
			Shelf
			<input type="text" placeholder="currently-reading" bind:value={shelfInput} />
		</label>

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

<div class="list">
	{#if goodreads.books.length > 0}
		{#each goodreads.books as book (book.link)}
			<a class="item" href={book.link} target="_blank" rel="noreferrer">
				{#if book.book_image_url}
					<img class="cover" src={book.book_image_url} alt="" width="64" height="96" loading="lazy" decoding="async" />
				{/if}
				<div class="item-body">
					<h2>{book.title}</h2>
					{#if book.author_name}
						<p class="meta">{book.author_name}</p>
					{/if}
					{#if book.user_rating && book.user_rating !== '0'}
						<p class="rating">Your rating: {book.user_rating}/5</p>
					{:else if book.average_rating}
						<p class="rating">Average rating: {book.average_rating}</p>
					{/if}
				</div>
			</a>
		{/each}
	{:else if !goodreads.user_id}
		<p class="hint">No shelf configured yet — tap "Edit shelf" to add your Goodreads user id.</p>
	{:else}
		<p class="hint">No books on this shelf yet.</p>
	{/if}
</div>

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

	.settings-form input {
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

	.list {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.item {
		display: flex;
		gap: 1rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1rem;
		color: inherit;
		text-decoration: none;
	}

	.item:active {
		background: var(--color-surface-hover);
	}

	.cover {
		flex-shrink: 0;
		width: 4rem;
		height: 6rem;
		object-fit: cover;
		border-radius: 0.5rem;
	}

	.item-body {
		min-width: 0;
	}

	.item h2 {
		margin: 0 0 0.25rem;
		font-size: 1.1rem;
	}

	.meta {
		color: var(--color-text-muted);
		font-size: 0.85rem;
		margin: 0 0 0.25rem;
	}

	.rating {
		margin: 0;
		font-size: 0.85rem;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
