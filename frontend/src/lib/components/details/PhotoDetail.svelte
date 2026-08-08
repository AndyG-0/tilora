<script lang="ts">
	import { onMount } from 'svelte';
	import { env } from '$env/dynamic/public';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { logger } from '$lib/logger';
	import { resolveSwipe } from '$lib/tabNavigation';
	import { user } from '$lib/stores/user';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	interface Photo {
		filename: string;
		url: string;
	}

	interface PhotoDetailData {
		provider?: 'local' | 'icloud_shared' | 'icloud_private' | 'immich';
		count: number;
		interval_seconds: number;
		photos: Photo[];
		directory?: string | null;
		recursive?: boolean;
		album_token?: string | null;
		connected?: boolean;
		immich_base_url?: string | null;
		has_immich_api_key?: boolean;
		immich_album_id?: string | null;
		indexing?: boolean;
		index_error?: string;
	}

	let { data: initialData }: { data: PhotoDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from save/connect refetches.
	let photoData = $state(initialData);

	let index = $state(0);
	let autoAdvanceTimer: ReturnType<typeof setInterval> | null = null;

	function clearAutoAdvance() {
		if (autoAdvanceTimer) clearInterval(autoAdvanceTimer);
		autoAdvanceTimer = null;
	}

	function restartAutoAdvance() {
		clearAutoAdvance();
		if (photoData.photos.length <= 1) return;
		autoAdvanceTimer = setInterval(() => {
			index = (index + 1) % photoData.photos.length;
		}, photoData.interval_seconds * 1000);
	}

	function goToPhoto(newIndex: number) {
		const count = photoData.photos.length;
		if (count === 0) return;
		index = ((newIndex % count) + count) % count;
		restartAutoAdvance();
	}

	function nextPhoto() {
		goToPhoto(index + 1);
	}

	function prevPhoto() {
		goToPhoto(index - 1);
	}

	onMount(() => {
		restartAutoAdvance();
		return clearAutoAdvance;
	});

	function onPhotoKeydown(event: KeyboardEvent) {
		if (event.target instanceof HTMLInputElement) return;
		if (photoData.photos.length === 0) return;
		if (event.key === 'ArrowRight') nextPhoto();
		else if (event.key === 'ArrowLeft') prevPhoto();
	}

	let touchStartX = 0;
	let touchStartY = 0;

	function onSlideTouchStart(event: TouchEvent) {
		touchStartX = event.touches[0].clientX;
		touchStartY = event.touches[0].clientY;
	}

	function onSlideTouchEnd(event: TouchEvent) {
		const deltaX = event.changedTouches[0].clientX - touchStartX;
		const deltaY = event.changedTouches[0].clientY - touchStartY;
		const direction = resolveSwipe(deltaX, deltaY);
		if (direction === 1) nextPhoto();
		else if (direction === -1) prevPhoto();
	}

	// Preload neighboring photos so manual navigation doesn't stutter
	// waiting on a fresh fetch — only the current index's <img> is in the
	// DOM otherwise. $effect only runs in the browser, not during SSR.
	$effect(() => {
		const count = photoData.photos.length;
		if (count <= 1) return;
		const neighborUrls = [photoData.photos[(index + 1) % count].url, photoData.photos[(index - 1 + count) % count].url];
		for (const url of neighborUrls) {
			const img = new Image();
			img.src = `${env.PUBLIC_API_BASE_URL}${url}`;
		}
	});

	// --- provider switcher ---
	const PROVIDER_LABELS = $derived<Record<string, string>>({
		local: $_('photos.detail.provider_local'),
		icloud_shared: $_('photos.detail.provider_icloud_shared'),
		icloud_private: $_('photos.detail.provider_icloud_private'),
		immich: $_('photos.detail.provider_immich'),
	});
	let changingProvider = $state(false);
	let providerError = $state<string | null>(null);

	async function changeProvider(newProvider: string) {
		if (!(newProvider in PROVIDER_LABELS) || newProvider === photoData.provider) return;
		changingProvider = true;
		providerError = null;
		try {
			await api.updateWidgetSettings(page.params.id!, { provider: newProvider });
			photoData = await api.widgetDetail<PhotoDetailData>(page.params.id!);
			index = 0;
			editingDirectory = false;
			editingAlbumLink = false;
			editingImmich = false;
		} catch (err) {
			logger.error('Failed to switch photo provider', err);
			providerError = get(_)('photos.detail.switch_provider_error');
		} finally {
			changingProvider = false;
		}
	}

	// --- local: editable folder path + recursive toggle ---
	let editingDirectory = $state(false);
	let directoryInput = $state('');
	let recursiveInput = $state(false);
	let savingDirectory = $state(false);
	let directoryError = $state<string | null>(null);

	function toggleEditDirectory() {
		editingDirectory = !editingDirectory;
		if (editingDirectory) {
			directoryInput = photoData.directory ?? '';
			recursiveInput = photoData.recursive ?? false;
		}
		directoryError = null;
	}

	async function saveDirectory() {
		savingDirectory = true;
		directoryError = null;
		try {
			await api.updateWidgetSettings(page.params.id!, {
				directory: directoryInput,
				recursive: recursiveInput,
			});
			photoData = await api.widgetDetail<PhotoDetailData>(page.params.id!);
			index = 0;
			editingDirectory = false;
		} catch (err) {
			logger.error('Failed to save photo directory settings', err);
			directoryError = get(_)('photos.detail.save_folder_error');
		} finally {
			savingDirectory = false;
		}
	}

	// --- icloud_shared: editable album link ---
	let editingAlbumLink = $state(false);
	let albumTokenInput = $state('');
	let savingAlbumLink = $state(false);
	let albumLinkError = $state<string | null>(null);

	function toggleEditAlbumLink() {
		editingAlbumLink = !editingAlbumLink;
		if (editingAlbumLink) albumTokenInput = photoData.album_token ?? '';
		albumLinkError = null;
	}

	async function saveAlbumLink() {
		savingAlbumLink = true;
		albumLinkError = null;
		try {
			await api.updateWidgetSettings(page.params.id!, { album_token: albumTokenInput });
			photoData = await api.widgetDetail<PhotoDetailData>(page.params.id!);
			index = 0;
			editingAlbumLink = false;
		} catch {
			albumLinkError = get(_)('photos.detail.save_album_link_error');
		} finally {
			savingAlbumLink = false;
		}
	}

	// --- immich: editable base URL / API key / album ID ---
	let editingImmich = $state(false);
	let immichBaseUrlInput = $state('');
	let immichApiKeyInput = $state('');
	let immichAlbumIdInput = $state('');
	let savingImmich = $state(false);
	let immichError = $state<string | null>(null);

	function toggleEditImmich() {
		editingImmich = !editingImmich;
		if (editingImmich) {
			immichBaseUrlInput = photoData.immich_base_url ?? '';
			// Never pre-fill the real key — it's write-only. An empty field on
			// save means "leave the stored key unchanged" (same convention as
			// SteamDetail's api_key field).
			immichApiKeyInput = '';
			immichAlbumIdInput = photoData.immich_album_id ?? '';
		}
		immichError = null;
	}

	async function saveImmich() {
		savingImmich = true;
		immichError = null;
		try {
			const settings: Record<string, unknown> = {
				base_url: immichBaseUrlInput,
				album_id: immichAlbumIdInput,
			};
			if (immichApiKeyInput) settings.api_key = immichApiKeyInput;
			await api.updateWidgetSettings(page.params.id!, settings);
			photoData = await api.widgetDetail<PhotoDetailData>(page.params.id!);
			index = 0;
			editingImmich = false;
		} catch {
			immichError = get(_)('photos.detail.save_immich_error');
		} finally {
			savingImmich = false;
		}
	}

	// --- icloud_private: connect + 2FA ---
	let connecting = $state(false);
	let awaiting2fa = $state(false);
	let codeInput = $state('');
	let connectError = $state<string | null>(null);

	async function startConnect() {
		connecting = true;
		connectError = null;
		try {
			const result = await api.startIcloudAuth();
			if (result.requires_2fa) {
				awaiting2fa = true;
			} else if (result.connected) {
				photoData = await api.widgetDetail<PhotoDetailData>(page.params.id!);
			} else {
				connectError = get(_)('photos.detail.connect_error');
			}
		} catch (err) {
			logger.error('Failed to start iCloud auth', err);
			connectError = get(_)('photos.detail.connect_error');
		} finally {
			connecting = false;
		}
	}

	async function verifyCode() {
		connecting = true;
		connectError = null;
		try {
			const result = await api.verifyIcloudAuth(codeInput);
			if (result.connected) {
				awaiting2fa = false;
				codeInput = '';
				photoData = await api.widgetDetail<PhotoDetailData>(page.params.id!);
			} else {
				connectError = get(_)('photos.detail.incorrect_code_error');
			}
		} catch {
			connectError = get(_)('photos.detail.verify_code_error');
		} finally {
			connecting = false;
		}
	}
</script>

<svelte:window onkeydown={onPhotoKeydown} />

{#if $user?.role === 'admin'}
	<div class="header">
		<h1>Photos</h1>
		<select
			class="provider-select"
			aria-label={$_('photos.detail.source_label')}
			value={photoData.provider}
			disabled={changingProvider}
			onchange={(e) => changeProvider(e.currentTarget.value)}
		>
			{#each Object.entries(PROVIDER_LABELS) as [id, label] (id)}
				<option value={id}>{label}</option>
			{/each}
		</select>
		{#if photoData.provider === 'local'}
			<button class="manage" onclick={toggleEditDirectory}>
				{editingDirectory
					? $_('common.cancel')
					: photoData.directory
						? $_('photos.detail.change_folder')
						: $_('photos.detail.set_folder')}
			</button>
		{:else if photoData.provider === 'icloud_shared'}
			<button class="manage" onclick={toggleEditAlbumLink}>
				{editingAlbumLink
					? $_('common.cancel')
					: photoData.album_token
						? $_('photos.detail.change_album_link')
						: $_('photos.detail.set_album_link')}
			</button>
		{:else if photoData.provider === 'immich'}
			<button class="manage" onclick={toggleEditImmich}>
				{editingImmich
					? $_('common.cancel')
					: photoData.immich_base_url
						? $_('photos.detail.change_immich_settings')
						: $_('photos.detail.set_up_immich')}
			</button>
		{/if}
	</div>

	{#if providerError}
		<p class="hint error">{providerError}</p>
	{/if}

	{#if editingDirectory}
		<div class="album-link-form">
			<input type="text" bind:value={directoryInput} placeholder={$_('photos.detail.folder_placeholder')} />
			<label class="checkbox-label">
				<input type="checkbox" bind:checked={recursiveInput} />
				{$_('photos.detail.include_subfolders')}
			</label>
			<button disabled={savingDirectory} onclick={saveDirectory}>
				{savingDirectory ? $_('common.saving') : $_('common.save')}
			</button>
			{#if directoryError}
				<p class="hint error">{directoryError}</p>
			{/if}
		</div>
	{/if}

	{#if editingAlbumLink}
		<div class="album-link-form">
			<input type="text" bind:value={albumTokenInput} placeholder={$_('photos.detail.album_link_placeholder')} />
			<button disabled={savingAlbumLink} onclick={saveAlbumLink}>
				{savingAlbumLink ? $_('common.saving') : $_('common.save')}
			</button>
			{#if albumLinkError}
				<p class="hint error">{albumLinkError}</p>
			{/if}
		</div>
	{/if}

	{#if editingImmich}
		<div class="album-link-form">
			<input
				type="text"
				bind:value={immichBaseUrlInput}
				placeholder={$_('photos.detail.immich_base_url_placeholder')}
			/>
			<input
				type="password"
				bind:value={immichApiKeyInput}
				placeholder={photoData.has_immich_api_key
					? $_('common.password_set_hint')
					: $_('photos.detail.immich_api_key_placeholder')}
			/>
			<input
				type="text"
				bind:value={immichAlbumIdInput}
				placeholder={$_('photos.detail.immich_album_id_placeholder')}
			/>
			<button disabled={savingImmich} onclick={saveImmich}>
				{savingImmich ? $_('common.saving') : $_('common.save')}
			</button>
			{#if immichError}
				<p class="hint error">{immichError}</p>
			{/if}
		</div>
	{/if}
{:else}
	<div class="header">
		<h1>Photos</h1>
	</div>
{/if}

{#if photoData.provider === 'icloud_shared'}
	<p class="hint warning">{$_('photos.detail.shared_album_warning')}</p>
{/if}

{#if photoData.provider === 'icloud_private' && !photoData.connected}
	<div class="connect">
		{#if awaiting2fa}
			<p class="hint">{$_('photos.detail.verify_code_hint')}</p>
			<div class="album-link-form">
				<input type="text" inputmode="numeric" bind:value={codeInput} placeholder="123456" />
				<button disabled={connecting} onclick={verifyCode}>
					{connecting ? $_('photos.detail.verifying') : $_('photos.detail.verify')}
				</button>
			</div>
		{:else}
			<p class="hint">{$_('photos.detail.connect_hint')}</p>
			<button class="connect-button" disabled={connecting} onclick={startConnect}>
				{connecting ? $_('photos.detail.connecting') : $_('photos.detail.connect_icloud')}
			</button>
			<p class="hint">
				{$_('photos.detail.settings_hint_prefix')}<a href="/settings">{$_('photos.detail.settings_hint_link')}</a>{$_(
					'photos.detail.settings_hint_suffix',
				)}
			</p>
		{/if}
		{#if connectError}
			<p class="hint error">{connectError}</p>
		{/if}
	</div>
{:else if photoData.photos.length > 0}
	<div class="slideshow" role="presentation" ontouchstart={onSlideTouchStart} ontouchend={onSlideTouchEnd}>
		{#if photoData.photos.length > 1}
			<button class="nav prev" aria-label={$_('photos.detail.previous_photo')} onclick={prevPhoto}>‹</button>
		{/if}
		<img src={`${env.PUBLIC_API_BASE_URL}${photoData.photos[index].url}`} alt={photoData.photos[index].filename} />
		{#if photoData.photos.length > 1}
			<button class="nav next" aria-label={$_('photos.detail.next_photo')} onclick={nextPhoto}>›</button>
		{/if}
	</div>
	<p class="caption">{$_('photos.detail.caption', { values: { index: index + 1, count: photoData.photos.length } })}</p>
{:else if photoData.indexing}
	<p class="hint">{$_('photos.tile.indexing')}</p>
{:else if photoData.index_error}
	<p class="hint error">{photoData.index_error}</p>
{:else}
	<p class="hint">{$_('photos.detail.no_photos')}</p>
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

	.manage {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.provider-select {
		font: inherit;
		padding: 0.4rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.provider-select:disabled {
		opacity: 0.6;
		cursor: default;
	}

	.album-link-form {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.5rem;
		margin: 1rem 0;
		max-width: 24rem;
	}

	.album-link-form input {
		width: 100%;
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.album-link-form button {
		background: var(--color-accent);
		color: var(--color-on-accent);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.checkbox-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--color-text);
		font-size: 0.9rem;
	}

	.checkbox-label input[type='checkbox'] {
		width: auto;
	}

	.album-link-form button:disabled {
		opacity: 0.6;
		cursor: default;
	}

	.connect {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.75rem;
	}

	.connect-button {
		display: inline-block;
		background: var(--color-accent);
		color: var(--color-on-accent);
		border: none;
		border-radius: 0.5rem;
		padding: 0.6rem 1rem;
		cursor: pointer;
	}

	.connect-button:disabled {
		opacity: 0.6;
		cursor: default;
	}

	.slideshow {
		position: relative;
		display: flex;
		justify-content: center;
	}

	.slideshow img {
		max-width: 100%;
		max-height: 70vh;
		border-radius: 1rem;
		object-fit: contain;
	}

	.nav {
		position: absolute;
		top: 50%;
		transform: translateY(-50%);
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-accent);
		font-size: 1.5rem;
		line-height: 1;
		cursor: pointer;
	}

	.nav.prev {
		left: 0.5rem;
	}

	.nav.next {
		right: 0.5rem;
	}

	.caption {
		text-align: center;
		color: var(--color-text-muted);
		margin-top: 1rem;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint a {
		color: var(--color-accent);
	}

	.hint.warning {
		color: var(--color-warning);
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
