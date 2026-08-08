<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import { renderMarkdown } from '$lib/markdown';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	interface AISummary {
		title: string;
		text: string;
		ran_at: string | null;
	}

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<AISummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<AISummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);
</script>

<TileCard {widgetId}>
	{#if summary}
		<div class="title">{summary.title}</div>
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- renderMarkdown sanitizes with DOMPurify against an explicit tag/attribute allowlist before this reaches the DOM. -->
		<div class="text">{@html renderMarkdown(summary.text)}</div>
	{:else}
		<div class="text">{$_('ai_insights.tile.loading')}</div>
	{/if}
</TileCard>

<style>
	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin-bottom: 0.5rem;
	}

	.text {
		font-size: 1.1rem;
		line-height: 1.4;
	}

	/* {@html}-injected markdown sits outside Svelte's scoped-style tree. */
	.text :global(p) {
		margin: 0 0 0.4em;
	}

	.text :global(p:last-child) {
		margin-bottom: 0;
	}

	.text :global(ul),
	.text :global(ol) {
		margin: 0 0 0.4em;
		padding-left: 1.2em;
	}

	.text :global(code) {
		background: var(--color-surface);
		border-radius: 0.25rem;
		padding: 0.1em 0.3em;
	}
</style>
