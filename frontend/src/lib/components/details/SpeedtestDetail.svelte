<script lang="ts">
	import { page } from '$app/state';
	import { api, type SpeedtestDetail, type SpeedtestRun } from '$lib/api';
	import { user } from '$lib/stores/user';
	import { _, locale } from 'svelte-i18n';
	import { get } from 'svelte/store';

	let { data: initialData }: { data: SpeedtestDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings/runNow's refetch.
	let speedtest = $state(initialData);

	let editing = $state(false);
	let intervalInput = $state(60);
	let saving = $state(false);
	let running = $state(false);
	let error = $state<string | null>(null);

	const widgetId = $derived(page.params.id!);

	function openEditor() {
		intervalInput = speedtest.interval_minutes;
		editing = true;
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, { interval_minutes: intervalInput });
			speedtest = await api.widgetDetail<SpeedtestDetail>(widgetId);
			editing = false;
		} catch {
			error = get(_)('speedtest.detail.save_error');
		} finally {
			saving = false;
		}
	}

	async function runNow() {
		running = true;
		error = null;
		try {
			speedtest = await api.runAiWidget<SpeedtestDetail>(widgetId);
		} catch {
			error = get(_)('speedtest.detail.run_error');
		} finally {
			running = false;
		}
	}

	function formatMbps(value: number | null | undefined): string {
		return value === null || value === undefined ? '—' : `${value.toFixed(1)} Mbps`;
	}

	const SPARKLINE_WIDTH = 300;
	const SPARKLINE_HEIGHT = 60;

	function sparklinePoints(history: SpeedtestRun[], key: 'download_mbps' | 'upload_mbps'): string {
		if (history.length === 0) return '';
		const values = [...history].reverse().map((run) => run[key]);
		const max = Math.max(...values, 1);
		const step = values.length > 1 ? SPARKLINE_WIDTH / (values.length - 1) : 0;
		return values
			.map((v, i) => `${(i * step).toFixed(1)},${(SPARKLINE_HEIGHT - (v / max) * SPARKLINE_HEIGHT).toFixed(1)}`)
			.join(' ');
	}
</script>

<div class="header">
	<h1>{speedtest.title}</h1>
	<div class="actions">
		<button class="run" disabled={running} onclick={runNow}>
			{running ? $_('speedtest.detail.running') : $_('speedtest.detail.run_now')}
		</button>
		{#if $user?.role === 'admin'}
			<button class="edit-settings" onclick={() => (editing ? (editing = false) : openEditor())}>
				{editing ? $_('common.cancel') : $_('speedtest.detail.edit_interval')}
			</button>
		{/if}
	</div>
</div>

{#if editing}
	<div class="settings-form">
		<label>
			{$_('speedtest.detail.interval_label')}
			<input type="number" min="5" bind:value={intervalInput} />
		</label>

		<button class="save" disabled={saving} onclick={saveSettings}>
			{saving ? $_('common.saving') : $_('common.save')}
		</button>
	</div>
{/if}

{#if error}
	<p class="hint error">{error}</p>
{/if}

{#if speedtest.ran_at === null}
	<p class="hint">{$_('speedtest.detail.no_results_hint')}</p>
{:else}
	<div class="stats">
		<div class="stat">
			<div class="stat-value">{formatMbps(speedtest.download_mbps)}</div>
			<div class="stat-label">{$_('speedtest.detail.download')}</div>
		</div>
		<div class="stat">
			<div class="stat-value">{formatMbps(speedtest.upload_mbps)}</div>
			<div class="stat-label">{$_('speedtest.detail.upload')}</div>
		</div>
		<div class="stat">
			<div class="stat-value">{speedtest.ping_ms?.toFixed(0)} ms</div>
			<div class="stat-label">{$_('speedtest.detail.ping')}</div>
		</div>
	</div>
	<p class="server">{speedtest.server_name} · {new Date(speedtest.ran_at).toLocaleString($locale ?? undefined)}</p>

	{#if speedtest.history.length > 1}
		<h2>{$_('speedtest.detail.history')}</h2>
		<svg class="sparkline" viewBox="0 0 {SPARKLINE_WIDTH} {SPARKLINE_HEIGHT}" preserveAspectRatio="none">
			<polyline points={sparklinePoints(speedtest.history, 'download_mbps')} class="line down" />
			<polyline points={sparklinePoints(speedtest.history, 'upload_mbps')} class="line up" />
		</svg>
		<table class="history">
			<thead>
				<tr>
					<th>{$_('speedtest.detail.column_when')}</th>
					<th>{$_('speedtest.detail.download')}</th>
					<th>{$_('speedtest.detail.upload')}</th>
					<th>{$_('speedtest.detail.ping')}</th>
					<th>{$_('speedtest.detail.column_server')}</th>
				</tr>
			</thead>
			<tbody>
				{#each speedtest.history as run (run.ran_at)}
					<tr>
						<td>{new Date(run.ran_at).toLocaleString($locale ?? undefined)}</td>
						<td>{formatMbps(run.download_mbps)}</td>
						<td>{formatMbps(run.upload_mbps)}</td>
						<td>{run.ping_ms.toFixed(0)} ms</td>
						<td>{run.server_name}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
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

	.actions {
		display: flex;
		gap: 0.5rem;
	}

	.run,
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
		margin: 1rem 0 1.5rem;
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

	.settings-form input[type='number'] {
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

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
		gap: 1rem;
		margin: 1rem 0;
	}

	.stat {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.75rem 1rem;
	}

	.stat-value {
		font-size: 1.5rem;
		font-weight: 600;
	}

	.stat-label {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.server {
		color: var(--color-text-muted);
		font-size: 0.9rem;
	}

	h2 {
		font-size: 1rem;
		margin: 1.5rem 0 0.5rem;
	}

	.sparkline {
		width: 100%;
		max-width: 40rem;
		height: 6rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
	}

	.sparkline .line {
		fill: none;
		stroke-width: 2;
		vector-effect: non-scaling-stroke;
	}

	.sparkline .line.down {
		stroke: var(--color-accent);
	}

	.sparkline .line.up {
		stroke: var(--color-success);
	}

	.history {
		width: 100%;
		border-collapse: collapse;
		margin-top: 0.75rem;
		font-size: 0.9rem;
	}

	.history th,
	.history td {
		text-align: left;
		padding: 0.4rem 0.6rem;
		border-bottom: 1px solid var(--color-border);
	}

	.history th {
		color: var(--color-text-muted);
		font-weight: 600;
	}
</style>
