<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';

	interface RSSItem {
		title: string;
		link: string;
		published: string | null;
		summary: string;
		source: string;
	}

	interface RSSFeed {
		url: string;
		name?: string;
	}

	interface RSSDetailData {
		title: string;
		feeds: RSSFeed[];
		item_limit: number;
		items: RSSItem[];
	}

	let { data: initialData }: { data: RSSDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let rss = $state(initialData);

	let editing = $state(false);
	let titleInput = $state('');
	let itemLimitInput = $state(5);
	let feedInputs = $state<RSSFeed[]>([]);
	let saving = $state(false);
	let error = $state<string | null>(null);

	function openEditor() {
		titleInput = rss.title;
		itemLimitInput = rss.item_limit;
		feedInputs = rss.feeds.map((feed) => ({ ...feed }));
		editing = true;
	}

	function addFeedRow() {
		feedInputs = [...feedInputs, { url: '', name: '' }];
	}

	function removeFeedRow(index: number) {
		feedInputs = feedInputs.filter((_, i) => i !== index);
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			const feeds = feedInputs
				.map((feed) => ({ url: feed.url.trim(), name: feed.name?.trim() || undefined }))
				.filter((feed) => feed.url.length > 0);
			await api.updateWidgetSettings(page.params.id!, {
				title: titleInput,
				item_limit: itemLimitInput,
				feeds,
			});
			rss = await api.widgetDetail<RSSDetailData>(page.params.id!);
			editing = false;
		} catch {
			error = 'Could not update the feeds.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>{rss.title || 'Headlines'}</h1>
	<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
		{editing ? 'Cancel' : 'Edit feeds'}
	</button>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			Title
			<input type="text" bind:value={titleInput} />
		</label>
		<label>
			Items to show
			<input type="number" min="1" max="20" bind:value={itemLimitInput} />
		</label>

		<div class="feeds">
			{#each feedInputs as feed, index (index)}
				<div class="feed-row">
					<input type="text" placeholder="Feed URL" bind:value={feed.url} />
					<input type="text" placeholder="Name (optional)" bind:value={feed.name} />
					<button class="remove-feed" onclick={() => removeFeedRow(index)} aria-label="Remove feed"> ✕ </button>
				</div>
			{:else}
				<p class="hint">No feeds yet — add one below.</p>
			{/each}
			<button class="add-feed" onclick={addFeedRow}>+ Add feed</button>
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

<div class="list">
	{#if rss.items.length > 0}
		{#each rss.items as item (item.link)}
			<a class="item" href={item.link} target="_blank" rel="noreferrer">
				<h2>{item.title}</h2>
				<p class="meta">{item.source}{item.published ? ` · ${item.published}` : ''}</p>
				{#if item.summary}
					<p class="summary">{item.summary}</p>
				{/if}
			</a>
		{/each}
	{:else if rss.feeds.length === 0}
		<p class="hint">No feeds configured yet — tap "Edit feeds" to add one.</p>
	{:else}
		<p class="hint">No items yet.</p>
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

	.feeds {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.feed-row {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.feed-row input {
		flex: 1;
		min-width: 0;
	}

	.remove-feed {
		flex-shrink: 0;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		cursor: pointer;
	}

	.add-feed {
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
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.item {
		display: block;
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
