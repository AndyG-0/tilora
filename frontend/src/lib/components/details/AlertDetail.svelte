<script lang="ts">
	import { page } from '$app/state';
	import { api, type Alert, type AlertSeverity } from '$lib/api';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	interface AlertDetailData {
		alerts: Alert[];
	}

	let { data: initialData }: { data: AlertDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from create/dismiss refetches.
	let detail = $state(initialData);

	let message = $state('');
	let severity = $state<AlertSeverity>('info');
	let creating = $state(false);
	let error = $state<string | null>(null);

	async function refresh() {
		detail = await api.widgetDetail<AlertDetailData>(page.params.id!);
	}

	async function createAlert() {
		const trimmed = message.trim();
		if (!trimmed) return;
		creating = true;
		error = null;
		try {
			await api.createAlert({ message: trimmed, severity });
			message = '';
			severity = 'info';
			await refresh();
		} catch {
			error = get(_)('alert.detail.create_error');
		} finally {
			creating = false;
		}
	}

	async function dismiss(id: number) {
		try {
			await api.dismissAlert(id);
			await refresh();
		} catch {
			error = get(_)('alert.detail.dismiss_error');
		}
	}
</script>

<h1>Alerts</h1>

<div class="list">
	{#each detail.alerts as alert (alert.id)}
		<div class="item severity-{alert.severity}">
			<div class="item-body">
				<p class="severity-label">{alert.severity}</p>
				<p class="message">{alert.message}</p>
			</div>
			<button class="dismiss" onclick={() => dismiss(alert.id)}>{$_('alert.detail.dismiss')}</button>
		</div>
	{:else}
		<p class="hint">{$_('alert.detail.empty')}</p>
	{/each}
</div>

<form class="create" onsubmit={(e) => (e.preventDefault(), createAlert())}>
	<h2>{$_('alert.detail.new_alert')}</h2>
	<input type="text" placeholder={$_('alert.detail.message_placeholder')} bind:value={message} />
	<select bind:value={severity}>
		<option value="info">{$_('alert.detail.severity_info')}</option>
		<option value="warning">{$_('alert.detail.severity_warning')}</option>
		<option value="critical">{$_('alert.detail.severity_critical')}</option>
	</select>
	<button type="submit" disabled={creating || !message.trim()}>{$_('alert.detail.add_alert')}</button>
	{#if error}
		<p class="hint error">{error}</p>
	{/if}
</form>

<style>
	.list {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		margin-bottom: 2rem;
	}

	.item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-left: 4px solid var(--alert-color, var(--color-text-muted));
		border-radius: 1rem;
		padding: 1rem;
	}

	.severity-info {
		--alert-color: var(--color-info);
	}

	.severity-warning {
		--alert-color: var(--color-warning);
	}

	.severity-critical {
		--alert-color: var(--color-error);
	}

	.severity-label {
		margin: 0 0 0.25rem;
		font-size: 0.8rem;
		text-transform: uppercase;
		color: var(--alert-color);
	}

	.message {
		margin: 0;
	}

	.dismiss {
		flex-shrink: 0;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}

	.create {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		max-width: 20rem;
	}

	.create h2 {
		margin: 0;
		font-size: 1rem;
	}

	.create input,
	.create select {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.create button {
		background: var(--color-accent);
		color: var(--color-on-accent);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
		cursor: pointer;
	}

	.create button:disabled {
		opacity: 0.6;
		cursor: default;
	}
</style>
