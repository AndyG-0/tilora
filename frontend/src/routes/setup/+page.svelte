<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { user } from '$lib/stores/user';
	import { needsSetup } from '$lib/stores/setup';

	let name = $state('');
	let avatar = $state('');
	let pin = $state('');
	let error = $state<string | null>(null);
	let creating = $state(false);

	async function createAdmin() {
		if (!name.trim()) return;
		if (pin && !/^\d{4,8}$/.test(pin)) {
			error = 'PIN must be 4-8 digits.';
			return;
		}
		creating = true;
		error = null;
		try {
			const me = await api.createSetupAdmin(name.trim(), avatar.trim() || undefined, pin || undefined);
			user.set(me);
			needsSetup.set(false);
			goto('/');
		} catch {
			error = 'Could not create your account. Please try again.';
		} finally {
			creating = false;
		}
	}
</script>

<div class="setup-page">
	<h1>Welcome to Tilora</h1>
	<p class="hint">Let's create your account. As the first profile, you'll be the household admin.</p>

	<div class="setup-form">
		<label>
			Name
			<input type="text" bind:value={name} placeholder="Alice" maxlength="40" />
		</label>
		<label>
			Avatar (emoji, optional)
			<input type="text" bind:value={avatar} placeholder="🐱" maxlength="8" />
		</label>
		<label>
			PIN (optional)
			<input type="password" inputmode="numeric" bind:value={pin} placeholder="4-8 digits" maxlength="8" />
		</label>
		{#if error}
			<p class="hint error">{error}</p>
		{/if}
		<button class="confirm-button" onclick={createAdmin} disabled={creating || !name.trim()}>
			{creating ? 'Creating…' : 'Create account'}
		</button>
	</div>
</div>

<style>
	.setup-page {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 2rem;
		gap: 1rem;
		text-align: center;
	}

	h1 {
		margin: 0;
	}

	.hint {
		color: var(--color-text-muted);
		max-width: 24rem;
	}

	.hint.error {
		color: var(--color-error);
	}

	.setup-form {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		width: 18rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1.5rem;
		margin-top: 1rem;
	}

	.setup-form label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		width: 100%;
		font-size: 0.9rem;
		color: var(--color-text-muted);
		text-align: left;
	}

	.setup-form input {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.confirm-button {
		align-self: stretch;
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
</style>
