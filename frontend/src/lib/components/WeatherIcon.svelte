<script lang="ts">
	import { weatherIconKey } from '$lib/weatherIcons';

	let { code, isDay, label }: { code: number; isDay: boolean; label: string } = $props();

	const icon = $derived(weatherIconKey(code, isDay));
</script>

<svg class="weather-icon" viewBox="0 0 64 64" role="img" aria-label={label}>
	{#if icon === 'clear-day'}
		<circle cx="32" cy="32" r="14" class="sun" />
		{#each [0, 45, 90, 135, 180, 225, 270, 315] as angle (angle)}
			<line x1="32" y1="6" x2="32" y2="14" class="ray" transform="rotate({angle} 32 32)" />
		{/each}
	{:else if icon === 'clear-night'}
		<path d="M40 12a20 20 0 1 0 12 36 16 16 0 0 1-12-36z" class="moon" />
	{:else if icon === 'partly-cloudy-day'}
		<circle cx="24" cy="24" r="10" class="sun" />
		{#each [0, 45, 90, 135, 180, 225, 270, 315] as angle (angle)}
			<line x1="24" y1="4" x2="24" y2="10" class="ray" transform="rotate({angle} 24 24)" />
		{/each}
		<path d="M20 46a10 10 0 0 1 19.4-3.4A9 9 0 0 1 38 60H22a8 8 0 0 1-2-14z" class="cloud" />
	{:else if icon === 'partly-cloudy-night'}
		<path d="M38 10a14 14 0 1 0 8 25 11 11 0 0 1-8-25z" class="moon" />
		<path d="M20 46a10 10 0 0 1 19.4-3.4A9 9 0 0 1 38 60H22a8 8 0 0 1-2-14z" class="cloud" />
	{:else if icon === 'fog'}
		<path d="M16 30a10 10 0 0 1 19.4-3.4A9 9 0 0 1 34 44H18a8 8 0 0 1-2-14z" class="cloud" />
		<line x1="10" y1="50" x2="54" y2="50" class="fog-line" />
		<line x1="10" y1="57" x2="54" y2="57" class="fog-line" />
	{:else if icon === 'drizzle' || icon === 'rain' || icon === 'showers'}
		<path d="M16 26a10 10 0 0 1 19.4-3.4A9 9 0 0 1 34 40H18a8 8 0 0 1-2-14z" class="cloud" />
		{#each [20, 32, 44] as x (x)}
			<line x1={x} y1="46" x2={x - 4} y2="58" class="drop" />
		{/each}
	{:else if icon === 'snow'}
		<path d="M16 26a10 10 0 0 1 19.4-3.4A9 9 0 0 1 34 40H18a8 8 0 0 1-2-14z" class="cloud" />
		{#each [20, 32, 44] as x (x)}
			<g class="snowflake" transform="translate({x} 52)">
				<line x1="-5" y1="0" x2="5" y2="0" />
				<line x1="0" y1="-5" x2="0" y2="5" />
				<line x1="-3.5" y1="-3.5" x2="3.5" y2="3.5" />
				<line x1="-3.5" y1="3.5" x2="3.5" y2="-3.5" />
			</g>
		{/each}
	{:else if icon === 'thunderstorm'}
		<path d="M16 24a10 10 0 0 1 19.4-3.4A9 9 0 0 1 34 38H18a8 8 0 0 1-2-14z" class="cloud" />
		<path d="M30 40 22 54h8l-4 10 14-18h-8z" class="bolt" />
	{:else}
		<path d="M14 28a11 11 0 0 1 21.4-3.6A10 10 0 0 1 34 44H16a9 9 0 0 1-2-16z" class="cloud" />
	{/if}
</svg>

<style>
	.weather-icon {
		width: 100%;
		height: 100%;
		overflow: visible;
	}

	.sun {
		fill: var(--color-accent);
	}

	.ray {
		stroke: var(--color-accent);
		stroke-width: 3;
		stroke-linecap: round;
	}

	.moon {
		fill: var(--color-text-muted);
	}

	.cloud {
		fill: var(--color-text-muted);
	}

	.fog-line {
		stroke: var(--color-text-muted);
		stroke-width: 3;
		stroke-linecap: round;
	}

	.drop {
		stroke: var(--color-accent);
		stroke-width: 3;
		stroke-linecap: round;
	}

	.snowflake line {
		stroke: var(--color-text-muted);
		stroke-width: 2;
		stroke-linecap: round;
	}

	.bolt {
		fill: var(--color-accent);
	}
</style>
