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

	let { children } = $props();

	// Shown once, right after a brand-new device cookie is minted, so a
	// household can tell "Kitchen Tablet" apart from "Alice's Phone" in the
	// device list later — skippable, defaults to the server's placeholder name.
	let namingDevice = $state(false);
	let deviceNameInput = $state('');

	onMount(async () => {
		const registered = await ensureDevice().catch(() => null);
		if (registered?.is_new) {
			namingDevice = true;
			deviceNameInput = registered.name;
		}

		await loadCurrentUser();
	});

	// Redirect to the profile picker once we know there's no session — but
	// only after the initial check resolves, so a logged-in user isn't
	// bounced through /login on every reload, and only outside /login itself
	// so the picker doesn't redirect-loop against itself.
	$effect(() => {
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

{@render children()}

<style>
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

	.device-modal input {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
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
</style>
