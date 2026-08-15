<script lang="ts">
	import { wallTime } from '$lib/clockTime';
	import { _ } from 'svelte-i18n';

	let { now, timezone, size }: { now: Date; timezone: string; size: 'tile' | 'detail' } = $props();

	const time = $derived(wallTime(now, timezone));
	const hourAngle = $derived(((time.hours % 12) + time.minutes / 60) * 30);
	const minuteAngle = $derived((time.minutes + time.seconds / 60) * 6);
	const secondAngle = $derived(time.seconds * 6);

	const ticks = Array.from({ length: 12 }, (_, i) => i * 30);
</script>

<svg
	class="analog"
	class:large={size === 'detail'}
	viewBox="0 0 200 200"
	role="img"
	aria-label={$_('clock.aria_analog')}
>
	<circle cx="100" cy="100" r="94" class="face" />
	{#each ticks as angle (angle)}
		<line
			x1="100"
			y1="10"
			x2="100"
			y2={angle % 90 === 0 ? 22 : 16}
			class="tick"
			class:major={angle % 90 === 0}
			transform="rotate({angle} 100 100)"
		/>
	{/each}
	<line x1="100" y1="100" x2="100" y2="55" class="hand hour" transform="rotate({hourAngle} 100 100)" />
	<line x1="100" y1="100" x2="100" y2="30" class="hand minute" transform="rotate({minuteAngle} 100 100)" />
	<line x1="100" y1="100" x2="100" y2="24" class="hand second" transform="rotate({secondAngle} 100 100)" />
	<circle cx="100" cy="100" r="4" class="pivot" />
</svg>

<style>
	.analog {
		display: block;
		width: 100%;
		height: 100%;
		max-width: 100%;
		max-height: 100%;
	}

	.analog.large {
		width: 14rem;
		height: 14rem;
	}

	.face {
		fill: var(--color-surface);
		stroke: var(--color-border);
		stroke-width: 3;
	}

	.tick {
		stroke: var(--color-text-muted);
		stroke-width: 2;
	}

	.tick.major {
		stroke: var(--color-text);
		stroke-width: 3;
	}

	.hand {
		stroke-linecap: round;
	}

	.hand.hour {
		stroke: var(--color-text);
		stroke-width: 6;
	}

	.hand.minute {
		stroke: var(--color-text);
		stroke-width: 4;
	}

	.hand.second {
		stroke: var(--color-accent);
		stroke-width: 2;
	}

	.pivot {
		fill: var(--color-accent);
	}
</style>
