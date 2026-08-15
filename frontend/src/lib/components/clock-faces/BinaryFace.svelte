<script lang="ts">
	import { wallTime } from '$lib/clockTime';
	import { _ } from 'svelte-i18n';

	let { now, timezone, size }: { now: Date; timezone: string; size: 'tile' | 'detail' } = $props();

	const time = $derived(wallTime(now, timezone));

	// BCD binary clock: each of H/M/S splits into a tens digit (0-9, only
	// ever 0-2/0-5 in practice) and a ones digit (0-9), each shown as 4 bits
	// (MSB first) so every column uses the same fixed height.
	function bits(digit: number): boolean[] {
		return [8, 4, 2, 1].map((place) => (digit & place) !== 0);
	}

	function digits(value: number): [number, number] {
		return [Math.floor(value / 10), value % 10];
	}

	const columns = $derived(
		([...digits(time.hours), ...digits(time.minutes), ...digits(time.seconds)] as number[]).map(bits),
	);
	const groupLabels = ['H', 'H', 'M', 'M', 'S', 'S'];
</script>

<div class="binary" class:large={size === 'detail'} role="img" aria-label={$_('clock.aria_binary')}>
	{#each columns as column, colIndex (colIndex)}
		<div class="column">
			{#each column as bit, rowIndex (rowIndex)}
				<span class="dot" class:lit={bit}></span>
			{/each}
			<span class="label">{groupLabels[colIndex]}</span>
		</div>
	{/each}
</div>

<style>
	.binary {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: clamp(0.35rem, min(3.5cqw, 3.5cqh), 1.25rem);
	}

	.column {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: clamp(0.2rem, min(2.5cqw, 2.5cqh), 0.8rem);
	}

	.binary:not(.large) .column:nth-child(2),
	.binary:not(.large) .column:nth-child(4) {
		margin-right: clamp(0.25rem, min(2.5cqw, 2.5cqh), 0.9rem);
	}

	.dot {
		width: clamp(0.55rem, min(10cqw, 14cqh), 2.25rem);
		height: clamp(0.55rem, min(10cqw, 14cqh), 2.25rem);
		border-radius: 50%;
		border: clamp(1.5px, 0.4cqmin, 3px) solid var(--color-border);
		background: transparent;
		box-sizing: border-box;
	}

	.dot.lit {
		background: var(--color-accent);
		border-color: var(--color-accent);
	}

	.label {
		font-size: clamp(0.6rem, min(5cqw, 6cqh), 1.1rem);
		font-weight: 600;
		color: var(--color-text-muted);
		margin-top: clamp(0.1rem, 1cqmin, 0.35rem);
		line-height: 1;
	}

	.binary.large {
		gap: 0.9rem;
	}

	.binary.large .column {
		gap: 0.5rem;
	}

	.binary.large .column:nth-child(2),
	.binary.large .column:nth-child(4) {
		margin-right: 0.6rem;
	}

	.binary.large .dot {
		width: 1.1rem;
		height: 1.1rem;
		border-width: 2px;
	}

	.binary.large .label {
		font-size: 0.9rem;
		margin-top: 0.1rem;
	}
</style>
