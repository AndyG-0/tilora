<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import type { RSSDetail as RSSDetailData, RSSItem, RSSFeed } from '$lib/api';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	let { data: initialData }: { data: RSSDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let rss = $state(initialData);

	let editing = $state(false);
	let titleInput = $state('');
	let selectedFeedIds = $state<Set<number>>(new Set());
	let saving = $state(false);
	let error = $state<string | null>(null);

	let managing = $state(false);
	let newFeedUrl = $state('');
	let newFeedName = $state('');
	let newFeedItemLimit = $state(10);
	let manageError = $state<string | null>(null);
	let editingFeedId = $state<number | null>(null);
	let editFeedName = $state('');
	let editFeedItemLimit = $state(10);

	function openEditor() {
		titleInput = rss.title;
		selectedFeedIds = new Set(rss.feed_ids);
		editing = true;
	}

	function toggleFeed(id: number) {
		const next = new Set(selectedFeedIds);
		if (next.has(id)) {
			next.delete(id);
		} else {
			next.add(id);
		}
		selectedFeedIds = next;
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(page.params.id!, {
				title: titleInput,
				feed_ids: [...selectedFeedIds],
			});
			rss = await api.widgetDetail<RSSDetailData>(page.params.id!);
			editing = false;
		} catch {
			error = get(_)('rss.detail.update_feeds_error');
		} finally {
			saving = false;
		}
	}

	async function refreshFeeds() {
		rss = { ...rss, all_feeds: await api.listRSSFeeds() };
	}

	async function addFeed() {
		const url = newFeedUrl.trim();
		if (!url) return;
		manageError = null;
		try {
			await api.addRSSFeed(url, newFeedName.trim() || undefined, newFeedItemLimit);
			newFeedUrl = '';
			newFeedName = '';
			newFeedItemLimit = 10;
			await refreshFeeds();
		} catch {
			manageError = get(_)('rss.detail.add_feed_error');
		}
	}

	function startEditFeed(feed: RSSFeed) {
		editingFeedId = feed.id;
		editFeedName = feed.name ?? '';
		editFeedItemLimit = feed.item_limit;
	}

	async function saveEditFeed(id: number) {
		manageError = null;
		try {
			await api.updateRSSFeed(id, editFeedName.trim() || null, editFeedItemLimit);
			editingFeedId = null;
			await refreshFeeds();
		} catch {
			manageError = get(_)('rss.detail.update_feed_error');
		}
	}

	async function removeFeed(id: number) {
		manageError = null;
		try {
			await api.deleteRSSFeed(id);
			const next = new Set(selectedFeedIds);
			next.delete(id);
			selectedFeedIds = next;
			await refreshFeeds();
		} catch {
			manageError = get(_)('rss.detail.remove_feed_error');
		}
	}

	let groups = $derived(rss.feed_groups.filter((group) => group.items.length > 0 || group.error));
</script>

{#snippet mediaList(items: RSSItem[])}
	<div class="list">
		{#each items as item (item.link)}
			<a class="item" href={item.link} target="_blank" rel="noreferrer">
				{#if item.image}
					<img class="thumb" src={item.image} alt="" loading="lazy" decoding="async" />
				{/if}
				<div class="info">
					<h2>{item.title}</h2>
					<p class="meta">{item.source}{item.published ? ` · ${item.published}` : ''}</p>
					{#if item.summary}
						<p class="summary">{item.summary}</p>
					{/if}
				</div>
			</a>
		{/each}
	</div>
{/snippet}

<div class="header">
	<h1>{rss.title || 'Headlines'}</h1>
	<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
		{editing ? $_('common.cancel') : $_('rss.detail.edit_feeds')}
	</button>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			{$_('rss.detail.title_label')}
			<input type="text" bind:value={titleInput} />
		</label>

		<div class="feed-checklist">
			<p class="label">{$_('rss.detail.show_feeds_label')}</p>
			{#if rss.all_feeds.length === 0}
				<p class="hint">{$_('rss.detail.no_feeds_catalog_hint')}</p>
			{:else}
				{#each rss.all_feeds as feed (feed.id)}
					<label class="feed-checkbox">
						<input type="checkbox" checked={selectedFeedIds.has(feed.id)} onchange={() => toggleFeed(feed.id)} />
						{feed.name || feed.url}
					</label>
				{/each}
			{/if}
		</div>

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={saveSettings}>
			{saving ? $_('common.saving') : $_('common.save')}
		</button>

		<button class="manage-toggle" onclick={() => (managing = !managing)}>
			{managing ? $_('rss.detail.hide_feeds') : $_('rss.detail.manage_feeds')}
		</button>

		{#if managing}
			<div class="manage-feeds">
				{#each rss.all_feeds as feed (feed.id)}
					<div class="feed-row">
						{#if editingFeedId === feed.id}
							<input type="text" placeholder={$_('rss.detail.name_placeholder')} bind:value={editFeedName} />
							<input type="number" min="1" max="30" bind:value={editFeedItemLimit} />
							<button class="row-action" onclick={() => saveEditFeed(feed.id)}>{$_('common.save')}</button>
							<button class="row-action" onclick={() => (editingFeedId = null)}>{$_('common.cancel')}</button>
						{:else}
							<div class="feed-summary">
								<span class="feed-name">{feed.name || feed.url}</span>
								<span class="feed-meta">{feed.url} · {feed.item_limit} items</span>
							</div>
							<button class="row-action" onclick={() => startEditFeed(feed)}>{$_('common.edit')}</button>
							<button class="row-action remove" onclick={() => removeFeed(feed.id)}>{$_('common.remove')}</button>
						{/if}
					</div>
				{:else}
					<p class="hint">{$_('rss.detail.no_feeds_hint')}</p>
				{/each}

				<div class="add-feed-row">
					<input type="text" placeholder={$_('rss.detail.feed_url_placeholder')} bind:value={newFeedUrl} />
					<input type="text" placeholder={$_('rss.detail.name_placeholder')} bind:value={newFeedName} />
					<input type="number" min="1" max="30" bind:value={newFeedItemLimit} />
					<button class="row-action" onclick={addFeed}>{$_('rss.detail.add_feed')}</button>
				</div>

				{#if manageError}
					<p class="hint error">{manageError}</p>
				{/if}
			</div>
		{/if}
	</div>
{:else if error}
	<p class="hint error">{error}</p>
{/if}

{#if groups.length > 0}
	{#each groups as group (group.feed_id)}
		{#if groups.length > 1}
			<h2 class="group-heading">{group.name}</h2>
		{/if}
		{#if group.error}
			<p class="hint error">{group.error}</p>
		{:else}
			{@render mediaList(group.items)}
		{/if}
	{/each}
{:else if rss.feed_ids.length === 0}
	<p class="hint">{$_('rss.detail.no_feeds_selected_hint')}</p>
{:else}
	<p class="hint">{$_('rss.detail.no_items')}</p>
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
	.settings-form input[type='number'] {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.feed-checklist {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.feed-checklist .label {
		margin: 0;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.settings-form label.feed-checkbox {
		flex-direction: row;
		align-items: center;
		gap: 0.5rem;
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

	.manage-toggle {
		align-self: flex-start;
		background: none;
		border: 1px dashed var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.manage-feeds {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		border-top: 1px solid var(--color-border);
		padding-top: 0.75rem;
	}

	.feed-row,
	.add-feed-row {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		flex-wrap: wrap;
	}

	.feed-summary {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
	}

	.feed-name {
		font-weight: 600;
	}

	.feed-meta {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.add-feed-row input[type='text'] {
		flex: 1;
		min-width: 8rem;
	}

	.add-feed-row input[type='number'] {
		width: 4.5rem;
	}

	.row-action {
		flex-shrink: 0;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.3rem 0.6rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.row-action.remove {
		color: var(--color-error);
	}

	.group-heading {
		margin: 1.5rem 0 0.75rem;
		font-size: 1.1rem;
	}

	.group-heading:first-of-type {
		margin-top: 0;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.item {
		display: flex;
		gap: 0.75rem;
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

	.thumb {
		flex-shrink: 0;
		width: 5rem;
		height: 5rem;
		border-radius: 0.5rem;
		object-fit: cover;
	}

	.info {
		min-width: 0;
	}

	.item h2 {
		margin: 0 0 0.25rem;
		font-size: 1.1rem;
	}

	.meta {
		color: var(--color-text-muted);
		font-size: 0.85rem;
		margin: 0 0 0.5rem;
	}

	.summary {
		margin: 0;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
