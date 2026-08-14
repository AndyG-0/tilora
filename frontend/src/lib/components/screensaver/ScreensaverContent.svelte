<script lang="ts">
	import { SCREENSAVER_COMPONENTS } from '$lib/widgetComponents';
	import { isScreensaverWordyType, type TextAnimationStyle, type FlipboardPattern } from '$lib/screensaverTypes';
	import WordyScreensaver from './WordyScreensaver.svelte';
	import PhotoScreensaver from './PhotoScreensaver.svelte';

	let {
		id,
		type,
		data,
		textAnimationStyle,
		ledColor,
		textPauseSeconds,
		flipboardPattern,
	}: {
		id: string;
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
		{id}
		{type}
		{data}
		animationStyle={textAnimationStyle}
		{ledColor}
		{textPauseSeconds}
		{flipboardPattern}
	/>
{:else if type === 'photos'}
	<PhotoScreensaver data={data as never} {id} />
{:else if Visual}
	<Visual data={data as never} {ledColor} />
{/if}
