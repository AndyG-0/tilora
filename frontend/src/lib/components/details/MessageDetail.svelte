<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';

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
			error = 'Could not update the message.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>{message.title || 'Message'}</h1>
	<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
		{editing ? 'Cancel' : 'Edit message'}
	</button>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			Title
			<input type="text" bind:value={titleInput} />
		</label>
		<label>
			Text
			<textarea rows="6" bind:value={textInput}></textarea>
		</label>

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={saveMessage}>
			{saving ? 'Saving…' : 'Save'}
		</button>
	</div>
{:else if error}
	<p class="hint error">{error}</p>
{/if}

<p class="current">{message.text}</p>

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
		white-space: pre-wrap;
		overflow-wrap: break-word;
	}
</style>
