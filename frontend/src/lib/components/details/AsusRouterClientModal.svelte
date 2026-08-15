<script lang="ts">
	import { api, type AsusRouterClient, type AsusRouterPingResult, type AsusRouterPortScanResult } from '$lib/api';
	import { _ } from 'svelte-i18n';

	let {
		client,
		widgetId,
		isAdmin = false,
		onclose,
		onupdate,
	}: {
		client: AsusRouterClient;
		widgetId: string;
		isAdmin?: boolean;
		onclose: () => void;
		onupdate?: (updated: AsusRouterClient) => void;
	} = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the initial prop; updates come from actions.
	let currentClient = $state<AsusRouterClient>({ ...client });

	// Port scan state
	let portScanning = $state(false);
	let portScanResult = $state<AsusRouterPortScanResult | null>(null);
	let portScanError = $state<string | null>(null);

	// WOL state
	let wolSending = $state(false);
	let wolSuccess = $state(false);
	let wolError = $state<string | null>(null);

	// Ping state
	let pinging = $state(false);
	let pingResult = $state<AsusRouterPingResult | null>(null);
	let pingError = $state<string | null>(null);

	// Alias editing
	let editingAlias = $state(false);
	let aliasInput = $state(currentClient.alias ?? currentClient.name ?? '');
	let aliasSaving = $state(false);
	let aliasError = $state<string | null>(null);

	// Static lease / block state
	let actionLoading = $state(false);
	let actionError = $state<string | null>(null);

	// Copy feedback
	let copiedIp = $state(false);
	let copiedMac = $state(false);

	async function copyToClipboard(text: string, type: 'ip' | 'mac') {
		try {
			await navigator.clipboard.writeText(text);
			if (type === 'ip') {
				copiedIp = true;
				setTimeout(() => (copiedIp = false), 2000);
			} else {
				copiedMac = true;
				setTimeout(() => (copiedMac = false), 2000);
			}
		} catch {
			// Fallback silently
		}
	}

	async function runPortScan() {
		if (portScanning || !currentClient.ip) return;
		portScanning = true;
		portScanError = null;
		try {
			const res = await api.asusRouterScanPorts(widgetId, currentClient.ip);
			portScanResult = res;
		} catch (err) {
			portScanError = err instanceof Error ? err.message : 'Port scan failed';
		} finally {
			portScanning = false;
		}
	}

	async function sendWakeOnLan() {
		if (wolSending || !currentClient.mac) return;
		wolSending = true;
		wolError = null;
		wolSuccess = false;
		try {
			await api.asusRouterWakeOnLan(widgetId, currentClient.mac);
			wolSuccess = true;
			setTimeout(() => (wolSuccess = false), 3500);
		} catch (err) {
			wolError = err instanceof Error ? err.message : 'Wake-on-LAN failed';
		} finally {
			wolSending = false;
		}
	}

	async function runPing() {
		if (pinging || !currentClient.ip) return;
		pinging = true;
		pingError = null;
		try {
			const res = await api.asusRouterPing(widgetId, currentClient.ip);
			pingResult = res;
		} catch (err) {
			pingError = err instanceof Error ? err.message : 'Ping failed';
		} finally {
			pinging = false;
		}
	}

	async function saveAlias() {
		if (aliasSaving || !currentClient.mac) return;
		aliasSaving = true;
		aliasError = null;
		try {
			const res = await api.asusRouterSetClientAlias(widgetId, currentClient.mac, aliasInput.trim());
			currentClient.alias = res.alias || null;
			if (res.alias) {
				currentClient.name = res.alias;
			}
			editingAlias = false;
			onupdate?.(currentClient);
		} catch (err) {
			aliasError = err instanceof Error ? err.message : 'Failed to save alias';
		} finally {
			aliasSaving = false;
		}
	}

	async function toggleInternetBlock() {
		if (actionLoading || !currentClient.mac) return;
		actionLoading = true;
		actionError = null;
		const nextState = !currentClient.internet_blocked;
		try {
			const res = await api.asusRouterSetClientBlock(widgetId, currentClient.mac, nextState);
			currentClient.internet_blocked = res.blocked;
			onupdate?.(currentClient);
		} catch (err) {
			actionError = err instanceof Error ? err.message : 'Failed to update internet access';
		} finally {
			actionLoading = false;
		}
	}

	async function toggleStaticLease() {
		if (actionLoading || !currentClient.mac || !currentClient.ip) return;
		actionLoading = true;
		actionError = null;
		const isCurrentlyStatic = currentClient.ip_type === 'static';
		const nextStatic = !isCurrentlyStatic;
		try {
			const res = await api.asusRouterSetStaticLease(
				widgetId,
				currentClient.mac,
				currentClient.ip,
				currentClient.alias || currentClient.name || '',
				nextStatic,
			);
			currentClient.ip_type = res.static ? 'static' : 'dhcp';
			onupdate?.(currentClient);
		} catch (err) {
			actionError = err instanceof Error ? err.message : 'Failed to update static reservation';
		} finally {
			actionLoading = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onclose();
		}
	}

	function getSignalQuality(rssi: number | null | undefined): { label: string; percent: number; color: string } {
		if (rssi == null) return { label: '', percent: 0, color: 'var(--color-text-muted)' };
		// RSSI typically ranges from -90 dBm (weak) to -30 dBm (strong)
		const percent = Math.min(100, Math.max(10, Math.round(((rssi + 95) / 65) * 100)));
		if (rssi >= -55) return { label: 'Excellent', percent, color: 'var(--color-success)' };
		if (rssi >= -68) return { label: 'Good', percent, color: 'var(--color-accent)' };
		if (rssi >= -80) return { label: 'Fair', percent, color: '#f59e0b' };
		return { label: 'Weak', percent, color: 'var(--color-error)' };
	}

	const signal = $derived(getSignalQuality(currentClient.rssi));
	const webLaunchUrl = $derived(portScanResult?.web_url);
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="modal-backdrop" role="presentation" onclick={onclose}>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div
		class="modal-card"
		role="dialog"
		aria-modal="true"
		aria-labelledby="client-modal-title"
		tabindex="-1"
		onclick={(e) => e.stopPropagation()}
	>
		<!-- Header -->
		<div class="modal-header">
			<div class="title-group">
				<div class="title-row">
					<span class="status-dot" class:offline={!currentClient.online}></span>
					<h2 id="client-modal-title" class="client-title">
						{currentClient.alias || currentClient.name || currentClient.mac}
					</h2>
					{#if currentClient.vendor}
						<span class="vendor-tag">{currentClient.vendor}</span>
					{/if}
				</div>
				{#if currentClient.alias && currentClient.hostname && currentClient.hostname !== currentClient.alias}
					<div class="hostname-sub">({currentClient.hostname})</div>
				{/if}
			</div>
			<button class="close-btn" aria-label={$_('asus_router.detail.close')} onclick={onclose}> &times; </button>
		</div>

		<!-- Action Row -->
		<div class="action-bar">
			{#if webLaunchUrl}
				<a href={webLaunchUrl} target="_blank" rel="noopener noreferrer" class="btn btn-primary launch-btn">
					<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
						<polyline points="15 3 21 3 21 9"></polyline>
						<line x1="10" y1="14" x2="21" y2="3"></line>
					</svg>
					{$_('asus_router.detail.launch_website')}
				</a>
			{/if}

			<button class="btn" disabled={portScanning} onclick={runPortScan}>
				{#if portScanning}
					<span class="spinner"></span>
					{$_('asus_router.detail.scanning_ports')}
				{:else}
					<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
						<circle cx="12" cy="12" r="9"></circle>
						<path d="M12 3v18M3 12h18"></path>
					</svg>
					{$_('asus_router.detail.scan_ports_btn')}
				{/if}
			</button>

			<button class="btn" disabled={wolSending} onclick={sendWakeOnLan}>
				{#if wolSending}
					<span class="spinner"></span>
				{:else}
					<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path>
						<line x1="12" y1="2" x2="12" y2="12"></line>
					</svg>
				{/if}
				{$_('asus_router.detail.wake_on_lan')}
			</button>

			<button class="btn" disabled={pinging} onclick={runPing}>
				{#if pinging}
					<span class="spinner"></span>
					{$_('asus_router.detail.pinging')}
				{:else}
					<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
						<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
					</svg>
					{$_('asus_router.detail.ping')}
				{/if}
			</button>

			{#if isAdmin}
				<button
					class="btn"
					class:btn-danger={!currentClient.internet_blocked}
					class:btn-success={currentClient.internet_blocked}
					disabled={actionLoading}
					onclick={toggleInternetBlock}
				>
					{#if currentClient.internet_blocked}
						{$_('asus_router.detail.unblock_internet')}
					{:else}
						{$_('asus_router.detail.block_internet')}
					{/if}
				</button>
			{/if}
		</div>

		<!-- Notifications / Feedback -->
		{#if wolSuccess}
			<div class="alert alert-success">{$_('asus_router.detail.wol_sent')}</div>
		{/if}
		{#if wolError}
			<div class="alert alert-error">{wolError}</div>
		{/if}
		{#if pingResult}
			<div class="alert" class:alert-info={pingResult.alive} class:alert-warning={!pingResult.alive}>
				{#if pingResult.alive && pingResult.latency_ms != null}
					Ping: {$_('asus_router.detail.ping_result', { values: { ms: pingResult.latency_ms } })}
				{:else}
					{$_('asus_router.detail.device_unresponsive')}
				{/if}
			</div>
		{/if}
		{#if pingError}
			<div class="alert alert-error">{pingError}</div>
		{/if}
		{#if actionError}
			<div class="alert alert-error">{actionError}</div>
		{/if}

		<!-- Details Grid -->
		<div class="info-grid">
			<!-- IP Address -->
			<div class="info-cell">
				<span class="cell-label">{$_('asus_router.detail.ip_address')}</span>
				<div class="cell-value-row">
					<span class="mono-val">{currentClient.ip || '—'}</span>
					{#if currentClient.ip}
						<button
							class="icon-btn"
							aria-label={$_('asus_router.detail.copy')}
							onclick={() => copyToClipboard(currentClient.ip, 'ip')}
						>
							{copiedIp ? $_('asus_router.detail.copied') : $_('asus_router.detail.copy')}
						</button>
					{/if}
				</div>
			</div>

			<!-- MAC Address -->
			<div class="info-cell">
				<span class="cell-label">{$_('asus_router.detail.mac_address')}</span>
				<div class="cell-value-row">
					<span class="mono-val">{currentClient.mac.toUpperCase()}</span>
					<button
						class="icon-btn"
						aria-label={$_('asus_router.detail.copy')}
						onclick={() => copyToClipboard(currentClient.mac, 'mac')}
					>
						{copiedMac ? $_('asus_router.detail.copied') : $_('asus_router.detail.copy')}
					</button>
				</div>
			</div>

			<!-- Connection Type -->
			<div class="info-cell">
				<span class="cell-label">{$_('asus_router.detail.connection')}</span>
				<div class="cell-value-row">
					{#if currentClient.connection_type === 'wired'}
						<span class="badge badge-wired">
							<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2">
								<rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
								<rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
								<line x1="6" y1="6" x2="6.01" y2="6"></line>
								<line x1="6" y1="18" x2="6.01" y2="18"></line>
							</svg>
							{$_('asus_router.detail.wired')} (Ethernet)
						</span>
					{:else if currentClient.connection_type === 'wireless'}
						<span class="badge badge-wireless">
							<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M5 12.55a11 11 0 0 1 14.08 0"></path>
								<path d="M1.42 9a16 16 0 0 1 21.16 0"></path>
								<path d="M8.53 16.11a6 6 0 0 1 6.95 0"></path>
								<line x1="12" y1="20" x2="12.01" y2="20"></line>
							</svg>
							{$_('asus_router.detail.wireless')}
							{currentClient.wireless_band ? `(${currentClient.wireless_band})` : ''}
						</span>
					{:else}
						<span class="badge">{$_('asus_router.detail.unknown_type')}</span>
					{/if}
				</div>
			</div>

			<!-- Signal Strength (if Wireless) -->
			{#if currentClient.connection_type === 'wireless' && currentClient.rssi != null}
				<div class="info-cell">
					<span class="cell-label">{$_('asus_router.detail.signal_strength')}</span>
					<div class="signal-meter-row">
						<div class="meter-bar">
							<div class="meter-fill" style="width: {signal.percent}%; background: {signal.color};"></div>
						</div>
						<span class="meter-text">{currentClient.rssi} dBm ({signal.label})</span>
					</div>
				</div>
			{/if}

			<!-- Link Rates (if available) -->
			{#if currentClient.tx_rate != null || currentClient.rx_rate != null}
				<div class="info-cell">
					<span class="cell-label">{$_('asus_router.detail.link_rate')}</span>
					<div class="cell-value-row">
						<span>
							Tx: {currentClient.tx_rate ?? '—'} Mbps / Rx: {currentClient.rx_rate ?? '—'} Mbps
						</span>
					</div>
				</div>
			{/if}

			<!-- IP Assignment & Static Reservation -->
			<div class="info-cell">
				<span class="cell-label">{$_('asus_router.detail.ip_assignment')}</span>
				<div class="cell-value-row">
					<span class="badge" class:badge-static={currentClient.ip_type === 'static'}>
						{currentClient.ip_type === 'static'
							? $_('asus_router.detail.static_reservation')
							: $_('asus_router.detail.dynamic_dhcp')}
					</span>
					{#if isAdmin}
						<button class="icon-btn" disabled={actionLoading} onclick={toggleStaticLease}>
							{currentClient.ip_type === 'static'
								? $_('asus_router.detail.remove_static')
								: $_('asus_router.detail.make_static')}
						</button>
					{/if}
				</div>
			</div>

			<!-- Internet Access State -->
			<div class="info-cell">
				<span class="cell-label">{$_('asus_router.detail.internet_access')}</span>
				<div class="cell-value-row">
					<span class="badge" class:badge-blocked={currentClient.internet_blocked}>
						{currentClient.internet_blocked
							? $_('asus_router.detail.internet_blocked')
							: $_('asus_router.detail.internet_allowed')}
					</span>
				</div>
			</div>
		</div>

		<!-- Friendly Name / Custom Alias Editor -->
		<div class="alias-section">
			<span class="cell-label">{$_('asus_router.detail.custom_alias')}</span>
			{#if editingAlias}
				<div class="alias-edit-row">
					<input
						type="text"
						bind:value={aliasInput}
						placeholder="e.g. Andy's MacBook Pro"
						maxlength="40"
						disabled={aliasSaving}
					/>
					<button class="btn btn-primary" disabled={aliasSaving} onclick={saveAlias}>
						{#if aliasSaving}
							<span class="spinner"></span>
						{:else}
							{$_('asus_router.detail.save_name')}
						{/if}
					</button>
					<button class="btn" disabled={aliasSaving} onclick={() => (editingAlias = false)}>
						{$_('asus_router.detail.close')}
					</button>
				</div>
				{#if aliasError}
					<p class="error-msg">{aliasError}</p>
				{/if}
			{:else}
				<div class="alias-display-row">
					<span class="alias-val">{currentClient.alias || currentClient.name || '—'}</span>
					{#if isAdmin}
						<button class="icon-btn" onclick={() => (editingAlias = true)}>
							{$_('asus_router.detail.edit_name')}
						</button>
					{/if}
				</div>
			{/if}
		</div>

		<!-- Port Scan Results -->
		<div class="port-scan-section">
			<div class="section-title-row">
				<h3>{$_('asus_router.detail.open_ports')}</h3>
				{#if portScanResult}
					<span class="scanned-time">{new Date(portScanResult.scanned_at).toLocaleTimeString()}</span>
				{/if}
			</div>

			{#if portScanning}
				<div class="scanning-state">
					<span class="spinner large"></span>
					<p>{$_('asus_router.detail.scanning_ports')}</p>
				</div>
			{:else if portScanError}
				<p class="error-msg">{portScanError}</p>
			{:else if portScanResult}
				{#if portScanResult.open_ports.length === 0}
					<p class="hint">{$_('asus_router.detail.no_open_ports')}</p>
				{:else}
					<ul class="ports-list">
						{#each portScanResult.open_ports as port (port.port)}
							<li class="port-item">
								<div class="port-info">
									<span class="port-number">{port.port}</span>
									<span class="port-service">{port.service}</span>
									{#if port.title}
										<span class="port-title">"{port.title}"</span>
									{/if}
								</div>
								{#if port.web_url}
									<a href={port.web_url} target="_blank" rel="noopener noreferrer" class="open-link-btn">
										{$_('asus_router.detail.open_web_link')}
										<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
											<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
											<polyline points="15 3 21 3 21 9"></polyline>
											<line x1="10" y1="14" x2="21" y2="3"></line>
										</svg>
									</a>
								{/if}
							</li>
						{/each}
					</ul>
				{/if}
			{:else}
				<p class="hint">Tap "Scan Ports" to inspect open services & web interfaces.</p>
			{/if}
		</div>
	</div>
</div>

<style>
	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(4px);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 150;
		padding: 1.5rem;
	}

	.modal-card {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		width: 36rem;
		max-width: 100%;
		max-height: 90vh;
		overflow-y: auto;
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
		box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
	}

	.modal-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
	}

	.title-group {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		min-width: 0;
	}

	.title-row {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex-wrap: wrap;
	}

	.client-title {
		margin: 0;
		font-size: 1.35rem;
		font-weight: 700;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.hostname-sub {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.status-dot {
		width: 0.65rem;
		height: 0.65rem;
		border-radius: 50%;
		background: var(--color-success);
		flex-shrink: 0;
	}

	.status-dot.offline {
		background: var(--color-text-muted);
	}

	.vendor-tag {
		font-size: 0.75rem;
		padding: 0.15rem 0.5rem;
		border-radius: 9999px;
		background: rgba(255, 255, 255, 0.08);
		border: 1px solid var(--color-border);
		color: var(--color-text-muted);
	}

	.close-btn {
		background: none;
		border: none;
		font-size: 1.75rem;
		line-height: 1;
		color: var(--color-text-muted);
		cursor: pointer;
		padding: 0.25rem;
		border-radius: 0.25rem;
	}

	.close-btn:hover {
		color: var(--color-text);
	}

	.action-bar {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font: inherit;
		font-size: 0.85rem;
		font-weight: 600;
		padding: 0.45rem 0.8rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: rgba(255, 255, 255, 0.04);
		color: var(--color-text);
		cursor: pointer;
		text-decoration: none;
		transition: background 0.15s ease;
	}

	.btn:hover:not(:disabled) {
		background: rgba(255, 255, 255, 0.1);
	}

	.btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-primary {
		background: var(--color-accent);
		color: var(--color-surface);
		border-color: var(--color-accent);
	}

	.btn-primary:hover:not(:disabled) {
		filter: brightness(1.1);
	}

	.btn-danger {
		color: var(--color-error);
		border-color: rgba(239, 68, 68, 0.3);
	}

	.btn-danger:hover:not(:disabled) {
		background: rgba(239, 68, 68, 0.15);
	}

	.btn-success {
		color: var(--color-success);
		border-color: rgba(16, 185, 129, 0.3);
	}

	.alert {
		font-size: 0.85rem;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
	}

	.alert-success {
		background: rgba(16, 185, 129, 0.15);
		color: var(--color-success);
		border: 1px solid rgba(16, 185, 129, 0.3);
	}

	.alert-error {
		background: rgba(239, 68, 68, 0.15);
		color: var(--color-error);
		border: 1px solid rgba(239, 68, 68, 0.3);
	}

	.alert-info {
		background: rgba(59, 130, 246, 0.15);
		color: var(--color-accent);
		border: 1px solid rgba(59, 130, 246, 0.3);
	}

	.alert-warning {
		background: rgba(245, 158, 11, 0.15);
		color: #f59e0b;
		border: 1px solid rgba(245, 158, 11, 0.3);
	}

	.info-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
		gap: 0.75rem;
	}

	.info-cell {
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.6rem 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.cell-label {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.cell-value-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		font-size: 0.9rem;
	}

	.mono-val {
		font-family: monospace;
		font-size: 0.88rem;
	}

	.icon-btn {
		background: none;
		border: none;
		color: var(--color-accent);
		font-size: 0.8rem;
		cursor: pointer;
		padding: 0.15rem 0.4rem;
		border-radius: 0.25rem;
	}

	.icon-btn:hover {
		text-decoration: underline;
	}

	.badge {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.8rem;
		font-weight: 500;
		padding: 0.2rem 0.5rem;
		border-radius: 0.4rem;
		background: rgba(255, 255, 255, 0.06);
		color: var(--color-text);
	}

	.badge-wired {
		color: #60a5fa;
		background: rgba(96, 165, 250, 0.12);
	}

	.badge-wireless {
		color: #34d399;
		background: rgba(52, 211, 153, 0.12);
	}

	.badge-static {
		color: #a78bfa;
		background: rgba(167, 139, 250, 0.12);
	}

	.badge-blocked {
		color: var(--color-error);
		background: rgba(239, 68, 68, 0.15);
	}

	.signal-meter-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.meter-bar {
		flex: 1;
		height: 0.4rem;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 9999px;
		overflow: hidden;
	}

	.meter-fill {
		height: 100%;
		border-radius: 9999px;
		transition: width 0.3s ease;
	}

	.meter-text {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		white-space: nowrap;
	}

	.alias-section {
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.alias-display-row,
	.alias-edit-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.alias-val {
		font-weight: 600;
		font-size: 0.95rem;
	}

	.alias-edit-row input {
		flex: 1;
		font: inherit;
		font-size: 0.9rem;
		padding: 0.4rem 0.6rem;
		border-radius: 0.4rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.port-scan-section {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		margin-top: 0.25rem;
	}

	.section-title-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
	}

	.section-title-row h3 {
		margin: 0;
		font-size: 1rem;
		font-weight: 600;
	}

	.scanned-time {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.scanning-state {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 1rem;
		background: rgba(255, 255, 255, 0.02);
		border-radius: 0.5rem;
		border: 1px dashed var(--color-border);
	}

	.ports-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.port-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
	}

	.port-info {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.port-number {
		font-family: monospace;
		font-weight: 700;
		font-size: 0.9rem;
		color: var(--color-accent);
	}

	.port-service {
		font-size: 0.85rem;
		font-weight: 500;
	}

	.port-title {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		font-style: italic;
	}

	.open-link-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--color-accent);
		text-decoration: none;
		padding: 0.2rem 0.5rem;
		border-radius: 0.35rem;
		background: rgba(59, 130, 246, 0.1);
	}

	.open-link-btn:hover {
		background: rgba(59, 130, 246, 0.2);
	}

	.hint {
		color: var(--color-text-muted);
		font-size: 0.85rem;
		margin: 0;
	}

	.error-msg {
		color: var(--color-error);
		font-size: 0.85rem;
		margin: 0;
	}

	.spinner {
		width: 0.85rem;
		height: 0.85rem;
		border: 2px solid rgba(255, 255, 255, 0.2);
		border-top-color: currentColor;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	.spinner.large {
		width: 1.25rem;
		height: 1.25rem;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
