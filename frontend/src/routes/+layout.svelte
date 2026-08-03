<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import favicon from '$lib/assets/favicon.svg';
	import '../app.css';
	// Imported for its side effect: subscribing keeps document.documentElement's
	// data-theme attribute (and localStorage) in sync with the store.
	import { loadThemeFromServer } from '$lib/stores/theme';
	import { device, ensureDevice, renameDevice } from '$lib/stores/device';
	import { user, userLoaded, loadCurrentUser } from '$lib/stores/user';
	import { needsSetup, setupStatusLoaded, setupStatusError, loadSetupStatus } from '$lib/stores/setup';
	import { reloadWidgets } from '$lib/stores/widgets';
	import { api, type DeviceListEntry } from '$lib/api';

	let { children } = $props();

	// Shown once, right after a brand-new device cookie is minted, so a
	// household can tell "Kitchen Tablet" apart from "Alice's Phone" in the
	// device list later — skippable, defaults to the server's placeholder name.
	let namingDevice = $state(false);
	let deviceNameInput = $state('');

	// Offered once a user is known to have zero saved layout on this device —
	// covers both a genuinely brand-new device and a second household member
	// logging into an already-set-up shared device for the first time.
	let offeringLayoutCopy = $state(false);
	let copySourceDevices = $state<DeviceListEntry[]>([]);
	let copySourceId = $state('');
	let copyingLayout = $state(false);

	function layoutSetupDismissedKey(userId: string, deviceId: string) {
		return `tilora:layout-setup-dismissed:${userId}:${deviceId}`;
	}

	async function maybeOfferLayoutCopy() {
		if (!$user || !$device) return;
		if (localStorage.getItem(layoutSetupDismissedKey($user.id, $device.id))) return;

		const status = await api.layoutStatus().catch(() => null);
		if (!status || status.has_layout) return;

		const devices = await api.listDevices().catch(() => []);
		const others = devices.filter((d) => d.id !== $device?.id);
		if (others.length === 0) return;

		copySourceDevices = others;
		copySourceId = others[0].id;
		offeringLayoutCopy = true;
	}

	async function copyLayoutFromSource() {
		if (!copySourceId) return;
		copyingLayout = true;
		try {
			await api.copyDeviceLayout(copySourceId);
			await reloadWidgets();
			offeringLayoutCopy = false;
		} finally {
			copyingLayout = false;
		}
	}

	function startFresh() {
		if ($user && $device) localStorage.setItem(layoutSetupDismissedKey($user.id, $device.id), 'true');
		offeringLayoutCopy = false;
	}

	onMount(async () => {
		const registered = await ensureDevice().catch(() => null);
		if (registered?.is_new) {
			namingDevice = true;
			deviceNameInput = registered.name;
		}

		// Resolved before loadCurrentUser() so the redirect effect below can
		// decide setup-vs-login before either store's data actually matters.
		await loadSetupStatus();
		await loadCurrentUser();
	});

	// Fires once user + device are both known and the naming modal (if it was
	// shown at all) has been dismissed — keeps the two modals from stacking.
	let layoutCopyOfferChecked = false;
	$effect(() => {
		if (namingDevice || !$userLoaded || !$user || layoutCopyOfferChecked) return;
		layoutCopyOfferChecked = true;
		maybeOfferLayoutCopy();
	});

	// Three-way redirect: unreachable backend gets its own message (below),
	// a fresh install goes to /setup, everyone else falls through to the
	// existing "no session -> /login" check. Order matters — $needsSetup and
	// $userLoaded are only meaningful once their respective loads resolve.
	$effect(() => {
		if (!$setupStatusLoaded || $setupStatusError) return;

		if ($needsSetup) {
			if (page.url.pathname !== '/setup') goto('/setup');
			return;
		}
		if (page.url.pathname === '/setup') {
			goto('/login');
			return;
		}

		if (!$userLoaded) return;
		if (!$user && page.url.pathname !== '/login') {
			goto('/login');
		}
	});

	$effect(() => {
		if ($user) loadThemeFromServer();
	});

	function confirmDeviceName() {
		namingDevice = false;
		const name = deviceNameInput.trim();
		if (name && name !== $device?.name) renameDevice(name);
	}
</script>

<svelte:head>
	<title>Tilora</title>
	<link rel="icon" href={favicon} />
</svelte:head>

{#if $setupStatusError}
	<div class="fatal-error">
		<h2>Could not reach the Tilora backend</h2>
		<p class="hint">Check that the backend is running and reachable, then reload this page.</p>
	</div>
{:else}
	{#if namingDevice}
		<div class="device-modal-backdrop" role="presentation">
			<div class="device-modal">
				<h2>Name this device</h2>
				<p class="hint">Helps tell it apart in the device list — e.g. "Kitchen Tablet" or "Living Room TV".</p>
				<input type="text" bind:value={deviceNameInput} maxlength="40" />
				<button class="confirm" onclick={confirmDeviceName}>Done</button>
			</div>
		</div>
	{/if}

	{#if offeringLayoutCopy}
		<div class="device-modal-backdrop" role="presentation">
			<div class="device-modal">
				<h2>Set up this device</h2>
				<p class="hint">Copy your dashboard layout from one of your other devices, or start with the default layout.</p>
				<select bind:value={copySourceId}>
					{#each copySourceDevices as d (d.id)}
						<option value={d.id}>{d.name}</option>
					{/each}
				</select>
				<div class="layout-copy-actions">
					<button class="cancel" onclick={startFresh} disabled={copyingLayout}>Start fresh</button>
					<button class="confirm" onclick={copyLayoutFromSource} disabled={copyingLayout}>
						{copyingLayout ? 'Copying…' : 'Copy layout'}
					</button>
				</div>
			</div>
		</div>
	{/if}

	{@render children()}
{/if}

<style>
	.fatal-error {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 2rem;
		text-align: center;
	}

	.device-modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}

	.device-modal {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		width: 20rem;
		max-width: calc(100vw - 3rem);
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1.5rem;
	}

	.device-modal h2 {
		margin: 0;
	}

	.hint {
		color: var(--color-text-muted);
		margin: 0;
		font-size: 0.9rem;
	}

	.device-modal input,
	.device-modal select {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.layout-copy-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}

	.confirm {
		align-self: flex-end;
		background: var(--color-accent);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.cancel {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		color: var(--color-text);
		cursor: pointer;
	}
</style>
