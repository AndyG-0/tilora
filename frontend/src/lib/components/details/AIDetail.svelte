<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { isSpeechSynthesisSupported, speak } from '$lib/speech';

	interface AIRun {
		ran_at: string;
		text: string;
	}

	interface AIDetailData {
		title: string;
		text: string;
		ran_at: string | null;
		history: AIRun[];
		prompt: string;
		cron: string;
	}

	let { data: initialData }: { data: AIDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings/regenerate's refetch.
	let ai = $state(initialData);

	let editingPrompt = $state(false);
	let promptInput = $state('');
	let saving = $state(false);
	let regenerating = $state(false);
	let error = $state<string | null>(null);

	function openEditor() {
		promptInput = ai.prompt;
		editingPrompt = true;
	}

	async function savePrompt() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(page.params.id!, { prompt: promptInput });
			ai = await api.widgetDetail<AIDetailData>(page.params.id!);
			editingPrompt = false;
		} catch {
			error = 'Could not update the prompt.';
		} finally {
			saving = false;
		}
	}

	async function regenerateNow() {
		regenerating = true;
		error = null;
		try {
			ai = await api.runAiWidget<AIDetailData>(page.params.id!);
		} catch {
			error = 'Could not regenerate the briefing.';
		} finally {
			regenerating = false;
		}
	}
</script>

<div class="header">
	<h1>{ai.title}</h1>
	<div class="actions">
		<button class="regenerate" disabled={regenerating} onclick={regenerateNow}>
			{regenerating ? 'Regenerating…' : 'Regenerate now'}
		</button>
		{#if isSpeechSynthesisSupported()}
			<button class="read-aloud" onclick={() => speak(ai.text)}>🔊 Read aloud</button>
		{/if}
		<button class="edit-settings" onclick={() => (editingPrompt ? (editingPrompt = false) : openEditor())}>
			{editingPrompt ? 'Cancel' : 'Edit prompt'}
		</button>
	</div>
</div>

{#if editingPrompt}
	<div class="settings-form">
		<label>
			Prompt
			<textarea rows="6" bind:value={promptInput}></textarea>
		</label>

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={savePrompt}>
			{saving ? 'Saving…' : 'Save'}
		</button>
	</div>
{:else if error}
	<p class="hint error">{error}</p>
{/if}

<p class="current">{ai.text}</p>
{#if ai.ran_at}
	<p class="timestamp">Last updated {new Date(ai.ran_at).toLocaleString()}</p>
{/if}

{#if ai.history.length > 1}
	<h2>History</h2>
	<div class="history">
		{#each ai.history.slice(1) as run (run.ran_at)}
			<div class="run">
				<div class="timestamp">{new Date(run.ran_at).toLocaleString()}</div>
				<div>{run.text}</div>
			</div>
		{/each}
	</div>
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

	.actions {
		display: flex;
		gap: 0.5rem;
	}

	.regenerate,
	.read-aloud,
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
	}

	.timestamp {
		color: var(--color-text-muted);
		font-size: 0.9rem;
	}

	.history {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		margin-top: 1rem;
	}

	.run {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem;
	}
</style>
