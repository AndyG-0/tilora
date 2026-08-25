<script lang="ts">
	import { SCREENSAVER_COMPONENTS } from '$lib/widgetComponents';
	import { loadComponent } from '$lib/lazyWidgetComponent';
	import { isScreensaverWordyType, type TextAnimationStyle, type FlipboardPattern } from '$lib/screensaverTypes';
	import WordyScreensaver from './WordyScreensaver.svelte';
	import PhotoScreensaver from './PhotoScreensaver.svelte';
	import type { Component } from 'svelte';

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

	// eslint-disable-next-line @typescript-eslint/no-explicit-any -- see lazyWidgetComponent.ts
	let Visual = $state<Component<any> | undefined>(undefined);
	$effect(() => {
		const loader = SCREENSAVER_COMPONENTS[type];
		if (!loader) {
			Visual = undefined;
			return;
		}
		let cancelled = false;
		loadComponent(loader).then((component) => {
			if (!cancelled) Visual = component;
		});
		return () => {
			cancelled = true;
		};
	});
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
