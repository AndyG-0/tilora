<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api, type JellyfinItem } from '$lib/api';
	import JellyfinPlayer from '$lib/components/JellyfinPlayer.svelte';
	import { user } from '$lib/stores/user';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	interface JellyfinDetailData {
		connected: boolean;
		playback_mode: 'compatible' | 'compatible_video' | 'direct';
		content_mode: 'added' | 'played' | 'both';
		resume_available: boolean;
	}

	let { data: initialData }: { data: JellyfinDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from setContentMode's refetch.
	let jellyfin = $state(initialData);

	let path = $state<{ id: string; name: string }[]>([]);
	let items = $state<JellyfinItem[]>([]);
	let itemsLoading = $state(false);
	let itemsError = $state<string | null>(null);
	let playingItem = $state<JellyfinItem | null>(null);

	// Raw override for this device — {} means "inheriting the household
	// default," which is already reflected in jellyfin.playback_mode itself,
	// so this is only consulted to tell an override apart from a default.
	let deviceOverride = $state<Record<string, unknown>>({});
	let deviceSaving = $state(false);
	let deviceError = $state<string | null>(null);

	let contentModeSaving = $state(false);
	let contentModeError = $state<string | null>(null);

	const widgetId = $derived(page.params.id!);

	async function loadDeviceOverride() {
		try {
			deviceOverride = await api.getWidgetDeviceSettings(widgetId);
		} catch {
			deviceOverride = {};
		}
	}

	async function setDevicePlaybackMode(mode: 'compatible' | 'compatible_video' | 'direct') {
		deviceSaving = true;
		deviceError = null;
		try {
			deviceOverride = await api.updateWidgetDeviceSettings(widgetId, { playback_mode: mode });
			jellyfin = await api.widgetDetail<JellyfinDetailData>(widgetId);
		} catch {
			deviceError = get(_)('jellyfin.detail.save_device_override_error');
		} finally {
			deviceSaving = false;
		}
	}

	async function clearDevicePlaybackMode() {
		deviceSaving = true;
		deviceError = null;
		try {
			await api.clearWidgetDeviceSettings(widgetId);
			deviceOverride = {};
			jellyfin = await api.widgetDetail<JellyfinDetailData>(widgetId);
		} catch {
			deviceError = get(_)('jellyfin.detail.reset_device_override_error');
		} finally {
			deviceSaving = false;
		}
	}

	async function setContentMode(mode: 'added' | 'played' | 'both') {
		contentModeSaving = true;
		contentModeError = null;
		try {
			await api.updateWidgetSettings(widgetId, { content_mode: mode });
			jellyfin = await api.widgetDetail<JellyfinDetailData>(widgetId);
		} catch {
			contentModeError = get(_)('jellyfin.detail.save_content_mode_error');
		} finally {
			contentModeSaving = false;
		}
	}

	async function loadItems() {
		if (!jellyfin.connected) return;
		itemsLoading = true;
		itemsError = null;
		try {
			items = await api.jellyfinChildren(widgetId, path.at(-1)?.id);
		} catch {
			itemsError = get(_)('jellyfin.detail.load_items_error');
			items = [];
		} finally {
			itemsLoading = false;
		}
	}

	function openItem(item: JellyfinItem) {
		if (item.is_folder) {
			path = [...path, { id: item.id, name: item.name }];
			loadItems();
		} else {
			playingItem = item;
		}
	}

	function goToBreadcrumb(index: number) {
		path = path.slice(0, index + 1);
		loadItems();
	}

	function goToRoot() {
		path = [];
		loadItems();
	}

	$effect(() => {
		loadItems();
	});

	onMount(loadDeviceOverride);
</script>

<div class="header">
	<h1>Jellyfin</h1>
</div>

{#if !jellyfin.connected}
	<p class="hint">{$_('jellyfin.detail.not_connected_hint')}</p>
{:else}
	{#if $user?.role === 'admin'}
		<div class="device-settings">
			<h2>{$_('jellyfin.detail.tile_content_heading')}</h2>
			<div class="auth-mode">
				<button
					type="button"
					disabled={contentModeSaving}
					class:active={jellyfin.content_mode === 'added'}
					onclick={() => setContentMode('added')}
				>
					{$_('jellyfin.detail.content_added')}
				</button>
				<button
					type="button"
					disabled={contentModeSaving || !jellyfin.resume_available}
					class:active={jellyfin.content_mode === 'played'}
					onclick={() => setContentMode('played')}
				>
					{$_('jellyfin.detail.content_played')}
				</button>
				<button
					type="button"
					disabled={contentModeSaving || !jellyfin.resume_available}
					class:active={jellyfin.content_mode === 'both'}
					onclick={() => setContentMode('both')}
				>
					{$_('jellyfin.detail.content_both')}
				</button>
			</div>
			{#if !jellyfin.resume_available}
				<p class="hint">{$_('jellyfin.detail.resume_unavailable_hint')}</p>
			{/if}
			{#if contentModeError}
				<p class="hint error">{contentModeError}</p>
			{/if}
		</div>
	{/if}

	<div class="device-settings">
		<h2>{$_('jellyfin.detail.playback_heading')}</h2>
		<div class="auth-mode">
			<button
				type="button"
				disabled={deviceSaving}
				class:active={jellyfin.playback_mode === 'compatible'}
				onclick={() => setDevicePlaybackMode('compatible')}
			>
				{$_('jellyfin.detail.playback_compatible')}
			</button>
			<button
				type="button"
				disabled={deviceSaving}
				class:active={jellyfin.playback_mode === 'compatible_video'}
				onclick={() => setDevicePlaybackMode('compatible_video')}
			>
				{$_('jellyfin.detail.playback_compatible_video')}
			</button>
			<button
				type="button"
				disabled={deviceSaving}
				class:active={jellyfin.playback_mode === 'direct'}
				onclick={() => setDevicePlaybackMode('direct')}
			>
				{$_('jellyfin.detail.playback_direct')}
			</button>
		</div>
		<p class="hint">
			{#if deviceOverride.playback_mode}
				{$_('jellyfin.detail.override_active_hint')}
			{:else}
				{$_('jellyfin.detail.override_inactive_hint')}
			{/if}
		</p>
		{#if deviceOverride.playback_mode}
			<button class="clear" disabled={deviceSaving} onclick={clearDevicePlaybackMode}>
				{$_('jellyfin.detail.use_household_default')}
			</button>
		{/if}
		{#if deviceError}
			<p class="hint error">{deviceError}</p>
		{/if}
	</div>

	<div class="breadcrumbs">
		<button class="crumb" onclick={goToRoot}>{$_('jellyfin.detail.libraries_root')}</button>
		{#each path as segment, index (segment.id)}
			<span class="sep">/</span>
			<button class="crumb" onclick={() => goToBreadcrumb(index)}>{segment.name}</button>
		{/each}
	</div>

	{#if itemsLoading}
		<p class="hint">{$_('common.loading')}</p>
	{:else if itemsError}
		<p class="hint error">{itemsError}</p>
	{:else if items.length === 0}
		<p class="hint">{$_('jellyfin.detail.nothing_here')}</p>
	{:else}
		<div class="grid">
			{#each items as item (item.id)}
				<button class="movie" onclick={() => openItem(item)}>
					{#if item.has_poster}
						<img class="poster" src={api.jellyfinImageUrl(widgetId, item.id)} alt={item.name} />
					{:else}
						<div class="poster placeholder"></div>
					{/if}
					<div class="info">
						<h2>{item.name}</h2>
						<p class="meta">
							{#if item.year}{item.year}{/if}
							{#if item.runtime_minutes}
								· {$_('jellyfin.detail.runtime_minutes', { values: { minutes: item.runtime_minutes } })}
							{/if}
						</p>
						{#if item.overview}
							<p class="overview">{item.overview}</p>
						{/if}
					</div>
				</button>
			{/each}
		</div>
	{/if}
{/if}

{#if playingItem}
	<JellyfinPlayer
		src={api.jellyfinStreamUrl(widgetId, playingItem.id)}
		title={playingItem.name}
		onClose={() => (playingItem = null)}
	/>
{/if}

<style>
	.header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
	}

	.header h1 {
		margin: 0;
	}

	.device-settings {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		max-width: 30rem;
		margin: 1rem 0;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem;
	}

	.device-settings h2 {
		margin: 0;
		font-size: 1rem;
	}

	.auth-mode {
		display: flex;
		gap: 0.5rem;
	}

	.auth-mode button {
		flex: 1;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.auth-mode button.active {
		border-color: var(--color-accent);
		color: var(--color-accent);
	}

	.clear {
		align-self: flex-start;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.3rem 0.6rem;
		font-size: 0.85rem;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.breadcrumbs {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin: 1rem 0;
	}

	.crumb {
		background: none;
		border: none;
		color: var(--color-accent);
		cursor: pointer;
		padding: 0.15rem 0.25rem;
		font: inherit;
	}

	.sep {
		color: var(--color-text-muted);
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
		gap: 1rem;
	}

	.movie {
		display: flex;
		gap: 1rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1rem;
		text-align: left;
		color: inherit;
		cursor: pointer;
	}

	.movie:active {
		background: var(--color-surface-hover);
	}

	.poster {
		width: 6rem;
		height: 9rem;
		object-fit: cover;
		border-radius: 0.5rem;
		flex-shrink: 0;
	}

	.poster.placeholder {
		background: var(--color-border);
	}

	.info {
		min-width: 0;
	}

	.info h2 {
		margin: 0 0 0.25rem;
		font-size: 1.1rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.meta {
		color: var(--color-text-muted);
		margin: 0 0 0.5rem;
	}

	.overview {
		margin: 0;
		overflow: hidden;
		display: -webkit-box;
		-webkit-line-clamp: 3;
		-webkit-box-orient: vertical;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
