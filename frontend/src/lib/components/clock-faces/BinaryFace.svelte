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
		gap: 0.4rem;
	}

	.column {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.25rem;
	}

	.dot {
		width: clamp(0.4rem, 8cqh, 0.7rem);
		height: clamp(0.4rem, 8cqh, 0.7rem);
		border-radius: 50%;
		border: 1.5px solid var(--color-border);
		background: transparent;
	}

	.dot.lit {
		background: var(--color-accent);
		border-color: var(--color-accent);
	}

	.label {
		font-size: 0.6rem;
		color: var(--color-text-muted);
		margin-top: 0.1rem;
	}

	.binary.large .dot {
		width: 1.1rem;
		height: 1.1rem;
		border-width: 2px;
	}

	.binary.large {
		gap: 0.9rem;
	}

	.binary.large .column {
		gap: 0.5rem;
	}

	.binary.large .label {
		font-size: 0.9rem;
	}
</style>
