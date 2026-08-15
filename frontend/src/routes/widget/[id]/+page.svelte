<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { DETAIL_COMPONENTS } from '$lib/widgetComponents';
	import { _ } from 'svelte-i18n';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const Detail = $derived(data.type ? DETAIL_COMPONENTS[data.type] : undefined);

	// SvelteKit reuses this component instance across navigations between two
	// widget detail pages (only `load()` re-runs), so `name` must resync
	// whenever the route actually loads a different widget — but stay put
	// after a same-widget rename, which only updates local state, not `data`.
	// A writable $derived does both: it re-tracks `data.name` on navigation,
	// while a direct assignment below (in saveName) locally overrides it.
	let name = $derived(data.name);

	let editingName = $state(false);
	let nameInput = $state('');
	let savingName = $state(false);
	let nameError = $state<string | null>(null);

	function startEditingName() {
		nameInput = name ?? '';
		nameError = null;
		editingName = true;
	}

	function cancelEditingName() {
		editingName = false;
		nameError = null;
	}

	async function saveName() {
		const trimmed = nameInput.trim();
		if (trimmed.length > 60) {
			nameError = $_('widget_detail.rename_error');
			return;
		}

		savingName = true;
		nameError = null;
		try {
			const result = await api.renameWidget(data.widgetId, trimmed);
			name = result.name;
			editingName = false;
		} catch {
			nameError = $_('widget_detail.rename_error');
		} finally {
			savingName = false;
		}
	}
</script>

<div class="detail-page">
	<button class="back" onclick={() => goto('/')}>{$_('common.back')}</button>

	{#if name}
		<div class="tile-name">
			{#if editingName}
				<form
					class="rename-form"
					onsubmit={(e) => {
						e.preventDefault();
						saveName();
					}}
				>
					<input
						type="text"
						bind:value={nameInput}
						maxlength="60"
						aria-label={$_('widget_detail.name_input_label')}
						disabled={savingName}
						onkeydown={(e) => {
							if (e.key === 'Escape') cancelEditingName();
						}}
					/>
					<button type="button" class="cancel" onclick={cancelEditingName} disabled={savingName}>
						{$_('common.cancel')}
					</button>
					<button type="submit" class="save" disabled={savingName}>
						{savingName ? $_('common.saving') : $_('common.save')}
					</button>
				</form>
				{#if nameError}
					<p class="hint error">{nameError}</p>
				{/if}
			{:else}
				<h1>{name}</h1>
				<button type="button" class="rename-link" onclick={startEditingName}>
					{$_('widget_detail.rename')}
				</button>
			{/if}
		</div>
	{/if}

	{#if Detail}
		<!-- Shape is only known at runtime via `data.type`; each Detail
		     component declares & validates its own expected shape. -->
		<Detail data={data.detail as never} />
	{:else}
		<p>{$_('widget_detail.unknown_widget')}</p>
	{/if}
</div>

<style>
	.detail-page {
		padding: 2rem;
		min-height: 100vh;
	}

	.back {
		background: none;
		border: none;
		font-size: 1.1rem;
		color: var(--color-accent);
		margin-bottom: 1.5rem;
		cursor: pointer;
		padding: 0.5rem 0;
	}

	.tile-name {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1.5rem;
	}

	.tile-name h1 {
		margin: 0;
		font-size: 1.5rem;
	}

	.rename-link {
		background: none;
		border: none;
		color: var(--color-accent);
		cursor: pointer;
		font-size: 0.9rem;
		padding: 0.25rem 0;
	}

	.rename-form {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.rename-form input {
		font-size: 1.1rem;
		padding: 0.4rem 0.6rem;
		border: 1px solid var(--color-border);
		border-radius: 0.4rem;
		background: var(--color-surface);
		color: inherit;
	}

	.rename-form .save,
	.rename-form .cancel {
		padding: 0.4rem 0.8rem;
		border-radius: 0.4rem;
		border: 1px solid var(--color-border);
		cursor: pointer;
		background: var(--color-surface);
		color: inherit;
	}

	.rename-form .save {
		background: var(--color-accent);
		color: var(--color-surface);
		border-color: transparent;
	}

	.rename-form .save:disabled,
	.rename-form .cancel:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.hint.error {
		color: var(--color-error);
		width: 100%;
		margin: 0.25rem 0 0;
	}
</style>
