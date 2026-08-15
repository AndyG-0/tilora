<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, type TileReportResponse, type TileReportItem } from '$lib/api';
	import { _ } from 'svelte-i18n';

	const TYPE_ICONS: Record<string, string> = {
		weather: '☀️',
		ai_insights: '✨',
		photos: '🖼️',
		movies: '🎬',
		discord: '💬',
		clock: '🕒',
		date: '📅',
		message: '📝',
		rss: '📰',
		bookmarks: '🔖',
		alert: '⚠️',
		calendar: '📆',
		jellyfin: '🍿',
		hdhomerun: '📺',
		pihole: '🛡️',
		game2048: '🔢',
		wordle: '🔤',
		system_monitor: '💻',
		container: '📦',
		docker: '🐳',
		podman: '🦭',
		synology: '💽',
		asus_router: '📶',
		sports: '⚽',
		steam: '🎮',
		bf6: '🎯',
		goodreads: '📚',
		qbittorrent: '⬇️',
		speedtest: '⚡',
		chores: '📋',
		shopping: '🛒',
		packages: '📦',
		nasa_apod: '🚀',
		flights: '✈️',
	};

	let report = $state<TileReportResponse | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	// Filters
	let searchQuery = $state('');
	let selectedTab = $state('all');
	let selectedSource = $state('all');
	let selectedScope = $state('all');

	// Rename Modal State
	let renameModalOpen = $state(false);
	let renamingTile = $state<TileReportItem | null>(null);
	let renameInput = $state('');
	let renameSaving = $state(false);
	let renameError = $state<string | null>(null);

	// Delete Modal State
	let deleteModalOpen = $state(false);
	let deletingTile = $state<TileReportItem | null>(null);
	let deleteInProgress = $state(false);
	let deleteError = $state<string | null>(null);

	async function loadReport() {
		loading = true;
		error = null;
		try {
			report = await api.tilesReport();
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadReport();
	});

	// Derived filtered tiles
	let filteredTiles = $derived.by(() => {
		if (!report) return [];
		return report.tiles.filter((tile) => {
			if (selectedTab !== 'all' && tile.tab_id !== selectedTab) return false;
			if (selectedSource !== 'all' && tile.source !== selectedSource) return false;
			if (selectedScope !== 'all' && tile.settings_scope !== selectedScope) return false;
			if (searchQuery.trim()) {
				const query = searchQuery.trim().toLowerCase();
				const matchName = tile.name.toLowerCase().includes(query);
				const matchCustom = (tile.custom_name ?? '').toLowerCase().includes(query);
				const matchType = tile.type.toLowerCase().includes(query);
				const matchTypeName = tile.type_name.toLowerCase().includes(query);
				const matchId = tile.id.toLowerCase().includes(query);
				const matchTab = tile.tab_name.toLowerCase().includes(query);
				const matchOwnerUser = (tile.owner_user_name ?? '').toLowerCase().includes(query);
				const matchOwnerDevice = (tile.owner_device_name ?? '').toLowerCase().includes(query);
				if (
					!matchName &&
					!matchCustom &&
					!matchType &&
					!matchTypeName &&
					!matchId &&
					!matchTab &&
					!matchOwnerUser &&
					!matchOwnerDevice
				) {
					return false;
				}
			}
			return true;
		});
	});

	// Available tabs for filter dropdown
	let availableTabs = $derived.by(() => {
		if (!report) return [];
		const map = new Map<string, string>();
		for (const t of report.tiles) {
			map.set(t.tab_id, t.tab_name);
		}
		return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
	});

	function openRenameModal(tile: TileReportItem) {
		renamingTile = tile;
		renameInput = tile.custom_name ?? tile.name;
		renameError = null;
		renameModalOpen = true;
	}

	function closeRenameModal() {
		renameModalOpen = false;
		renamingTile = null;
		renameInput = '';
		renameError = null;
	}

	async function handleSaveRename(restoreDefault: boolean = false) {
		if (!renamingTile) return;
		renameSaving = true;
		renameError = null;
		const nameToSave = restoreDefault ? '' : renameInput.trim();

		try {
			const res = await api.renameWidget(renamingTile.id, nameToSave);
			if (report) {
				const updatedTiles = report.tiles.map((t) => {
					if (t.id === renamingTile!.id) {
						const hasCustom = Boolean(nameToSave);
						return {
							...t,
							name: res.name,
							custom_name: hasCustom ? nameToSave : null,
							has_custom_name: hasCustom,
						};
					}
					return t;
				});
				const customNamedCount = updatedTiles.filter((t) => t.has_custom_name).length;
				report = {
					...report,
					summary: {
						...report.summary,
						custom_named_tiles: customNamedCount,
					},
					tiles: updatedTiles,
				};
			}
			closeRenameModal();
		} catch (err) {
			renameError = err instanceof Error ? err.message : String(err);
		} finally {
			renameSaving = false;
		}
	}

	function openDeleteModal(tile: TileReportItem) {
		deletingTile = tile;
		deleteError = null;
		deleteModalOpen = true;
	}

	function closeDeleteModal() {
		deleteModalOpen = false;
		deletingTile = null;
		deleteError = null;
	}

	async function handleConfirmDelete() {
		if (!deletingTile) return;
		deleteInProgress = true;
		deleteError = null;

		try {
			const res = await api.removeWidget(deletingTile.id);
			if (report) {
				if (res.status === 'hidden') {
					// Shared widget was hidden for this device
					const updatedTiles = report.tiles.map((t) => (t.id === deletingTile!.id ? { ...t, is_hidden: true } : t));
					const hiddenCount = updatedTiles.filter((t) => t.is_hidden).length;
					report = {
						...report,
						summary: {
							...report.summary,
							hidden_tiles: hiddenCount,
						},
						tiles: updatedTiles,
					};
				} else {
					// Custom widget was deleted
					const updatedTiles = report.tiles.filter((t) => t.id !== deletingTile!.id);
					report = {
						...report,
						summary: {
							...report.summary,
							total_tiles: updatedTiles.length,
							custom_tiles: updatedTiles.filter((t) => t.source === 'custom').length,
							custom_named_tiles: updatedTiles.filter((t) => t.has_custom_name).length,
							hidden_tiles: updatedTiles.filter((t) => t.is_hidden).length,
						},
						tiles: updatedTiles,
					};
				}
			}
			closeDeleteModal();
		} catch (err) {
			deleteError = err instanceof Error ? err.message : String(err);
		} finally {
			deleteInProgress = false;
		}
	}

	function clearFilters() {
		searchQuery = '';
		selectedTab = 'all';
		selectedSource = 'all';
		selectedScope = 'all';
	}
</script>

<svelte:head>
	<title>{$_('reports.title')} · Tilora</title>
</svelte:head>

<div class="report-container">
	<!-- Top Navigation Header -->
	<header class="report-header">
		<div class="header-left">
			<button class="back-button" onclick={() => goto('/')} aria-label={$_('reports.back_to_dashboard')}>
				<span class="arrow">←</span>
				<span>{$_('reports.back_to_dashboard')}</span>
			</button>
			<div class="header-title-block">
				<h1>{$_('reports.title')}</h1>
				<p class="subtitle">{$_('reports.subtitle')}</p>
			</div>
		</div>
		<div class="header-right">
			<button class="refresh-button" onclick={loadReport} disabled={loading} aria-label={$_('reports.refresh')}>
				<span class="refresh-icon" class:spin={loading}>↻</span>
				<span class="refresh-label">{$_('reports.refresh')}</span>
			</button>
		</div>
	</header>

	{#if loading && !report}
		<div class="state-container">
			<div class="spinner"></div>
			<p>{$_('reports.loading')}</p>
		</div>
	{:else if error && !report}
		<div class="state-container error-state">
			<p class="error-msg">{$_('reports.load_error')}</p>
			<p class="error-detail">{error}</p>
			<button class="retry-button" onclick={loadReport}>{$_('reports.refresh')}</button>
		</div>
	{:else if report}
		<!-- Summary Metrics Bar -->
		<section class="summary-grid" aria-label="Summary Statistics">
			<div class="metric-card" title={$_('reports.summary_total_hint')}>
				<span class="metric-label">{$_('reports.summary_total')}</span>
				<span class="metric-value">{report.summary.total_tiles}</span>
			</div>
			<div class="metric-card" title={$_('reports.summary_builtin_hint')}>
				<span class="metric-label">{$_('reports.summary_builtin')}</span>
				<span class="metric-value">{report.summary.builtin_tiles}</span>
			</div>
			<div class="metric-card" title={$_('reports.summary_custom_hint')}>
				<span class="metric-label">{$_('reports.summary_custom')}</span>
				<span class="metric-value">{report.summary.custom_tiles}</span>
			</div>
			<div class="metric-card" title={$_('reports.summary_custom_named_hint')}>
				<span class="metric-label">{$_('reports.summary_custom_named')}</span>
				<span class="metric-value">{report.summary.custom_named_tiles}</span>
			</div>
			<div class="metric-card" title={$_('reports.summary_hidden_hint')}>
				<span class="metric-label">{$_('reports.summary_hidden')}</span>
				<span class="metric-value">{report.summary.hidden_tiles}</span>
			</div>
			<div class="metric-card" title={$_('reports.summary_tabs_hint')}>
				<span class="metric-label">{$_('reports.summary_tabs')}</span>
				<span class="metric-value">{report.summary.tabs_count}</span>
			</div>
		</section>

		<!-- Search & Filter Controls -->
		<section class="controls-bar" aria-label="Search and Filter Controls">
			<div class="search-input-wrapper">
				<span class="search-icon">🔍</span>
				<input
					type="search"
					bind:value={searchQuery}
					placeholder={$_('reports.search_placeholder')}
					aria-label={$_('reports.search_placeholder')}
				/>
				{#if searchQuery}
					<button class="clear-search" onclick={() => (searchQuery = '')} aria-label="Clear search">✕</button>
				{/if}
			</div>

			<div class="filters-group">
				<select bind:value={selectedTab} aria-label="Filter by tab">
					<option value="all">{$_('reports.filter_all_tabs')}</option>
					{#each availableTabs as tab (tab.id)}
						<option value={tab.id}>{tab.name}</option>
					{/each}
				</select>

				<select bind:value={selectedSource} aria-label="Filter by source">
					<option value="all">{$_('reports.filter_all_sources')}</option>
					<option value="builtin">{$_('reports.source_builtin')}</option>
					<option value="custom">{$_('reports.source_custom')}</option>
				</select>

				<select bind:value={selectedScope} aria-label="Filter by scope">
					<option value="all">{$_('reports.filter_all_scopes')}</option>
					<option value="network">{$_('reports.scope_network')}</option>
					<option value="personal">{$_('reports.scope_personal')}</option>
				</select>
			</div>
		</section>

		<!-- Tiles Inventory List -->
		{#if filteredTiles.length === 0}
			<div class="state-container empty-state">
				<p>{$_('reports.no_tiles_found')}</p>
				<button class="retry-button" onclick={clearFilters}>Clear Filters</button>
			</div>
		{:else}
			<section class="tiles-list" aria-label="Tiles inventory">
				{#each filteredTiles as tile (tile.id)}
					<article class="tile-row-card" class:is-hidden={tile.is_hidden}>
						<div class="card-main">
							<div class="tile-icon-badge" aria-hidden="true">
								{TYPE_ICONS[tile.type] ?? '🧩'}
							</div>

							<div class="tile-details">
								<div class="title-line">
									<h2 class="tile-name">{tile.name}</h2>
									{#if tile.has_custom_name}
										<span class="pill-badge custom-name-pill" title="Custom user-assigned name">
											{$_('reports.badge_custom_name')}
										</span>
									{/if}
									{#if tile.is_hidden}
										<span class="pill-badge hidden-pill">
											{$_('reports.badge_hidden')}
										</span>
									{/if}
									<span class="pill-badge source-pill" class:custom={tile.source === 'custom'}>
										{tile.source === 'custom' ? $_('reports.badge_custom') : $_('reports.badge_builtin')}
									</span>
								</div>

								<div class="meta-row">
									<span class="meta-item id-item">
										<span class="meta-label">ID:</span>
										<code>{tile.id}</code>
									</span>
									<span class="meta-item">
										<span class="meta-label">Type:</span>
										<strong>{tile.type_name}</strong>
									</span>
									<span class="meta-item">
										<span class="meta-label">Tab:</span>
										<span class="tab-chip">🏷️ {tile.tab_name}</span>
									</span>
									<span class="meta-item">
										<span class="meta-label">Size:</span>
										<span
											class="size-chip"
											title="Grid layout: col {tile.layout.col}, row {tile.layout.row}, {tile.layout
												.colSpan} cols × {tile.layout.rowSpan} rows"
										>
											📐 {tile.size_description}
										</span>
									</span>
									<span class="meta-item">
										<span class="meta-label">Scope:</span>
										<span>{tile.settings_scope === 'network' ? '🌐 Shared' : '🔒 Personal'}</span>
									</span>
									{#if tile.owner_user_name && tile.source === 'custom'}
										<span class="meta-item">
											<span class="meta-label">Created by:</span>
											<span>👤 {tile.owner_user_name} ({tile.owner_device_name})</span>
										</span>
									{/if}
								</div>

								<!-- Database Statistics & Details -->
								<div class="db-details-grid">
									{#if tile.network_integration}
										<span class="db-stat-tag integration-tag">
											🔗 Integration: {tile.network_integration}
										</span>
									{/if}
									{#if tile.type === 'chores'}
										<span class="db-stat-tag stat-count-tag">
											📋 {$_('reports.stat_chores', {
												values: { active: tile.stats.chores_active, total: tile.stats.chores_total },
											})}
										</span>
									{/if}
									{#if tile.type === 'shopping'}
										<span class="db-stat-tag stat-count-tag">
											🛒 {$_('reports.stat_shopping', {
												values: { active: tile.stats.shopping_active, total: tile.stats.shopping_total },
											})}
										</span>
									{/if}
									{#if tile.stats.alerts_active > 0}
										<span class="db-stat-tag alert-tag">
											⚠️ {$_('reports.stat_alerts', { values: { count: tile.stats.alerts_active } })}
										</span>
									{/if}
									{#if tile.stats.photos_count > 0}
										<span class="db-stat-tag photo-tag">
											🖼️ {$_('reports.stat_photos', { values: { count: tile.stats.photos_count } })}
										</span>
									{/if}
									{#if tile.stats.packages_count > 0}
										<span class="db-stat-tag package-tag">
											📦 {$_('reports.stat_packages', { values: { count: tile.stats.packages_count } })}
										</span>
									{/if}
									{#if tile.stats.has_custom_settings}
										<span class="db-stat-tag settings-tag">⚙️ {$_('reports.stat_custom_settings')}</span>
									{/if}
									{#if tile.stats.has_device_settings}
										<span class="db-stat-tag device-tag">📱 {$_('reports.stat_device_settings')}</span>
									{/if}
									{#if tile.stats.has_user_settings}
										<span class="db-stat-tag user-tag">👤 {$_('reports.stat_user_settings')}</span>
									{/if}
									{#if tile.stats.has_layout_overrides}
										<span class="db-stat-tag layout-tag">📐 {$_('reports.stat_layout_overrides')}</span>
									{/if}
								</div>
							</div>
						</div>

						<!-- Action Buttons -->
						<div class="card-actions">
							<button
								class="action-btn rename-btn"
								onclick={() => openRenameModal(tile)}
								aria-label="{$_('reports.action_rename')} {tile.name}"
							>
								<span class="btn-icon">✏</span>
								<span>{$_('reports.action_rename')}</span>
							</button>
							<button
								class="action-btn delete-btn"
								onclick={() => openDeleteModal(tile)}
								aria-label="{tile.source === 'custom'
									? $_('reports.action_delete')
									: $_('reports.action_hide')} {tile.name}"
							>
								<span class="btn-icon">🗑</span>
								<span>{tile.source === 'custom' ? $_('reports.action_delete') : $_('reports.action_hide')}</span>
							</button>
						</div>
					</article>
				{/each}
			</section>
		{/if}
	{/if}
</div>

<!-- Rename Modal -->
{#if renameModalOpen && renamingTile}
	<div class="modal-backdrop" role="presentation" onclick={closeRenameModal}>
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<div
			class="modal-box"
			role="dialog"
			tabindex="-1"
			aria-modal="true"
			aria-labelledby="rename-title"
			onclick={(e) => e.stopPropagation()}
		>
			<h3 id="rename-title">{$_('reports.rename_modal_title')}</h3>
			<p class="modal-hint">{$_('reports.rename_modal_hint')}</p>

			{#if renameError}
				<div class="modal-error" role="alert">{renameError}</div>
			{/if}

			<div class="form-group">
				<label for="rename-input">{$_('reports.rename_input_label')}</label>
				<input
					id="rename-input"
					type="text"
					bind:value={renameInput}
					placeholder={renamingTile.default_name || $_('reports.rename_input_placeholder')}
					maxlength="60"
					onkeydown={(e) => {
						if (e.key === 'Enter') handleSaveRename(false);
						if (e.key === 'Escape') closeRenameModal();
					}}
				/>
			</div>

			<div class="modal-buttons">
				{#if renamingTile.has_custom_name}
					<button
						type="button"
						class="btn secondary-btn"
						onclick={() => handleSaveRename(true)}
						disabled={renameSaving}
					>
						{$_('reports.rename_clear')}
					</button>
				{/if}
				<div class="modal-right-buttons">
					<button type="button" class="btn cancel-btn" onclick={closeRenameModal} disabled={renameSaving}>
						{$_('reports.rename_cancel')}
					</button>
					<button type="button" class="btn confirm-btn" onclick={() => handleSaveRename(false)} disabled={renameSaving}>
						{renameSaving ? $_('reports.rename_saving') : $_('reports.rename_save')}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}

<!-- Delete / Hide Modal -->
{#if deleteModalOpen && deletingTile}
	<div class="modal-backdrop" role="presentation" onclick={closeDeleteModal}>
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<div
			class="modal-box"
			role="dialog"
			tabindex="-1"
			aria-modal="true"
			aria-labelledby="delete-title"
			onclick={(e) => e.stopPropagation()}
		>
			<h3 id="delete-title">
				{deletingTile.source === 'custom' ? $_('reports.delete_modal_title') : $_('reports.hide_modal_title')}
			</h3>
			<p class="modal-hint">
				{deletingTile.source === 'custom'
					? $_('reports.delete_modal_text', { values: { name: deletingTile.name } })
					: $_('reports.hide_modal_text', { values: { name: deletingTile.name } })}
			</p>

			{#if deleteError}
				<div class="modal-error" role="alert">{deleteError}</div>
			{/if}

			<div class="modal-buttons modal-right-only">
				<button type="button" class="btn cancel-btn" onclick={closeDeleteModal} disabled={deleteInProgress}>
					{$_('reports.delete_cancel')}
				</button>
				<button type="button" class="btn danger-btn" onclick={handleConfirmDelete} disabled={deleteInProgress}>
					{deleteInProgress
						? $_('reports.delete_in_progress')
						: deletingTile.source === 'custom'
							? $_('reports.delete_confirm')
							: $_('reports.hide_confirm')}
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.report-container {
		max-width: 1200px;
		margin: 0 auto;
		padding: 1.5rem 1rem 4rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	/* Header */
	.report-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
		padding-bottom: 1rem;
		border-bottom: 1px solid var(--color-border);
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: 1.25rem;
		flex-wrap: wrap;
	}

	.back-button {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		background: var(--color-surface);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.85rem;
		font-size: 0.9rem;
		cursor: pointer;
		transition: background 0.15s ease;
	}

	.back-button:hover {
		background: var(--color-surface-hover);
	}

	.header-title-block h1 {
		margin: 0;
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--color-text);
		letter-spacing: -0.01em;
	}

	.header-title-block .subtitle {
		margin: 0.2rem 0 0;
		font-size: 0.875rem;
		color: var(--color-text-muted);
	}

	.refresh-button {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		background: var(--color-surface);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.85rem;
		font-size: 0.9rem;
		cursor: pointer;
		transition: background 0.15s ease;
	}

	.refresh-button:hover:not(:disabled) {
		background: var(--color-surface-hover);
	}

	.refresh-icon.spin {
		display: inline-block;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		from {
			transform: rotate(0deg);
		}
		to {
			transform: rotate(360deg);
		}
	}

	/* Summary Metrics */
	.summary-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 0.75rem;
	}

	.metric-card {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.85rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		cursor: help;
		transition:
			border-color 0.15s ease,
			transform 0.15s ease;
	}

	.metric-card:hover {
		border-color: var(--color-accent);
	}

	.metric-label {
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--color-text-muted);
	}

	.metric-value {
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--color-accent);
	}

	/* Search & Filters Controls */
	.controls-bar {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		align-items: center;
		justify-content: space-between;
	}

	.search-input-wrapper {
		position: relative;
		flex: 1 1 280px;
		display: flex;
		align-items: center;
	}

	.search-icon {
		position: absolute;
		left: 0.75rem;
		font-size: 0.85rem;
		pointer-events: none;
		color: var(--color-text-muted);
	}

	.search-input-wrapper input {
		width: 100%;
		padding: 0.55rem 2rem 0.55rem 2.2rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		font-size: 0.9rem;
	}

	.search-input-wrapper input:focus {
		outline: 2px solid var(--color-accent);
	}

	.clear-search {
		position: absolute;
		right: 0.6rem;
		background: transparent;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		font-size: 0.85rem;
	}

	.filters-group {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.filters-group select {
		padding: 0.55rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		font-size: 0.85rem;
		cursor: pointer;
	}

	.filters-group select:focus {
		outline: 2px solid var(--color-accent);
	}

	/* State Containers */
	.state-container {
		min-height: 250px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		text-align: center;
		color: var(--color-text-muted);
		background: var(--color-surface);
		border: 1px dashed var(--color-border);
		border-radius: 0.75rem;
		padding: 2rem;
	}

	.error-state {
		color: var(--color-error);
	}

	.error-msg {
		font-weight: 600;
		margin: 0;
	}

	.error-detail {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin: 0;
	}

	.spinner {
		width: 2rem;
		height: 2rem;
		border: 3px solid var(--color-border);
		border-top-color: var(--color-accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	.retry-button {
		background: var(--color-accent);
		color: var(--color-on-accent);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
		font-size: 0.875rem;
		font-weight: 600;
	}

	/* Tiles List */
	.tiles-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.tile-row-card {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem 1.25rem;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		transition:
			border-color 0.15s ease,
			box-shadow 0.15s ease;
	}

	.tile-row-card:hover {
		border-color: var(--color-accent);
	}

	.tile-row-card.is-hidden {
		opacity: 0.65;
	}

	.card-main {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
		flex: 1 1 auto;
		min-width: 0;
	}

	.tile-icon-badge {
		font-size: 1.75rem;
		line-height: 1;
		padding: 0.5rem;
		background: var(--color-bg);
		border-radius: 0.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.tile-details {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		min-width: 0;
		flex: 1 1 auto;
	}

	.title-line {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.tile-name {
		margin: 0;
		font-size: 1.1rem;
		font-weight: 600;
		color: var(--color-text);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.pill-badge {
		font-size: 0.7rem;
		font-weight: 600;
		padding: 0.15rem 0.45rem;
		border-radius: 0.35rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}

	.custom-name-pill {
		background: rgba(91, 141, 250, 0.15);
		color: var(--color-accent);
		border: 1px solid rgba(91, 141, 250, 0.3);
	}

	.hidden-pill {
		background: rgba(224, 160, 90, 0.15);
		color: var(--color-warning);
		border: 1px solid rgba(224, 160, 90, 0.3);
	}

	.source-pill {
		background: var(--color-bg);
		color: var(--color-text-muted);
		border: 1px solid var(--color-border);
	}

	.source-pill.custom {
		background: rgba(76, 175, 125, 0.15);
		color: var(--color-success);
		border: 1px solid rgba(76, 175, 125, 0.3);
	}

	.meta-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.85rem;
		font-size: 0.825rem;
		color: var(--color-text-muted);
		align-items: center;
	}

	.meta-item {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}

	.meta-item code {
		background: var(--color-bg);
		padding: 0.1rem 0.35rem;
		border-radius: 0.25rem;
		font-size: 0.775rem;
		color: var(--color-text);
		border: 1px solid var(--color-border);
	}

	.tab-chip,
	.size-chip {
		background: var(--color-bg);
		padding: 0.15rem 0.45rem;
		border-radius: 0.35rem;
		font-size: 0.8rem;
		color: var(--color-text);
		border: 1px solid var(--color-border);
	}

	.db-details-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-top: 0.2rem;
	}

	.db-stat-tag {
		font-size: 0.75rem;
		padding: 0.15rem 0.45rem;
		border-radius: 0.3rem;
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border);
	}

	.stat-count-tag {
		background: rgba(91, 141, 250, 0.1);
		color: var(--color-accent);
		border-color: rgba(91, 141, 250, 0.25);
	}

	.alert-tag {
		background: rgba(224, 90, 90, 0.1);
		color: var(--color-error);
		border-color: rgba(224, 90, 90, 0.25);
	}

	.integration-tag {
		background: rgba(74, 158, 218, 0.1);
		color: var(--color-info);
		border-color: rgba(74, 158, 218, 0.25);
	}

	/* Card Actions */
	.card-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.action-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.45rem 0.75rem;
		border-radius: 0.5rem;
		font-size: 0.85rem;
		font-weight: 500;
		cursor: pointer;
		border: 1px solid var(--color-border);
		background: var(--color-bg);
		color: var(--color-text);
		transition: all 0.15s ease;
	}

	.action-btn:hover {
		background: var(--color-surface-hover);
	}

	.rename-btn:hover {
		border-color: var(--color-accent);
		color: var(--color-accent);
	}

	.delete-btn:hover {
		border-color: var(--color-error);
		color: var(--color-error);
	}

	/* Modal Styles */
	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}

	.modal-box {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.85rem;
		padding: 1.5rem;
		width: 100%;
		max-width: 450px;
		display: flex;
		flex-direction: column;
		gap: 1rem;
		box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
	}

	.modal-box h3 {
		margin: 0;
		font-size: 1.25rem;
		color: var(--color-text);
	}

	.modal-hint {
		margin: 0;
		font-size: 0.875rem;
		color: var(--color-text-muted);
		line-height: 1.4;
	}

	.modal-error {
		background: rgba(224, 90, 90, 0.15);
		color: var(--color-error);
		border: 1px solid var(--color-error);
		border-radius: 0.4rem;
		padding: 0.5rem 0.75rem;
		font-size: 0.85rem;
	}

	.form-group {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.form-group label {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--color-text-muted);
	}

	.form-group input {
		padding: 0.6rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-bg);
		color: var(--color-text);
		font-size: 0.95rem;
	}

	.form-group input:focus {
		outline: 2px solid var(--color-accent);
	}

	.modal-buttons {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		margin-top: 0.5rem;
		flex-wrap: wrap;
	}

	.modal-right-only {
		justify-content: flex-end;
	}

	.modal-right-buttons {
		display: flex;
		gap: 0.5rem;
		margin-left: auto;
	}

	.btn {
		padding: 0.5rem 0.9rem;
		border-radius: 0.5rem;
		font-size: 0.875rem;
		font-weight: 600;
		cursor: pointer;
		border: none;
		transition: opacity 0.15s ease;
	}

	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.cancel-btn {
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border);
	}

	.confirm-btn {
		background: var(--color-accent);
		color: var(--color-on-accent);
	}

	.secondary-btn {
		background: transparent;
		color: var(--color-text-muted);
		border: 1px solid var(--color-border);
		font-size: 0.8rem;
	}

	.secondary-btn:hover:not(:disabled) {
		color: var(--color-text);
		background: var(--color-surface-hover);
	}

	.danger-btn {
		background: var(--color-error);
		color: #ffffff;
	}

	@media (max-width: 768px) {
		.tile-row-card {
			flex-direction: column;
			align-items: stretch;
		}

		.card-actions {
			justify-content: flex-end;
			border-top: 1px solid var(--color-border);
			padding-top: 0.75rem;
		}
	}
</style>
