<script lang="ts">
	import { SCREENSAVER_COMPONENTS } from '$lib/widgetComponents';
	import { isScreensaverWordyType, type TextAnimationStyle, type FlipboardPattern } from '$lib/screensaverTypes';
	import WordyScreensaver from './WordyScreensaver.svelte';

	let {
		type,
		data,
		textAnimationStyle,
		ledColor,
		textPauseSeconds,
		flipboardPattern,
	}: {
		type: string;
		data: unknown;
		textAnimationStyle: TextAnimationStyle;
		ledColor?: string;
		textPauseSeconds?: number;
		flipboardPattern?: FlipboardPattern;
	} = $props();

	const Visual = $derived(SCREENSAVER_COMPONENTS[type]);
</script>

{#if isScreensaverWordyType(type)}
	<WordyScreensaver
		{type}
		{data}
		animationStyle={textAnimationStyle}
		{ledColor}
		{textPauseSeconds}
		{flipboardPattern}
	/>
{:else if Visual}
	<Visual data={data as never} {ledColor} />
{/if}
