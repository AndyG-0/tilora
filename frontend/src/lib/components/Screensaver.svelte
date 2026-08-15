<script lang="ts">
	import { fade } from 'svelte/transition';
	import { api, type ScreensaverSettings } from '$lib/api';
	import { widgets } from '$lib/stores/widgets';
	import { isScreensaverAllowedType } from '$lib/screensaverTypes';
	import ScreensaverContent from '$lib/components/screensaver/ScreensaverContent.svelte';
	import { getRotationIndex, setRotationIndex } from '$lib/stores/screensaverProgress';
	import { _ } from 'svelte-i18n';

	let { settings, ondismiss }: { settings: ScreensaverSettings; ondismiss: () => void } = $props();

	let index = $state(getRotationIndex());
	let detail = $state<Record<string, unknown> | null>(null);
	let currentId = $state<string | null>(null);
	let rotationTimer: ReturnType<typeof setInterval> | undefined;

	const currentWidget = $derived($widgets.find((w) => w.id === currentId));
	const isCurrentWidgetRenderable = $derived(currentWidget ? isScreensaverAllowedType(currentWidget.type) : false);

	async function showCurrent() {
		const ids = settings.widget_ids;
		if (ids.length === 0) {
			currentId = null;
			detail = null;
			return;
		}

		// Advance past any id that no longer resolves to a real, renderable
		// widget (removed since this was saved) instead of showing nothing —
		// tries at most once per id so a fully-stale list still stops looping.
		for (let attempts = 0; attempts < ids.length; attempts++) {
			const id = ids[index % ids.length];
			const widget = $widgets.find((w) => w.id === id);
			if (widget && isScreensaverAllowedType(widget.type)) {
				// Clear detail in the same tick as currentId so a render between
				// here and the await below never pairs the new widget's type
				// with the previous widget's (differently-shaped) detail data.
				currentId = id;
				detail = null;
				try {
					detail = await api.widgetDetail(id);
				} catch {
					detail = null;
				}
				return;
			}
			index = (index + 1) % ids.length;
			setRotationIndex(index);
		}
		currentId = null;
		detail = null;
	}

	function advance() {
		if (settings.widget_ids.length === 0) return;
		index = (index + 1) % settings.widget_ids.length;
		setRotationIndex(index);
		showCurrent();
	}

	$effect(() => {
		showCurrent();
		rotationTimer = setInterval(advance, settings.rotation_interval_seconds * 1000);
		return () => {
			if (rotationTimer !== undefined) clearInterval(rotationTimer);
		};
	});
</script>

<div class="screensaver" role="button" tabindex="0" onclick={ondismiss} onkeydown={ondismiss}>
	{#if currentWidget && isCurrentWidgetRenderable && detail}
		{#key currentId}
			<div class="content" transition:fade={{ duration: 400 }}>
				<!-- Shape is only known at runtime via each widget's own type, same as widget/[id]/+page.svelte. -->
				<ScreensaverContent
					id={currentId!}
					type={currentWidget.type}
					data={detail}
					textAnimationStyle={settings.text_animation_style}
					ledColor={settings.led_color}
					textPauseSeconds={settings.text_pause_seconds}
					flipboardPattern={settings.flipboard_pattern}
				/>
			</div>
		{/key}
	{:else}
		<div class="empty">{$_('screensaver.empty')}</div>
	{/if}
</div>

<style>
	.screensaver {
		position: fixed;
		inset: 0;
		z-index: 200;
		background: var(--color-bg);
		color: var(--color-text);
		overflow: hidden;
	}

	.content {
		position: absolute;
		inset: 0;
		padding: 2rem;
		overflow: auto;
	}

	.empty {
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--color-text-muted);
		font-size: 1.5rem;
	}
</style>
