<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import { renderMarkdown } from '$lib/markdown';
	import { scrollFade } from '$lib/scrollFade';
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
	<div class="widget">
		{#if summary}
			<div class="title">{summary.title}</div>
			<div class="scroll-wrap">
				<!-- eslint-disable-next-line svelte/no-at-html-tags -- renderMarkdown sanitizes with DOMPurify against an explicit tag/attribute allowlist before this reaches the DOM. -->
				<div class="text" use:scrollFade={summary}>{@html renderMarkdown(summary.text)}</div>
			</div>
		{:else}
			<div class="empty">{$_('ai_insights.tile.loading')}</div>
		{/if}
	</div>
</TileCard>

<style>
	.widget {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
	}

	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin-bottom: 0.5rem;
		flex-shrink: 0;
	}

	.scroll-wrap {
		position: relative;
		flex: 1;
		min-height: 0;
	}

	.scroll-wrap::before,
	.scroll-wrap::after {
		content: '';
		position: absolute;
		left: 0;
		right: 0;
		height: 1.25rem;
		pointer-events: none;
		opacity: 0;
		transition: opacity 0.15s ease;
		z-index: 1;
	}

	.scroll-wrap::before {
		top: 0;
		background: linear-gradient(to bottom, var(--color-surface), transparent);
	}

	.scroll-wrap::after {
		bottom: 0;
		background: linear-gradient(to top, var(--color-surface), transparent);
	}

	.scroll-wrap:global(.fade-top)::before {
		opacity: 1;
	}

	.scroll-wrap:global(.fade-bottom)::after {
		opacity: 1;
	}

	.text {
		font-size: 1.1rem;
		line-height: 1.4;
		height: 100%;
		overflow-y: auto;
		overflow-wrap: break-word;
	}

	.text::-webkit-scrollbar {
		width: 4px;
	}

	.text::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 2px;
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

	.text :global(h1),
	.text :global(h2),
	.text :global(h3) {
		margin: 0.5em 0 0.3em;
		font-size: 1.1rem;
	}

	.text :global(blockquote) {
		margin: 0 0 0.4em;
		padding-left: 0.75em;
		border-left: 3px solid var(--color-border);
		color: var(--color-text-muted);
	}

	.text :global(code) {
		background: var(--color-surface);
		border-radius: 0.25rem;
		padding: 0.1em 0.3em;
	}

	.empty {
		color: var(--color-text-muted);
	}
</style>
