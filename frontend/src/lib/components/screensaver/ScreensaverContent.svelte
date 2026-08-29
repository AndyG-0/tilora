<script lang="ts">
	import { SCREENSAVER_COMPONENTS } from '$lib/widgetComponents';
	import { loadComponent } from '$lib/lazyWidgetComponent';
	import { isScreensaverWordyType, type TextAnimationStyle, type FlipboardPattern } from '$lib/screensaverTypes';
	import WordyScreensaver from './WordyScreensaver.svelte';
	import PhotoScreensaver from './PhotoScreensaver.svelte';
	import type { Component } from 'svelte';
	import { _ } from 'svelte-i18n';

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
	let loadFailed = $state(false);
	$effect(() => {
		const loader = SCREENSAVER_COMPONENTS[type];
		if (!loader) {
			Visual = undefined;
			return;
		}
		let cancelled = false;
		loadFailed = false;
		loadComponent(loader)
			.then((component) => {
				if (!cancelled) Visual = component;
			})
			.catch(() => {
				if (!cancelled) loadFailed = true;
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
{:else if loadFailed}
	<div class="load-error">{$_('screensaver.display_failed', { values: { type } })}</div>
{/if}

<style>
	.load-error {
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--color-text-muted);
		font-size: 1.25rem;
		text-align: center;
		padding: 2rem;
	}
</style>
