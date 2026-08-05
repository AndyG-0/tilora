<script lang="ts">
	import DigitalFace from './DigitalFace.svelte';
	import AnalogFace from './AnalogFace.svelte';
	import BinaryFace from './BinaryFace.svelte';
	import WordFace from './WordFace.svelte';
	import MatrixFace from './MatrixFace.svelte';

	export type ClockStyle = 'digital' | 'analog' | 'binary' | 'word' | 'matrix';

	let {
		style,
		now,
		timezone,
		size = 'tile',
	}: { style: ClockStyle; now: Date; timezone: string; size?: 'tile' | 'detail' } = $props();
</script>

{#if style === 'analog'}
	<AnalogFace {now} {timezone} {size} />
{:else if style === 'binary'}
	<BinaryFace {now} {timezone} {size} />
{:else if style === 'word'}
	<WordFace {now} {timezone} {size} />
{:else if style === 'matrix'}
	<MatrixFace {now} {timezone} {size} />
{:else}
	<DigitalFace {now} {timezone} {size} />
{/if}
