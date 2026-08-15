<script lang="ts">
	import { page } from '$app/state';
	import { type AsusRouterClient, type AsusRouterDetail } from '$lib/api';
	import { user } from '$lib/stores/user';
	import { _ } from 'svelte-i18n';
	import AsusRouterClientModal from './AsusRouterClientModal.svelte';

	let { data: initialData }: { data: AsusRouterDetail } = $props();

	// svelte-ignore state_referenced_locally -- seed local mutable state from initial data; updates come from mutations.
	let router = $state<AsusRouterDetail>(initialData);
	let selectedClient = $state<AsusRouterClient | null>(null);
	let searchQuery = $state('');
	let filterType = $state<'all' | 'wired' | 'wireless' | 'online'>('all');

	const widgetId = $derived(page.params.id || 'asus_router');
	const isAdmin = $derived($user?.role === 'admin');

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

	const wiredCount = $derived(router.clients.filter((c) => c.connection_type === 'wired').length);
	const wirelessCount = $derived(router.clients.filter((c) => c.connection_type === 'wireless').length);
	const onlineCount = $derived(router.clients.filter((c) => c.online).length);

	const filteredClients = $derived(
		router.clients.filter((client) => {
			if (filterType === 'wired' && client.connection_type !== 'wired') return false;
			if (filterType === 'wireless' && client.connection_type !== 'wireless') return false;
			if (filterType === 'online' && !client.online) return false;

			if (!searchQuery.trim()) return true;
			const q = searchQuery.toLowerCase().trim();
			return (
				client.name.toLowerCase().includes(q) ||
				(client.alias && client.alias.toLowerCase().includes(q)) ||
				(client.hostname && client.hostname.toLowerCase().includes(q)) ||
				client.ip.toLowerCase().includes(q) ||
				(client.mac && client.mac.toLowerCase().includes(q)) ||
				(client.vendor && client.vendor.toLowerCase().includes(q))
			);
		}),
	);

	function updateClientInList(updated: AsusRouterClient) {
		const idx = router.clients.findIndex((c) => c.mac === updated.mac || (c.ip && c.ip === updated.ip));
		if (idx !== -1) {
			router.clients[idx] = updated;
		}
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
		<div class="clients-section">
			<!-- Filter & Search Controls -->
			<div class="client-controls">
				<div class="filter-pills">
					<button class="pill-btn" class:active={filterType === 'all'} onclick={() => (filterType = 'all')}>
						{$_('asus_router.detail.filter_all', { values: { count: router.clients.length } })}
					</button>
					<button class="pill-btn" class:active={filterType === 'online'} onclick={() => (filterType = 'online')}>
						{$_('asus_router.detail.filter_online', { values: { count: onlineCount } })}
					</button>
					<button class="pill-btn" class:active={filterType === 'wired'} onclick={() => (filterType = 'wired')}>
						{$_('asus_router.detail.filter_wired', { values: { count: wiredCount } })}
					</button>
					<button class="pill-btn" class:active={filterType === 'wireless'} onclick={() => (filterType = 'wireless')}>
						{$_('asus_router.detail.filter_wireless', { values: { count: wirelessCount } })}
					</button>
				</div>

				<div class="search-box">
					<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
						<circle cx="11" cy="11" r="8"></circle>
						<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
					</svg>
					<input type="search" bind:value={searchQuery} placeholder={$_('asus_router.detail.search_placeholder')} />
				</div>
			</div>

			<!-- Clients List -->
			<ul class="clients" role="list">
				{#each filteredClients as client (client.mac || client.name + client.ip)}
					<li>
						<button type="button" class="client-row-btn" onclick={() => (selectedClient = client)}>
							<span class="dot" class:offline={!client.online}></span>

							<!-- Connection Type Badge -->
							{#if client.connection_type === 'wired'}
								<div class="conn-badge">
									<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2">
										<rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
										<rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
										<line x1="6" y1="6" x2="6.01" y2="6"></line>
										<line x1="6" y1="18" x2="6.01" y2="18"></line>
									</svg>
									<span>{$_('asus_router.detail.wired')}</span>
								</div>
							{:else if client.connection_type === 'wireless'}
								<div class="conn-badge wireless">
									<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2">
										<path d="M5 12.55a11 11 0 0 1 14.08 0"></path>
										<path d="M1.42 9a16 16 0 0 1 21.16 0"></path>
										<path d="M8.53 16.11a6 6 0 0 1 6.95 0"></path>
										<line x1="12" y1="20" x2="12.01" y2="20"></line>
									</svg>
									<span>{client.wireless_band || $_('asus_router.detail.wireless')}</span>
									{#if client.rssi != null}
										<span class="rssi-val">{client.rssi} dBm</span>
									{/if}
								</div>
							{/if}

							<!-- Device Names & Vendor -->
							<div class="name-col">
								<span class="name">{client.alias || client.name}</span>
								<div class="sub-row">
									{#if client.vendor}
										<span class="vendor-sub">{client.vendor}</span>
									{/if}
									{#if client.mac}
										<span class="mac-sub">{client.mac.toUpperCase()}</span>
									{/if}
								</div>
							</div>

							<!-- IP Address & Blocked tag -->
							<div class="ip-col">
								<span class="ip">{client.ip}</span>
								{#if client.internet_blocked}
									<span class="blocked-pill">{$_('asus_router.detail.internet_blocked')}</span>
								{/if}
							</div>

							<!-- Chevron Icon -->
							<svg
								class="chevron"
								viewBox="0 0 24 24"
								width="16"
								height="16"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
							>
								<polyline points="9 18 15 12 9 6"></polyline>
							</svg>
						</button>
					</li>
				{/each}
			</ul>
		</div>
	{/if}
{/if}

<!-- Client Detail Modal -->
{#if selectedClient}
	<AsusRouterClientModal
		client={selectedClient}
		{widgetId}
		{isAdmin}
		onclose={() => (selectedClient = null)}
		onupdate={(updated) => {
			updateClientInList(updated);
			selectedClient = updated;
		}}
	/>
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

	.clients-section {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-top: 1rem;
	}

	.client-controls {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.filter-pills {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-wrap: wrap;
	}

	.pill-btn {
		font: inherit;
		font-size: 0.8rem;
		font-weight: 500;
		padding: 0.35rem 0.65rem;
		border-radius: 9999px;
		border: 1px solid var(--color-border);
		background: rgba(255, 255, 255, 0.04);
		color: var(--color-text-muted);
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.pill-btn:hover {
		background: rgba(255, 255, 255, 0.08);
		color: var(--color-text);
	}

	.pill-btn.active {
		background: var(--color-accent);
		color: var(--color-surface);
		border-color: var(--color-accent);
		font-weight: 600;
	}

	.search-box {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		min-width: 15rem;
		max-width: 100%;
		color: var(--color-text-muted);
	}

	.search-box input {
		font: inherit;
		font-size: 0.85rem;
		background: none;
		border: none;
		outline: none;
		color: var(--color-text);
		width: 100%;
	}

	.clients {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.clients li {
		margin: 0;
		padding: 0;
	}

	.client-row-btn {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.6rem;
		padding: 0.65rem 0.9rem;
		font: inherit;
		color: inherit;
		text-align: left;
		cursor: pointer;
		transition:
			transform 0.1s ease,
			border-color 0.15s ease,
			background 0.15s ease;
	}

	.client-row-btn:hover {
		background: rgba(255, 255, 255, 0.03);
		border-color: rgba(255, 255, 255, 0.25);
		transform: translateY(-1px);
	}

	.name-col {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		min-width: 0;
		flex: 1;
	}

	.name {
		font-weight: 600;
		font-size: 0.95rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.sub-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.75rem;
		color: var(--color-text-muted);
		flex-wrap: wrap;
	}

	.vendor-sub {
		font-weight: 500;
		color: var(--color-accent);
	}

	.mac-sub {
		font-family: monospace;
		opacity: 0.8;
	}

	.ip-col {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.15rem;
		flex-shrink: 0;
		margin-left: auto;
	}

	.ip {
		color: var(--color-text-muted);
		font-size: 0.88rem;
		font-family: monospace;
	}

	.blocked-pill {
		font-size: 0.7rem;
		font-weight: 600;
		color: var(--color-error);
		background: rgba(239, 68, 68, 0.15);
		border-radius: 0.25rem;
		padding: 0.1rem 0.35rem;
	}

	.conn-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.75rem;
		font-weight: 500;
		padding: 0.2rem 0.45rem;
		border-radius: 0.35rem;
		background: rgba(96, 165, 250, 0.12);
		color: #60a5fa;
		flex-shrink: 0;
	}

	.conn-badge.wireless {
		background: rgba(52, 211, 153, 0.12);
		color: #34d399;
	}

	.rssi-val {
		font-size: 0.7rem;
		opacity: 0.85;
	}

	.dot {
		width: 0.55rem;
		height: 0.55rem;
		border-radius: 50%;
		background: var(--color-success);
		flex-shrink: 0;
	}

	.dot.offline {
		background: var(--color-text-muted);
	}

	.chevron {
		color: var(--color-text-muted);
		opacity: 0.6;
		flex-shrink: 0;
		transition: transform 0.15s ease;
	}

	.client-row-btn:hover .chevron {
		opacity: 1;
		transform: translateX(2px);
	}
</style>
