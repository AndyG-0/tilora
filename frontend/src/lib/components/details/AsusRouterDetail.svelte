<script lang="ts">
	import { type AsusRouterDetail } from '$lib/api';
	import { _ } from 'svelte-i18n';

	let { data: router }: { data: AsusRouterDetail } = $props();

	function formatBytes(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		const units = ['KB', 'MB', 'GB', 'TB'];
		let value = bytes / 1024;
		let unitIndex = 0;
		while (value >= 1024 && unitIndex < units.length - 1) {
			value /= 1024;
			unitIndex++;
		}
		return `${value.toFixed(1)} ${units[unitIndex]}`;
	}
</script>

<div class="header">
	<h1>Asus Router</h1>
</div>

{#if !router.connected}
	<p class="hint">{$_('asus_router.detail.not_connected_hint')}</p>
{:else}
	{#if router.error}
		<p class="hint error">{router.error}</p>
	{/if}

	<div class="system-info">
		<div class="stat">
			<div class="stat-value">
				{router.wan_connected ? $_('asus_router.detail.connected') : $_('asus_router.detail.down')}
			</div>
			<div class="stat-label">{$_('asus_router.detail.wan_status_label')}</div>
		</div>
		<div class="stat">
			<div class="stat-value">{router.wan_ip ?? $_('common.unknown')}</div>
			<div class="stat-label">{$_('asus_router.detail.wan_ip_label')}</div>
		</div>
		<div class="stat">
			<div class="stat-value">{formatBytes(router.rx_bytes)}</div>
			<div class="stat-label">{$_('asus_router.detail.download_label')}</div>
		</div>
		<div class="stat">
			<div class="stat-value">{formatBytes(router.tx_bytes)}</div>
			<div class="stat-label">{$_('asus_router.detail.upload_label')}</div>
		</div>
	</div>

	{#if router.clients.length === 0}
		<p class="hint">{$_('asus_router.detail.no_clients')}</p>
	{:else}
		<ul class="clients">
			{#each router.clients as client (client.name + client.ip)}
				<li>
					<span class="dot" class:offline={!client.online}></span>
					<span class="name">{client.name}</span>
					<span class="ip">{client.ip}</span>
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

	.clients {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.clients li {
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

	.ip {
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

	.dot.offline {
		background: var(--color-text-muted);
	}
</style>
