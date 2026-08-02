<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';

	interface MessageSummary {
		title: string;
		text: string;
	}

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<MessageSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<MessageSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);
</script>

<TileCard {widgetId}>
	{#if summary}
		{#if summary.title}
			<div class="title">{summary.title}</div>
		{/if}
		<div class="text">{summary.text}</div>
	{:else}
		<div class="text">Loading…</div>
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
		white-space: pre-wrap;
		overflow-wrap: break-word;
	}
</style>
