<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { renderMarkdown } from '$lib/markdown';
	import { isSpeechSynthesisSupported, speak } from '$lib/speech';
	import { voiceSelection } from '$lib/stores/voice';
	import { _, locale } from 'svelte-i18n';
	import { get } from 'svelte/store';

	interface AIRun {
		ran_at: string;
		text: string;
	}

	interface AITopic {
		id: string;
		name: string;
	}

	interface AIDetailData {
		title: string;
		text: string;
		ran_at: string | null;
		history: AIRun[];
		prompt: string;
		cron: string;
		topics: string[];
		language: string;
	}

	let { data: initialData }: { data: AIDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings/regenerate's refetch.
	let ai = $state(initialData);

	let editingPrompt = $state(false);
	let promptInput = $state('');
	let topicsInput = $state<string[]>([]);
	let languageInput = $state('en');
	let topicCatalog = $state<AITopic[]>([]);
	let saving = $state(false);
	let regenerating = $state(false);
	let error = $state<string | null>(null);

	async function openEditor() {
		promptInput = ai.prompt;
		topicsInput = [...ai.topics];
		languageInput = ai.language;
		editingPrompt = true;
		try {
			topicCatalog = await api.assistantTopics();
		} catch {
			topicCatalog = [];
		}
	}

	function toggleTopic(id: string) {
		topicsInput = topicsInput.includes(id) ? topicsInput.filter((t) => t !== id) : [...topicsInput, id];
	}

	async function savePrompt() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(page.params.id!, {
				prompt: promptInput,
				topics: topicsInput,
				language: languageInput,
			});
			ai = await api.widgetDetail<AIDetailData>(page.params.id!);
			editingPrompt = false;
		} catch {
			error = get(_)('ai_insights.detail.save_error');
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
			error = get(_)('ai_insights.detail.regenerate_error');
		} finally {
			regenerating = false;
		}
	}
</script>

<div class="header">
	<h1>{ai.title}</h1>
	<div class="actions">
		<button class="regenerate" disabled={regenerating} onclick={regenerateNow}>
			{regenerating ? $_('ai_insights.detail.regenerating') : $_('ai_insights.detail.regenerate_now')}
		</button>
		{#if isSpeechSynthesisSupported()}
			<button class="read-aloud" onclick={() => speak(ai.text, $voiceSelection)}>
				{$_('ai_insights.detail.read_aloud')}
			</button>
		{/if}
		<button class="edit-settings" onclick={() => (editingPrompt ? (editingPrompt = false) : openEditor())}>
			{editingPrompt ? $_('common.cancel') : $_('ai_insights.detail.edit_prompt')}
		</button>
	</div>
</div>

{#if editingPrompt}
	<div class="settings-form">
		<label>
			{$_('ai_insights.detail.prompt_label')}
			<textarea rows="6" bind:value={promptInput}></textarea>
		</label>

		<div class="topics">
			<span class="topics-label">{$_('ai_insights.detail.topics_label')}</span>
			<p class="hint">{$_('ai_insights.detail.topics_hint')}</p>
			<div class="topics-list">
				{#each topicCatalog as topic (topic.id)}
					<label class="topic">
						<input type="checkbox" checked={topicsInput.includes(topic.id)} onchange={() => toggleTopic(topic.id)} />
						{topic.name}
					</label>
				{/each}
			</div>
		</div>

		<label>
			{$_('ai_insights.detail.language_label')}
			<select bind:value={languageInput}>
				<option value="en">English</option>
				<option value="es">Español</option>
				<option value="fr">Français</option>
				<option value="de">Deutsch</option>
			</select>
		</label>

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={savePrompt}>
			{saving ? $_('common.saving') : $_('common.save')}
		</button>
	</div>
{:else if error}
	<p class="hint error">{error}</p>
{/if}

<!-- eslint-disable-next-line svelte/no-at-html-tags -- renderMarkdown sanitizes with DOMPurify against an explicit tag/attribute allowlist before this reaches the DOM. -->
<div class="current">{@html renderMarkdown(ai.text)}</div>
{#if ai.ran_at}
	<p class="timestamp">
		{$_('ai_insights.detail.last_updated', {
			values: { date: new Date(ai.ran_at).toLocaleString(get(locale) ?? undefined) },
		})}
	</p>
{/if}

{#if ai.history.length > 1}
	<h2>{$_('ai_insights.detail.history_heading')}</h2>
	<div class="history">
		{#each ai.history.slice(1) as run (run.ran_at)}
			<div class="run">
				<div class="timestamp">{new Date(run.ran_at).toLocaleString(get(locale) ?? undefined)}</div>
				<!-- eslint-disable-next-line svelte/no-at-html-tags -- renderMarkdown sanitizes with DOMPurify against an explicit tag/attribute allowlist before this reaches the DOM. -->
				<div class="run-text">{@html renderMarkdown(run.text)}</div>
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

	.topics-label {
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.topics .hint {
		font-size: 0.8rem;
		margin: 0.15rem 0 0.5rem;
	}

	.topics-list {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1rem;
	}

	.settings-form label.topic {
		flex-direction: row;
		align-items: center;
		gap: 0.4rem;
		width: auto;
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

	/* {@html}-injected markdown sits outside Svelte's scoped-style tree. */
	.current :global(p),
	.run-text :global(p) {
		margin: 0 0 0.6em;
	}

	.current :global(p:last-child),
	.run-text :global(p:last-child) {
		margin-bottom: 0;
	}

	.current :global(ul),
	.current :global(ol),
	.run-text :global(ul),
	.run-text :global(ol) {
		margin: 0 0 0.6em;
		padding-left: 1.4em;
	}

	.current :global(h1),
	.current :global(h2),
	.current :global(h3),
	.run-text :global(h1),
	.run-text :global(h2),
	.run-text :global(h3) {
		margin: 0.75em 0 0.4em;
	}

	.current :global(blockquote),
	.run-text :global(blockquote) {
		margin: 0 0 0.6em;
		padding-left: 0.75em;
		border-left: 3px solid var(--color-border);
		color: var(--color-text-muted);
	}

	.current :global(code),
	.run-text :global(code) {
		background: var(--color-surface);
		border-radius: 0.25rem;
		padding: 0.1em 0.3em;
	}

	.current :global(pre),
	.run-text :global(pre) {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.75em;
		overflow-x: auto;
	}

	.current :global(pre code),
	.run-text :global(pre code) {
		background: none;
		padding: 0;
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
