<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';

	interface ClockSummary {
		timezone: string;
	}

	let { widgetId }: { widgetId: string } = $props();

	let timezone = $state('UTC');
	let now = $state(new Date());

	onMount(() => {
		api
			.widgetSummary<ClockSummary>(widgetId)
			.then((summary) => (timezone = summary.timezone))
			.catch(() => {
				// keep the UTC fallback
			});

		// The timezone rarely changes, so there's no need to poll the
		// backend — just tick the clock face locally every second.
		const interval = setInterval(() => (now = new Date()), 1000);
		return () => clearInterval(interval);
	});

	const formatted = $derived(
		new Intl.DateTimeFormat(undefined, {
			timeZone: timezone,
			hour: 'numeric',
			minute: '2-digit',
			second: '2-digit',
		}).format(now),
	);
</script>

<TileCard {widgetId}>
	<div class="time">{formatted}</div>
</TileCard>

<style>
	.time {
		font-size: 2.5rem;
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}
</style>
