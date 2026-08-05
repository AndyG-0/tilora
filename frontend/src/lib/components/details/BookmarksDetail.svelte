<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import type { BookmarkItem, BookmarksData } from '$lib/api';
	import { faviconSrc, hideBrokenIcon } from '$lib/bookmarkIcons';

	let { data: initialData }: { data: BookmarksData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let bookmarks = $state(initialData);

	let editing = $state(false);
	let titleInput = $state('');
	let bookmarkInputs = $state<BookmarkItem[]>([]);
	let saving = $state(false);
	let error = $state<string | null>(null);

	function openEditor() {
		titleInput = bookmarks.title;
		bookmarkInputs = bookmarks.bookmarks.map((bookmark) => ({ ...bookmark }));
		editing = true;
	}

	function addBookmarkRow() {
		bookmarkInputs = [...bookmarkInputs, { name: '', url: '', icon: '' }];
	}

	function removeBookmarkRow(index: number) {
		bookmarkInputs = bookmarkInputs.filter((_, i) => i !== index);
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			const newBookmarks = bookmarkInputs
				.map((bookmark) => ({
					name: bookmark.name.trim(),
					url: bookmark.url.trim(),
					icon: bookmark.icon?.trim() || undefined,
				}))
				.filter((bookmark) => bookmark.name.length > 0 && bookmark.url.length > 0);
			await api.updateWidgetSettings(page.params.id!, {
				title: titleInput,
				bookmarks: newBookmarks,
			});
			bookmarks = await api.widgetDetail<BookmarksData>(page.params.id!);
			editing = false;
		} catch {
			error = 'Could not update the bookmarks.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>{bookmarks.title || 'Bookmarks'}</h1>
	<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
		{editing ? 'Cancel' : 'Edit bookmarks'}
	</button>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			Title
			<input type="text" bind:value={titleInput} />
		</label>

		<div class="bookmarks">
			{#each bookmarkInputs as bookmark, index (index)}
				<div class="bookmark-row">
					<input type="text" placeholder="Name" bind:value={bookmark.name} />
					<input type="text" placeholder="URL" bind:value={bookmark.url} />
					<input type="text" placeholder="Icon URL (optional)" bind:value={bookmark.icon} />
					<button class="remove-bookmark" onclick={() => removeBookmarkRow(index)} aria-label="Remove bookmark">
						✕
					</button>
				</div>
			{:else}
				<p class="hint">No bookmarks yet — add one below.</p>
			{/each}
			<button class="add-bookmark" onclick={addBookmarkRow}>+ Add bookmark</button>
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

<ul class="list">
	{#if bookmarks.bookmarks.length > 0}
		{#each bookmarks.bookmarks as bookmark (bookmark.url)}
			<li>
				<a class="item" href={bookmark.url} target="_blank" rel="noreferrer">
					<img class="icon" src={faviconSrc(bookmark)} alt="" onerror={hideBrokenIcon} />
					<span class="name">{bookmark.name}</span>
				</a>
			</li>
		{/each}
	{:else}
		<p class="hint">No bookmarks configured yet — tap "Edit bookmarks" to add one.</p>
	{/if}
</ul>

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
		max-width: 34rem;
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

	.bookmarks {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.bookmark-row {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.bookmark-row input {
		flex: 1;
		min-width: 0;
	}

	.remove-bookmark {
		flex-shrink: 0;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		cursor: pointer;
	}

	.add-bookmark {
		align-self: flex-start;
		background: none;
		border: 1px dashed var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
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
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.item {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
		color: inherit;
		text-decoration: none;
	}

	.item:active {
		background: var(--color-surface-hover);
	}

	.icon {
		width: 1.25rem;
		height: 1.25rem;
		flex-shrink: 0;
		border-radius: 0.25rem;
	}

	.name {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
