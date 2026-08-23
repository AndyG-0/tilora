<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { renderMarkdown } from '$lib/markdown';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	interface MessageDetailData {
		title: string;
		text: string;
	}

	let { data: initialData }: { data: MessageDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveMessage's refetch.
	let message = $state(initialData);

	let editing = $state(false);
	let titleInput = $state('');
	let textInput = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);

	function openEditor() {
		titleInput = message.title;
		textInput = message.text;
		editing = true;
	}

	async function saveMessage() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(page.params.id!, { title: titleInput, text: textInput });
			message = await api.widgetDetail<MessageDetailData>(page.params.id!);
			editing = false;
		} catch {
			error = get(_)('message.detail.save_error');
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>{message.title || $_('message.detail.default_title')}</h1>
	<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
		{editing ? $_('common.cancel') : $_('message.detail.edit_message')}
	</button>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			{$_('message.detail.title_label')}
			<input type="text" bind:value={titleInput} />
		</label>
		<label>
			{$_('message.detail.text_label')}
			<textarea rows="6" bind:value={textInput}></textarea>
		</label>
		<p class="hint">{$_('message.detail.markdown_hint')}</p>

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={saveMessage}>
			{saving ? $_('common.saving') : $_('common.save')}
		</button>
	</div>
{:else if error}
	<p class="hint error">{error}</p>
{/if}

<!-- eslint-disable-next-line svelte/no-at-html-tags -- renderMarkdown sanitizes with DOMPurify against an explicit tag/attribute allowlist before this reaches the DOM. -->
<div class="current">{@html renderMarkdown(message.text)}</div>

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

	.settings-form input,
	.settings-form textarea {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		resize: vertical;
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

	.hint {
		color: var(--color-text-muted);
		margin: 0.5rem 0 0;
	}

	.hint.error {
		color: var(--color-error);
	}

	.current {
		font-size: 1.3rem;
		line-height: 1.5;
		overflow-wrap: break-word;
	}

	/* {@html}-injected markdown sits outside Svelte's scoped-style tree. */
	.current :global(p) {
		margin: 0 0 0.6em;
	}

	.current :global(p:last-child) {
		margin-bottom: 0;
	}

	.current :global(ul),
	.current :global(ol) {
		margin: 0 0 0.6em;
		padding-left: 1.4em;
	}

	.current :global(h1),
	.current :global(h2),
	.current :global(h3) {
		margin: 0.75em 0 0.4em;
	}

	.current :global(blockquote) {
		margin: 0 0 0.6em;
		padding-left: 0.75em;
		border-left: 3px solid var(--color-border);
		color: var(--color-text-muted);
	}

	.current :global(code) {
		background: var(--color-surface);
		border-radius: 0.25rem;
		padding: 0.1em 0.3em;
	}

	.current :global(pre) {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.75em;
		overflow-x: auto;
	}

	.current :global(pre code) {
		background: none;
		padding: 0;
	}
</style>
