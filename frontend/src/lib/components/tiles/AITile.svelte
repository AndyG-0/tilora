<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';

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
		<div class="text">{summary.text}</div>
	{:else}
		<div class="text">Loading briefing…</div>
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
</style>
