<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import ClockFace, { type ClockStyle } from '$lib/components/clock-faces/ClockFace.svelte';

	interface ClockDetailData {
		timezone: string;
		style: ClockStyle;
	}

	const STYLE_OPTIONS: { value: ClockStyle; label: string }[] = [
		{ value: 'digital', label: 'Digital' },
		{ value: 'analog', label: 'Analog' },
		{ value: 'binary', label: 'Binary' },
		{ value: 'word', label: 'Word clock' },
		{ value: 'matrix', label: 'Matrix' },
	];

	let { data: initialData }: { data: ClockDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let clock = $state(initialData);

	let now = $state(new Date());
	let editingSettings = $state(false);
	let styleChoice = $state<ClockStyle>('digital');
	let saving = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		const interval = setInterval(() => (now = new Date()), 1000);
		return () => clearInterval(interval);
	});

	function openEditor() {
		styleChoice = clock.style;
		editingSettings = true;
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(page.params.id!, { style: styleChoice });
			clock = await api.widgetDetail<ClockDetailData>(page.params.id!);
			editingSettings = false;
		} catch {
			error = 'Could not update the settings.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>Clock</h1>
	<button class="edit-settings" onclick={() => (editingSettings ? (editingSettings = false) : openEditor())}>
		{editingSettings ? 'Cancel' : 'Edit settings'}
	</button>
</div>

{#if editingSettings}
	<div class="settings-form">
		<label>
			Style
			<select bind:value={styleChoice}>
				{#each STYLE_OPTIONS as option (option.value)}
					<option value={option.value}>{option.label}</option>
				{/each}
			</select>
		</label>

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={saveSettings}>
			{saving ? 'Saving…' : 'Save'}
		</button>
	</div>
{/if}

<div class="face">
	<ClockFace style={clock.style} {now} timezone={clock.timezone} size="detail" />
</div>
<p class="hint">{clock.timezone} · change this in Settings</p>

<style>
	.header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
	}

	.header h1 {
		margin: 0 0 1rem;
	}

	.edit-settings {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.settings-form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		max-width: 20rem;
		margin: 0 0 1.5rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem;
	}

	.settings-form label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.settings-form select {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.save {
		align-self: flex-start;
		background: var(--color-accent);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.face {
		margin: 0 0 0.5rem;
	}

	.hint {
		color: var(--color-text-muted);
		margin: 0;
	}

	.hint.error {
		color: var(--color-error);
	}
</style>
