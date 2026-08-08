<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { locale } from 'svelte-i18n';
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

	const weekday = $derived(
		new Intl.DateTimeFormat($locale ?? undefined, { timeZone: timezone, weekday: 'long' }).format(now),
	);
	const date = $derived(
		new Intl.DateTimeFormat($locale ?? undefined, {
			timeZone: timezone,
			month: 'long',
			day: 'numeric',
		}).format(now),
	);
	const year = $derived(
		new Intl.DateTimeFormat($locale ?? undefined, { timeZone: timezone, year: 'numeric' }).format(now),
	);
</script>

<TileCard {widgetId}>
	<div class="weekday">{weekday}</div>
	<div class="date">{date}</div>
	<div class="year">{year}</div>
</TileCard>

<style>
	.weekday {
		font-size: clamp(0.75rem, 10cqh, 1.1rem);
		color: var(--color-text-muted);
	}

	.date {
		font-size: clamp(1.4rem, 24cqh, 2.75rem);
		font-weight: 600;
		line-height: 1.15;
	}

	.year {
		font-size: clamp(0.9rem, 14cqh, 1.5rem);
		color: var(--color-text-muted);
	}
</style>
