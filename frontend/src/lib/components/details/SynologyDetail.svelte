<script lang="ts">
	import { type SynologyDetail } from '$lib/api';
	import { _ } from 'svelte-i18n';

	let { data: synology }: { data: SynologyDetail } = $props();
</script>

<div class="header">
	<h1>Synology</h1>
</div>

{#if !synology.connected}
	<p class="hint">{$_('synology.detail.not_connected_hint')}</p>
{:else}
	{#if synology.error}
		<p class="hint error">{synology.error}</p>
	{/if}

	<div class="system-info">
		<div class="stat">
			<div class="stat-value">{synology.model ?? $_('common.unknown')}</div>
			<div class="stat-label">{$_('synology.detail.model_label')}</div>
		</div>
		<div class="stat">
			<div class="stat-value">{synology.uptime ?? $_('common.unknown')}</div>
			<div class="stat-label">{$_('synology.detail.uptime_label')}</div>
		</div>
		<div class="stat">
			<div class="stat-value">
				{synology.temperature_celsius != null ? `${synology.temperature_celsius}°C` : $_('common.unknown')}
			</div>
			<div class="stat-label">{$_('synology.detail.temp_label')}</div>
			{#if synology.temperature_celsius == null}
				<div class="stat-hint">{$_('synology.detail.temp_hint')}</div>
			{/if}
		</div>
	</div>

	{#if synology.volumes.length === 0}
		<p class="hint">{$_('synology.detail.no_volumes')}</p>
	{:else}
		<ul class="volumes">
			{#each synology.volumes as volume (volume.name)}
				<li>
					<span class="dot" class:warn={volume.status !== 'normal'}></span>
					<span class="name">{volume.name}</span>
					<span class="status">{volume.status}</span>
					<span class="percent">{volume.used_percent}%</span>
				</li>
			{/each}
		</ul>
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

	.hint {
		color: var(--color-text-muted);
	}

	.hint.error {
		color: var(--color-error);
	}

	.system-info {
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
		font-size: 1.25rem;
		font-weight: 600;
	}

	.stat-label {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.stat-hint {
		color: var(--color-text-muted);
		font-size: 0.7rem;
		margin-top: 0.2rem;
	}

	.volumes {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.volumes li {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
	}

	.name {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.status {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.percent {
		margin-left: auto;
		color: var(--color-text-muted);
		font-size: 0.85rem;
		flex-shrink: 0;
	}

	.dot {
		width: 0.6rem;
		height: 0.6rem;
		border-radius: 50%;
		background: var(--color-success);
		flex-shrink: 0;
	}

	.dot.warn {
		background: var(--color-warning);
	}
</style>
