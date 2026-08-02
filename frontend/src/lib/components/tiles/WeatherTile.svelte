<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';

	interface WeatherSummary {
		location_name: string;
		temperature: number;
		condition: string;
	}

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<WeatherSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<WeatherSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);
</script>

<TileCard {widgetId}>
	{#if summary}
		<div class="location">{summary.location_name}</div>
		<div class="temp">{Math.round(summary.temperature)}°</div>
		<div class="condition">{summary.condition}</div>
	{:else}
		<div class="condition">Loading weather…</div>
	{/if}
</TileCard>

<style>
	.location {
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.temp {
		font-size: 3rem;
		font-weight: 600;
		line-height: 1.1;
	}

	.condition {
		color: var(--color-text-muted);
	}
</style>
