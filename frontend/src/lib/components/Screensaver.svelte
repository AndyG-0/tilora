<script lang="ts">
	import { fade } from 'svelte/transition';
	import { api, describeFetchError, type FetchErrorKind, type ScreensaverSettings } from '$lib/api';
	import { widgets, widgetsLoadError } from '$lib/stores/widgets';
	import { device } from '$lib/stores/device';
	import { isScreensaverAllowedType } from '$lib/screensaverTypes';
	import ScreensaverContent from '$lib/components/screensaver/ScreensaverContent.svelte';
	import { getRotationIndex, setRotationIndex } from '$lib/stores/screensaverProgress';
	import { _ } from 'svelte-i18n';

	let { settings, ondismiss }: { settings: ScreensaverSettings; ondismiss: () => void } = $props();

	let index = $state(getRotationIndex());
	let detail = $state<Record<string, unknown> | null>(null);
	let currentId = $state<string | null>(null);
	let detailError = $state<FetchErrorKind | null>(null);
	let rotationTimer: ReturnType<typeof setInterval> | undefined;

	const currentWidget = $derived($widgets.find((w) => w.id === currentId));
	const isCurrentWidgetRenderable = $derived(currentWidget ? isScreensaverAllowedType(currentWidget.type) : false);

	// Drives the fallback panel shown whenever the widget above isn't ready to
	// render. 'loading' also covers the (usually instant) window while its
	// detail fetch is in flight, so a slow-but-working backend still names the
	// widget instead of a bare "Screensaver".
	type FallbackKind = 'none-configured' | 'list-unavailable' | 'all-missing' | 'detail-failed' | 'loading';
	const fallbackKind = $derived.by((): FallbackKind => {
		if (settings.widget_ids.length === 0) return 'none-configured';
		if (currentId && !currentWidget && $widgetsLoadError) return 'list-unavailable';
		if (!currentId) return 'all-missing';
		if (detailError) return 'detail-failed';
		return 'loading';
	});

	async function showCurrent() {
		const ids = settings.widget_ids;
		if (ids.length === 0) {
			currentId = null;
			detail = null;
			detailError = null;
			return;
		}

		if ($widgetsLoadError) {
			// The widget list itself failed to load, so no id can be verified
			// against it — show the one at the current rotation position as-is
			// rather than cycling through every id treating them all as removed.
			currentId = ids[index % ids.length];
			detail = null;
			detailError = null;
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
				detailError = null;
				try {
					detail = await api.widgetDetail(id);
				} catch (error) {
					detail = null;
					detailError = describeFetchError(error);
				}
				return;
			}
			index = (index + 1) % ids.length;
			setRotationIndex(index);
		}
		currentId = null;
		detail = null;
		detailError = null;
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
		<div class="empty">
			{#if fallbackKind === 'none-configured'}
				<div class="empty-message">{$_('screensaver.no_widgets')}</div>
			{:else if fallbackKind === 'list-unavailable'}
				<div class="empty-message">
					{$_('screensaver.list_unavailable', { values: { error: $_(`screensaver.error_${$widgetsLoadError}`) } })}
				</div>
				<div class="empty-detail">{$_('screensaver.widget_id_label', { values: { id: currentId } })}</div>
			{:else if fallbackKind === 'all-missing'}
				<div class="empty-message">{$_('screensaver.all_missing')}</div>
			{:else if fallbackKind === 'detail-failed'}
				<div class="empty-message">
					{$_('screensaver.detail_failed', {
						values: { name: currentWidget?.name, error: $_(`screensaver.error_${detailError}`) },
					})}
				</div>
				<div class="empty-detail">{currentWidget?.type}</div>
			{:else}
				<div class="empty-message">{$_('screensaver.loading', { values: { name: currentWidget?.name } })}</div>
			{/if}
			{#if fallbackKind !== 'loading' && $device?.name}
				<div class="empty-footer">{$_('screensaver.device_label', { values: { name: $device.name } })}</div>
			{/if}
		</div>
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
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 2rem;
		text-align: center;
		color: var(--color-text-muted);
	}

	.empty-message {
		font-size: 1.5rem;
	}

	.empty-detail {
		font-size: 1rem;
		opacity: 0.8;
	}

	.empty-footer {
		position: absolute;
		bottom: 1rem;
		left: 0;
		right: 0;
		font-size: 0.8rem;
		opacity: 0.6;
		text-align: center;
	}
</style>
