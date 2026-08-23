<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import type { BookmarkItem, BookmarksData } from '$lib/api';
	import { faviconSrc, hideBrokenIcon } from '$lib/bookmarkIcons';
	import { importBookmarksFromFile } from '$lib/bookmarkImport';
	import { isSafeUrl } from '$lib/url';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	let { data: initialData }: { data: BookmarksData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let bookmarks = $state(initialData);

	let searchQuery = $state('');
	let viewSort = $state<'none' | 'az' | 'za'>('none');

	let editing = $state(false);
	let titleInput = $state('');
	let bookmarkInputs = $state<BookmarkItem[]>([]);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let infoMessage = $state<string | null>(null);

	let pendingImport = $state<BookmarkItem[] | null>(null);
	let fileInputRef = $state<HTMLInputElement | null>(null);

	// Drag-and-drop state
	let draggedIndex = $state<number | null>(null);
	let dragOverIndex = $state<number | null>(null);
	let dragPosition = $state<'above' | 'below' | null>(null);

	let displayedBookmarks = $derived.by(() => {
		let list = [...bookmarks.bookmarks];
		const q = searchQuery.trim().toLowerCase();
		if (q) {
			list = list.filter((b) => b.name.toLowerCase().includes(q) || b.url.toLowerCase().includes(q));
		}
		if (viewSort === 'az') {
			list.sort((a, b) =>
				a.name.trim().localeCompare(b.name.trim(), undefined, { sensitivity: 'base', numeric: true }),
			);
		} else if (viewSort === 'za') {
			list.sort((a, b) =>
				b.name.trim().localeCompare(a.name.trim(), undefined, { sensitivity: 'base', numeric: true }),
			);
		}
		return list;
	});

	function openEditor() {
		titleInput = bookmarks.title;
		bookmarkInputs = bookmarks.bookmarks.map((bookmark) => ({ ...bookmark }));
		editing = true;
		error = null;
		infoMessage = null;
		pendingImport = null;
	}

	function addBookmarkRow() {
		bookmarkInputs = [...bookmarkInputs, { name: '', url: '', icon: '' }];
	}

	function removeBookmarkRow(index: number) {
		bookmarkInputs = bookmarkInputs.filter((_, i) => i !== index);
	}

	function moveBookmark(index: number, direction: 'up' | 'down') {
		const targetIndex = direction === 'up' ? index - 1 : index + 1;
		if (targetIndex < 0 || targetIndex >= bookmarkInputs.length) return;
		const next = [...bookmarkInputs];
		const [item] = next.splice(index, 1);
		next.splice(targetIndex, 0, item);
		bookmarkInputs = next;
	}

	function sortEditor(ascending = true) {
		bookmarkInputs = [...bookmarkInputs].sort((a, b) => {
			const cmp = a.name.trim().localeCompare(b.name.trim(), undefined, { sensitivity: 'base', numeric: true });
			return ascending ? cmp : -cmp;
		});
	}

	function toggleViewSort() {
		if (viewSort === 'none') {
			viewSort = 'az';
		} else if (viewSort === 'az') {
			viewSort = 'za';
		} else {
			viewSort = 'none';
		}
	}

	function handleDragStart(event: DragEvent, index: number) {
		draggedIndex = index;
		if (event.dataTransfer) {
			event.dataTransfer.effectAllowed = 'move';
			event.dataTransfer.setData('text/plain', String(index));
		}
	}

	function handleDragOver(event: DragEvent, index: number) {
		event.preventDefault();
		if (draggedIndex === null || draggedIndex === index) return;
		if (event.dataTransfer) {
			event.dataTransfer.dropEffect = 'move';
		}
		dragOverIndex = index;
		const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
		const midY = rect.top + rect.height / 2;
		dragPosition = event.clientY < midY ? 'above' : 'below';
	}

	function handleDragLeave(_event: DragEvent, index: number) {
		if (dragOverIndex === index) {
			dragOverIndex = null;
			dragPosition = null;
		}
	}

	function handleDrop(event: DragEvent, dropIndex: number) {
		event.preventDefault();
		if (draggedIndex === null || draggedIndex === dropIndex) {
			handleDragEnd();
			return;
		}

		const next = [...bookmarkInputs];
		const [moved] = next.splice(draggedIndex, 1);
		let target = dropIndex;
		if (dragPosition === 'below' && draggedIndex < dropIndex) {
			// already shifted by splice
		} else if (dragPosition === 'below' && draggedIndex > dropIndex) {
			target = dropIndex + 1;
		} else if (dragPosition === 'above' && draggedIndex < dropIndex) {
			target = dropIndex - 1;
		}
		target = Math.max(0, Math.min(target, next.length));
		next.splice(target, 0, moved);
		bookmarkInputs = next;
		handleDragEnd();
	}

	function handleDragEnd() {
		draggedIndex = null;
		dragOverIndex = null;
		dragPosition = null;
	}

	async function handleFileSelect(event: Event) {
		const target = event.target as HTMLInputElement;
		const file = target.files?.[0];
		if (!file) return;
		await processImportFile(file);
		target.value = '';
	}

	async function processImportFile(file: File) {
		error = null;
		infoMessage = null;
		try {
			const imported = await importBookmarksFromFile(file);
			if (bookmarkInputs.length === 0) {
				bookmarkInputs = imported;
				infoMessage = get(_)('bookmarks.detail.import_success', { values: { count: imported.length } });
			} else {
				pendingImport = imported;
			}
		} catch (err: unknown) {
			error = err instanceof Error ? err.message : get(_)('bookmarks.detail.import_error');
		}
	}

	function applyImport(mode: 'append' | 'replace') {
		if (!pendingImport) return;
		if (mode === 'append') {
			bookmarkInputs = [...bookmarkInputs, ...pendingImport];
		} else {
			bookmarkInputs = pendingImport;
		}
		infoMessage = get(_)('bookmarks.detail.import_success', { values: { count: pendingImport.length } });
		pendingImport = null;
	}

	async function saveSettings() {
		saving = true;
		error = null;
		infoMessage = null;
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
			error = get(_)('bookmarks.detail.save_error');
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>{bookmarks.title || 'Bookmarks'}</h1>
	<div class="header-actions">
		{#if !editing && bookmarks.bookmarks.length > 1}
			<button
				class="sort-toggle"
				onclick={toggleViewSort}
				aria-label={viewSort === 'az'
					? $_('bookmarks.detail.sort_za')
					: viewSort === 'za'
						? $_('common.reset')
						: $_('bookmarks.detail.sort_az')}
			>
				{viewSort === 'az' ? 'A–Z ↓' : viewSort === 'za' ? 'Z–A ↑' : 'A–Z'}
			</button>
		{/if}
		<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
			{editing ? $_('common.cancel') : $_('bookmarks.detail.edit')}
		</button>
	</div>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			{$_('bookmarks.detail.title_label')}
			<input type="text" bind:value={titleInput} />
		</label>

		<div class="toolbar">
			<button class="tool-button" type="button" onclick={() => sortEditor(true)}>
				{$_('bookmarks.detail.sort_az')}
			</button>
			<button class="tool-button" type="button" onclick={() => sortEditor(false)}>
				{$_('bookmarks.detail.sort_za')}
			</button>
			<button class="tool-button" type="button" onclick={() => fileInputRef?.click()}>
				{$_('bookmarks.detail.import_bookmarks')}
			</button>
			<input
				type="file"
				bind:this={fileInputRef}
				accept=".html,.htm,.json,.csv,.tsv"
				onchange={handleFileSelect}
				style="display: none;"
			/>
		</div>

		{#if pendingImport}
			<div class="import-prompt">
				<p class="import-prompt-text">
					{$_('bookmarks.detail.import_prompt_body', { values: { count: pendingImport.length } })}
				</p>
				<div class="import-prompt-actions">
					<button class="tool-button primary" type="button" onclick={() => applyImport('append')}>
						{$_('bookmarks.detail.import_append')}
					</button>
					<button class="tool-button" type="button" onclick={() => applyImport('replace')}>
						{$_('bookmarks.detail.import_replace')}
					</button>
					<button class="tool-button" type="button" onclick={() => (pendingImport = null)}>
						{$_('common.cancel')}
					</button>
				</div>
			</div>
		{/if}

		{#if infoMessage}
			<p class="hint info">{infoMessage}</p>
		{/if}

		<div class="bookmarks">
			{#each bookmarkInputs as bookmark, index (index)}
				<div
					class="bookmark-row"
					class:dragging={draggedIndex === index}
					class:drag-over-above={dragOverIndex === index && dragPosition === 'above'}
					class:drag-over-below={dragOverIndex === index && dragPosition === 'below'}
					draggable={true}
					role="group"
					aria-label={bookmark.name || `Bookmark ${index + 1}`}
					ondragstart={(e) => handleDragStart(e, index)}
					ondragover={(e) => handleDragOver(e, index)}
					ondragenter={(e) => handleDragOver(e, index)}
					ondragleave={(e) => handleDragLeave(e, index)}
					ondrop={(e) => handleDrop(e, index)}
					ondragend={handleDragEnd}
				>
					<span
						class="drag-handle"
						title={$_('bookmarks.detail.drag_handle')}
						aria-label={$_('bookmarks.detail.drag_handle')}
					>
						⋮⋮
					</span>
					<div class="reorder-buttons">
						<button
							type="button"
							class="move-button"
							disabled={index === 0}
							onclick={() => moveBookmark(index, 'up')}
							aria-label={$_('bookmarks.detail.move_up')}
						>
							▲
						</button>
						<button
							type="button"
							class="move-button"
							disabled={index === bookmarkInputs.length - 1}
							onclick={() => moveBookmark(index, 'down')}
							aria-label={$_('bookmarks.detail.move_down')}
						>
							▼
						</button>
					</div>
					<input type="text" placeholder={$_('bookmarks.detail.name_placeholder')} bind:value={bookmark.name} />
					<input type="text" placeholder={$_('bookmarks.detail.url_placeholder')} bind:value={bookmark.url} />
					<input type="text" placeholder={$_('bookmarks.detail.icon_placeholder')} bind:value={bookmark.icon} />
					<button
						class="remove-bookmark"
						type="button"
						onclick={() => removeBookmarkRow(index)}
						aria-label={$_('bookmarks.detail.remove_aria')}
					>
						✕
					</button>
				</div>
			{:else}
				<p class="hint">{$_('bookmarks.detail.empty_editing_hint')}</p>
			{/each}
			<button class="add-bookmark" type="button" onclick={addBookmarkRow}>
				{$_('bookmarks.detail.add_bookmark')}
			</button>
		</div>

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={saveSettings}>
			{saving ? $_('common.saving') : $_('common.save')}
		</button>
	</div>
{:else}
	{#if bookmarks.bookmarks.length > 0}
		<div class="search-bar">
			<input type="search" placeholder={$_('bookmarks.detail.search_placeholder')} bind:value={searchQuery} />
			{#if searchQuery}
				<button
					class="clear-search"
					type="button"
					onclick={() => (searchQuery = '')}
					aria-label={$_('bookmarks.detail.search_clear')}
				>
					✕
				</button>
			{/if}
		</div>
	{/if}

	{#if error}
		<p class="hint error">{error}</p>
	{/if}

	<ul class="list">
		{#if displayedBookmarks.length > 0}
			{#each displayedBookmarks as bookmark (bookmark.url)}
				<li>
					<a class="item" href={isSafeUrl(bookmark.url) ? bookmark.url : undefined} target="_blank" rel="noreferrer">
						<img class="icon" src={faviconSrc(bookmark)} alt="" onerror={hideBrokenIcon} />
						<span class="name">{bookmark.name}</span>
					</a>
				</li>
			{/each}
		{:else if searchQuery}
			<p class="hint">{$_('bookmarks.detail.no_search_results', { values: { query: searchQuery } })}</p>
		{:else}
			<p class="hint">{$_('bookmarks.detail.empty_hint')}</p>
		{/if}
	</ul>
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

	.header-actions {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.sort-toggle,
	.edit-settings {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
		font: inherit;
		font-size: 0.9rem;
	}

	.search-bar {
		display: flex;
		align-items: center;
		position: relative;
		margin: 1rem 0;
		max-width: 34rem;
	}

	.search-bar input {
		width: 100%;
		font: inherit;
		padding: 0.5rem 2rem 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.clear-search {
		position: absolute;
		right: 0.5rem;
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		font-size: 0.85rem;
		padding: 0.25rem 0.5rem;
	}

	.toolbar {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-bottom: 0.25rem;
	}

	.tool-button {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.4rem;
		padding: 0.3rem 0.6rem;
		color: var(--color-text);
		font-size: 0.85rem;
		cursor: pointer;
	}

	.tool-button:hover {
		background: var(--color-surface-hover, rgba(255, 255, 255, 0.05));
	}

	.tool-button.primary {
		background: var(--color-accent);
		color: var(--color-surface);
		border-color: var(--color-accent);
	}

	.import-prompt {
		background: var(--color-surface-hover, rgba(255, 255, 255, 0.04));
		border: 1px dashed var(--color-accent);
		border-radius: 0.5rem;
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.import-prompt-text {
		margin: 0;
		font-size: 0.9rem;
		font-weight: 500;
	}

	.import-prompt-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.settings-form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		max-width: 40rem;
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
		gap: 0.4rem;
		align-items: center;
		padding: 0.25rem;
		border-radius: 0.5rem;
		transition: background-color 0.15s ease;
	}

	.bookmark-row.dragging {
		opacity: 0.4;
	}

	.bookmark-row.drag-over-above {
		box-shadow: 0 -2px 0 0 var(--color-accent);
	}

	.bookmark-row.drag-over-below {
		box-shadow: 0 2px 0 0 var(--color-accent);
	}

	.drag-handle {
		cursor: grab;
		color: var(--color-text-muted);
		user-select: none;
		font-size: 1rem;
		padding: 0 0.2rem;
		flex-shrink: 0;
	}

	.reorder-buttons {
		display: flex;
		flex-direction: column;
		gap: 2px;
		flex-shrink: 0;
	}

	.move-button {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.25rem;
		color: var(--color-text-muted);
		font-size: 0.65rem;
		padding: 1px 4px;
		cursor: pointer;
		line-height: 1;
	}

	.move-button:disabled {
		opacity: 0.3;
		cursor: default;
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
		max-width: 34rem;
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

	.hint.info {
		color: var(--color-accent);
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
