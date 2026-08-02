<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';

	interface DateSummary {
		timezone: string;
	}

	let { widgetId }: { widgetId: string } = $props();

	let timezone = $state('UTC');
	let now = $state(new Date());

	onMount(() => {
		api
			.widgetSummary<DateSummary>(widgetId)
			.then((summary) => (timezone = summary.timezone))
			.catch(() => {
				// keep the UTC fallback
			});

		// Cheap insurance against the date rolling over at midnight while
		// the tile is showing — no need to fetch from the backend for this.
		const interval = setInterval(() => (now = new Date()), 60_000);
		return () => clearInterval(interval);
	});

	const weekday = $derived(new Intl.DateTimeFormat(undefined, { timeZone: timezone, weekday: 'long' }).format(now));
	const date = $derived(
		new Intl.DateTimeFormat(undefined, {
			timeZone: timezone,
			month: 'long',
			day: 'numeric',
		}).format(now),
	);
</script>

<TileCard {widgetId}>
	<div class="weekday">{weekday}</div>
	<div class="date">{date}</div>
</TileCard>

<style>
	.weekday {
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.date {
		font-size: 1.8rem;
		font-weight: 600;
	}
</style>
