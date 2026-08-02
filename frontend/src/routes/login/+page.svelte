<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, type UserProfile } from '$lib/api';
	import { user } from '$lib/stores/user';

	let profiles = $state<UserProfile[]>([]);
	let loading = $state(true);
	let loadError = $state<string | null>(null);

	// A profile with a PIN drops into this mode instead of logging in
	// immediately; `pin` accumulates digit taps for the pad below.
	let pinProfile = $state<UserProfile | null>(null);
	let pin = $state('');
	let pinError = $state<string | null>(null);
	let loggingIn = $state(false);

	let adding = $state(false);
	let newName = $state('');
	let newAvatar = $state('');
	let newPin = $state('');
	let addError = $state<string | null>(null);
	let creating = $state(false);

	async function loadProfiles() {
		loading = true;
		loadError = null;
		try {
			profiles = await api.listUsers();
		} catch {
			loadError = 'Could not load profiles.';
		} finally {
			loading = false;
		}
	}

	onMount(loadProfiles);

	async function selectProfile(profile: UserProfile) {
		if (profile.has_pin) {
			pinProfile = profile;
			pin = '';
			pinError = null;
			return;
		}
		await login(profile, undefined);
	}

	async function login(profile: UserProfile, submittedPin: string | undefined) {
		loggingIn = true;
		pinError = null;
		try {
			const me = await api.loginUser(profile.id, submittedPin);
			user.set(me);
			goto('/');
		} catch {
			pinError = 'Incorrect PIN.';
			pin = '';
		} finally {
			loggingIn = false;
		}
	}

	function tapDigit(digit: string) {
		if (pin.length >= 8) return;
		pin += digit;
	}

	function backspace() {
		pin = pin.slice(0, -1);
	}

	function cancelPin() {
		pinProfile = null;
		pin = '';
		pinError = null;
	}

	function submitPin() {
		if (!pinProfile || pin.length < 4) return;
		login(pinProfile, pin);
	}

	function openAdd() {
		adding = true;
		newName = '';
		newAvatar = '';
		newPin = '';
		addError = null;
	}

	function cancelAdd() {
		adding = false;
	}

	async function createProfile() {
		if (!newName.trim()) return;
		if (newPin && !/^\d{4,8}$/.test(newPin)) {
			addError = 'PIN must be 4-8 digits.';
			return;
		}
		creating = true;
		addError = null;
		try {
			const me = await api.createUser(newName.trim(), newAvatar.trim() || undefined, newPin || undefined);
			user.set(me);
			goto('/');
		} catch {
			addError = 'Could not create profile.';
		} finally {
			creating = false;
		}
	}
</script>

<div class="login-page">
	<h1>Who's watching?</h1>

	{#if loading}
		<p class="hint">Loading…</p>
	{:else if loadError}
		<p class="hint error">{loadError}</p>
	{:else if pinProfile}
		<div class="pin-pad">
			<p class="pin-prompt">Enter PIN for {pinProfile.name}</p>
			<div class="pin-dots" aria-hidden="true">
				<!-- eslint-disable-next-line @typescript-eslint/no-unused-vars -- each-block item binding is required syntax; only the index is used -->
				{#each Array(8) as _, i (i)}
					<span class="pin-dot" class:filled={i < pin.length}></span>
				{/each}
			</div>
			{#if pinError}
				<p class="hint error">{pinError}</p>
			{/if}
			<div class="pad-grid">
				{#each ['1', '2', '3', '4', '5', '6', '7', '8', '9'] as digit (digit)}
					<button class="pad-key" onclick={() => tapDigit(digit)} disabled={loggingIn}>{digit}</button>
				{/each}
				<button class="pad-key" onclick={backspace} disabled={loggingIn} aria-label="Backspace">⌫</button>
				<button class="pad-key" onclick={() => tapDigit('0')} disabled={loggingIn}>0</button>
				<button
					class="pad-key confirm"
					onclick={submitPin}
					disabled={loggingIn || pin.length < 4}
					aria-label="Submit PIN"
				>
					✓
				</button>
			</div>
			<button class="cancel" onclick={cancelPin} disabled={loggingIn}>← Back</button>
		</div>
	{:else if adding}
		<div class="add-form">
			<label>
				Name
				<input type="text" bind:value={newName} placeholder="Alice" maxlength="40" />
			</label>
			<label>
				Avatar (emoji, optional)
				<input type="text" bind:value={newAvatar} placeholder="🐱" maxlength="8" />
			</label>
			<label>
				PIN (optional)
				<input type="password" inputmode="numeric" bind:value={newPin} placeholder="4-8 digits" maxlength="8" />
			</label>
			{#if addError}
				<p class="hint error">{addError}</p>
			{/if}
			<div class="add-actions">
				<button class="cancel" onclick={cancelAdd} disabled={creating}>Cancel</button>
				<button class="confirm-button" onclick={createProfile} disabled={creating || !newName.trim()}>
					{creating ? 'Creating…' : 'Create'}
				</button>
			</div>
		</div>
	{:else}
		<div class="profile-grid">
			{#each profiles as profile (profile.id)}
				<button class="profile" onclick={() => selectProfile(profile)}>
					<span class="avatar">{profile.avatar || profile.name.charAt(0).toUpperCase()}</span>
					<span class="name">{profile.name}</span>
					{#if profile.has_pin}
						<span class="lock" aria-hidden="true">🔒</span>
					{/if}
				</button>
			{/each}
			<button class="profile add" onclick={openAdd}>
				<span class="avatar">+</span>
				<span class="name">Add profile</span>
			</button>
		</div>
	{/if}
</div>

<style>
	.login-page {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 2rem;
		gap: 2rem;
	}

	h1 {
		margin: 0;
	}

	.profile-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 1.5rem;
		justify-content: center;
		max-width: 40rem;
	}

	.profile {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		width: 8rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1.25rem 0.75rem;
		cursor: pointer;
		color: var(--color-text);
	}

	.profile.add {
		border-style: dashed;
		color: var(--color-text-muted);
	}

	.avatar {
		width: 3.5rem;
		height: 3.5rem;
		border-radius: 50%;
		background: var(--color-surface-hover, var(--color-border));
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1.6rem;
	}

	.name {
		font-size: 0.95rem;
		text-align: center;
	}

	.lock {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
		font-size: 0.9rem;
	}

	.pin-pad,
	.add-form {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		width: 18rem;
	}

	.pin-prompt {
		margin: 0;
	}

	.pin-dots {
		display: flex;
		gap: 0.5rem;
	}

	.pin-dot {
		width: 0.75rem;
		height: 0.75rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: transparent;
	}

	.pin-dot.filled {
		background: var(--color-accent, var(--color-text));
	}

	.pad-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.75rem;
	}

	.pad-key {
		width: 4rem;
		height: 4rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		font-size: 1.3rem;
		cursor: pointer;
	}

	.pad-key.confirm {
		background: var(--color-accent);
		color: var(--color-surface);
		border: none;
	}

	.pad-key:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.cancel {
		background: none;
		border: none;
		color: var(--color-accent);
		cursor: pointer;
		font-size: 1rem;
	}

	.add-form {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1.5rem;
	}

	.add-form label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		width: 100%;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.add-form input {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.add-actions {
		display: flex;
		gap: 0.75rem;
		width: 100%;
		justify-content: flex-end;
	}

	.confirm-button {
		background: var(--color-accent);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.confirm-button:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
