<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import ClockFace, { type ClockStyle } from '$lib/components/clock-faces/ClockFace.svelte';

	interface ClockSummary {
		timezone: string;
		style: ClockStyle;
	}

	let { widgetId }: { widgetId: string } = $props();

	let timezone = $state('UTC');
	let style = $state<ClockStyle>('digital');
	let now = $state(new Date());

	onMount(() => {
		api
			.widgetSummary<ClockSummary>(widgetId)
			.then((summary) => {
				timezone = summary.timezone;
				style = summary.style;
			})
			.catch(() => {
				// keep the digital/UTC fallback
			});

		// The timezone/style rarely change, so there's no need to poll the
		// backend — just tick the clock face locally every second.
		const interval = setInterval(() => (now = new Date()), 1000);
		return () => clearInterval(interval);
	});
</script>

<TileCard {widgetId}>
	<div class="clock-tile">
		<ClockFace {style} {now} {timezone} size="tile" />
	</div>
</TileCard>

<style>
	.clock-tile {
		width: 100%;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
	}
</style>
