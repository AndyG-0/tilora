<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { widgets, applyLayoutUpdates, addWidgetLocal, removeWidgetLocal } from '$lib/stores/widgets';
	import { tabs } from '$lib/stores/tabs';
	import { activeTabIndex } from '$lib/stores/activeTab';
	import { theme, persistTheme } from '$lib/stores/theme';
	import { user, logout } from '$lib/stores/user';
	import { api, type WidgetLayout, type WidgetSummaryMeta } from '$lib/api';
	import { groupWidgetsByTab, resolveSwipe } from '$lib/tabNavigation';
	import { computeResizedLayout, MAX_ROW_SPAN } from '$lib/resize';
	import { computeEmptyCells, isRectFree } from '$lib/layout';
	import { isSpeechRecognitionSupported, listenOnce, speak } from '$lib/speech';
	import { TILE_COMPONENTS } from '$lib/widgetComponents';

	// Matches the `.grid`'s `grid-template-columns: repeat(4, 1fr)` below —
	// caps how wide a tile can grow when resizing.
	const GRID_COLUMNS = 4;

	const THEME_ICONS: Record<string, string> = {
		light: '🌙',
		dark: '☀️',
		sepia: '◐',
		contrast: '◑',
	};

	// Fallback matches the backend's default set; refreshed from /api/theme
	// on mount so new themes show up without a frontend redeploy.
	let themeIds = $state(['light', 'dark', 'sepia', 'contrast']);
	let updateAvailable = $state(false);

	async function checkVersion() {
		try {
			const info = await api.version();
			updateAvailable = info.update_available;
		} catch {
			// keep the last known value
		}
	}

	onMount(() => {
		api
			.themes()
			.then(({ themes }) => {
				themeIds = themes.map((t) => t.id);
			})
			.catch(() => {
				// keep the fallback list
			});

		// The backend only rechecks GitHub once a day; an hourly poll here
		// is just to pick that up without requiring a page reload on a
		// kiosk that stays open for weeks at a time.
		checkVersion();
		const interval = setInterval(checkVersion, 60 * 60 * 1000);
		return () => clearInterval(interval);
	});

	function cycleTheme() {
		let next = '';
		theme.update((current) => {
			const index = themeIds.indexOf(current);
			next = themeIds[(index + 1) % themeIds.length];
			return next;
		});
		persistTheme(next);
	}

	let profileMenuOpen = $state(false);

	function toggleProfileMenu() {
		profileMenuOpen = !profileMenuOpen;
	}

	async function switchProfile() {
		profileMenuOpen = false;
		await logout().catch(() => {});
		goto('/login');
	}

	const grouped = $derived(groupWidgetsByTab($widgets, $tabs));
	const clampedIndex = $derived(Math.min($activeTabIndex, Math.max(grouped.length - 1, 0)));

	function goToTab(index: number) {
		activeTabIndex.set(Math.min(Math.max(index, 0), grouped.length - 1));
	}

	let touchStartX = 0;
	let touchStartY = 0;

	function onTouchStart(event: TouchEvent) {
		if (editMode) return;
		touchStartX = event.touches[0].clientX;
		touchStartY = event.touches[0].clientY;
	}

	function onTouchEnd(event: TouchEvent) {
		if (editMode) return;
		const deltaX = event.changedTouches[0].clientX - touchStartX;
		const deltaY = event.changedTouches[0].clientY - touchStartY;
		const direction = resolveSwipe(deltaX, deltaY);
		if (direction !== 0) goToTab(clampedIndex + direction);
	}

	// Drag-to-rearrange: dragging one tile onto another swaps their grid
	// positions (each keeps its own span); dragging onto empty grid space
	// moves it there instead. Both persist via PUT /api/widgets/layout. Uses
	// elementFromPoint rather than manual grid geometry so it works regardless
	// of column/row sizing — empty cells get invisible marker elements (see
	// the template) so they're hit-testable too.
	let editMode = $state(false);
	let dragWidgetId = $state<string | null>(null);
	let dragDelta = $state({ x: 0, y: 0 });
	let dropTargetId = $state<string | null>(null);
	let dropEmptyCell = $state<{ col: number; row: number } | null>(null);
	let dragStart = { x: 0, y: 0 };

	function toggleEditMode() {
		editMode = !editMode;
	}

	function onCellPointerDown(event: PointerEvent, widgetId: string) {
		if (!editMode) return;
		event.preventDefault();
		(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
		dragWidgetId = widgetId;
		dragStart = { x: event.clientX, y: event.clientY };
		dragDelta = { x: 0, y: 0 };
		dropTargetId = null;
		dropEmptyCell = null;
	}

	function onCellPointerMove(event: PointerEvent) {
		if (!dragWidgetId) return;
		dragDelta = { x: event.clientX - dragStart.x, y: event.clientY - dragStart.y };
		const hovered = document.elementFromPoint(event.clientX, event.clientY);

		const hoveredWidget = hovered?.closest<HTMLElement>('[data-widget-id]');
		const hoveredWidgetId = hoveredWidget?.dataset.widgetId ?? null;
		if (hoveredWidgetId && hoveredWidgetId !== dragWidgetId) {
			dropTargetId = hoveredWidgetId;
			dropEmptyCell = null;
			return;
		}
		dropTargetId = null;

		const hoveredEmpty = hovered?.closest<HTMLElement>('[data-empty-cell]');
		const source = $widgets.find((w) => w.id === dragWidgetId);
		if (hoveredEmpty && source) {
			const col = Number(hoveredEmpty.dataset.col);
			const row = Number(hoveredEmpty.dataset.row);
			const target = { ...source.layout, col, row };
			const siblings = $widgets.filter((w) => w.tab === source.tab);
			dropEmptyCell = isRectFree(siblings, source.id, target, GRID_COLUMNS) ? { col, row } : null;
		} else {
			dropEmptyCell = null;
		}
	}

	async function onCellPointerUp() {
		const sourceId = dragWidgetId;
		const targetId = dropTargetId;
		const emptyCell = dropEmptyCell;
		dragWidgetId = null;
		dropTargetId = null;
		dropEmptyCell = null;
		dragDelta = { x: 0, y: 0 };
		if (!sourceId) return;

		const source = $widgets.find((w) => w.id === sourceId);
		if (!source) return;

		if (targetId) {
			const target = $widgets.find((w) => w.id === targetId);
			if (!target) return;
			const updates = [
				{ id: source.id, layout: target.layout },
				{ id: target.id, layout: source.layout },
			];
			await api.updateWidgetsLayout(updates);
			applyLayoutUpdates(updates);
		} else if (emptyCell) {
			const updates = [{ id: source.id, layout: { ...source.layout, col: emptyCell.col, row: emptyCell.row } }];
			await api.updateWidgetsLayout(updates);
			applyLayoutUpdates(updates);
		}
	}

	// Resize: dragging a tile's corner handle grows/shrinks its colSpan/rowSpan,
	// persisted via the same PUT /api/widgets/layout endpoint the rearrange
	// drag uses. Pointer capture is set on the handle itself so a drag started
	// there doesn't get reinterpreted as a rearrange, but move/up are handled
	// at the window level below (not on the handle) — pointer-capture retargeting
	// of move events isn't reliably delivered for mouse input across browsers,
	// which broke bottom-edge auto-scroll for mouse/trackpad while working fine
	// for touch.
	let resizeWidgetId = $state<string | null>(null);
	let resizeStartLayout: WidgetLayout | null = null;
	let resizeCellSize = { width: 100, height: 100 };
	let resizeStart = { x: 0, y: 0 };
	let resizePreviewLayout = $state<WidgetLayout | null>(null);
	let resizeLastPointer = { x: 0, y: 0 };

	// Auto-scroll while resizing: on a kiosk the viewport is the physical
	// screen, so a widget near the bottom can't grow past window height by
	// pointer movement alone — there's no room below to drag into. Instead,
	// holding the handle near the bottom edge scrolls the tab panel, and the
	// scrolled distance is folded into the resize delta so the tile keeps
	// growing even though the pointer itself stops moving.
	const AUTOSCROLL_EDGE = 60;
	const AUTOSCROLL_MAX_SPEED = 16;
	let resizeScrollOffset = 0;
	let resizeScrollContainer: HTMLElement | null = null;
	let autoScrollSpeed = 0;
	let autoScrollFrame: number | null = null;

	function onResizePointerDown(event: PointerEvent, widget: WidgetSummaryMeta) {
		if (!editMode) return;
		event.stopPropagation();
		event.preventDefault();
		const handle = event.currentTarget as HTMLElement;
		handle.setPointerCapture(event.pointerId);

		const cellRect = handle.closest<HTMLElement>('[data-widget-id]')?.getBoundingClientRect();
		resizeCellSize = {
			width: (cellRect?.width ?? widget.layout.colSpan * 100) / widget.layout.colSpan,
			height: (cellRect?.height ?? widget.layout.rowSpan * 100) / widget.layout.rowSpan,
		};
		resizeWidgetId = widget.id;
		resizeStartLayout = widget.layout;
		resizePreviewLayout = widget.layout;
		resizeStart = { x: event.clientX, y: event.clientY };
		resizeLastPointer = { x: event.clientX, y: event.clientY };
		resizeScrollOffset = 0;
		resizeScrollContainer = handle.closest<HTMLElement>('.tab-panel');
	}

	function updateResizePreview() {
		if (!resizeWidgetId || !resizeStartLayout) return;
		resizePreviewLayout = computeResizedLayout(
			resizeStartLayout,
			resizeLastPointer.x - resizeStart.x,
			resizeLastPointer.y - resizeStart.y + resizeScrollOffset,
			resizeCellSize.width,
			resizeCellSize.height,
			GRID_COLUMNS,
		);
	}

	function runAutoScroll() {
		autoScrollFrame = null;
		if (!resizeScrollContainer || autoScrollSpeed === 0) return;
		const before = resizeScrollContainer.scrollTop;
		resizeScrollContainer.scrollTop += autoScrollSpeed;
		const scrolled = resizeScrollContainer.scrollTop - before;
		if (scrolled !== 0) {
			resizeScrollOffset += scrolled;
			updateResizePreview();
			autoScrollFrame = requestAnimationFrame(runAutoScroll);
		}
	}

	function stopAutoScroll() {
		autoScrollSpeed = 0;
		resizeScrollContainer = null;
		if (autoScrollFrame !== null) {
			cancelAnimationFrame(autoScrollFrame);
			autoScrollFrame = null;
		}
	}

	function onResizePointerMove(event: PointerEvent) {
		if (!resizeWidgetId) return;
		resizeLastPointer = { x: event.clientX, y: event.clientY };
		updateResizePreview();

		const distanceFromBottom = window.innerHeight - event.clientY;
		autoScrollSpeed =
			distanceFromBottom < AUTOSCROLL_EDGE
				? Math.ceil(((AUTOSCROLL_EDGE - distanceFromBottom) / AUTOSCROLL_EDGE) * AUTOSCROLL_MAX_SPEED)
				: 0;

		if (autoScrollSpeed !== 0 && autoScrollFrame === null) {
			autoScrollFrame = requestAnimationFrame(runAutoScroll);
		}
	}

	async function onResizePointerUp() {
		stopAutoScroll();
		const widgetId = resizeWidgetId;
		const layout = resizePreviewLayout;
		resizeWidgetId = null;
		resizeStartLayout = null;
		resizePreviewLayout = null;
		if (!widgetId || !layout) return;

		const updates = [{ id: widgetId, layout }];
		await api.updateWidgetsLayout(updates);
		applyLayoutUpdates(updates);
	}

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowRight') goToTab(clampedIndex + 1);
		else if (event.key === 'ArrowLeft') goToTab(clampedIndex - 1);
	}

	// Mic button: capture one spoken command, route it through the AI
	// tool-calling loop, then show + speak the answer. `assistantState` is a
	// small local union rather than a store since nothing outside this page
	// needs it.
	type AssistantState =
		| { status: 'idle' }
		| { status: 'listening' }
		| { status: 'thinking'; query: string }
		| { status: 'answered'; query: string; answer: string }
		| { status: 'error'; message: string };

	let assistantState = $state<AssistantState>({ status: 'idle' });
	const micSupported = isSpeechRecognitionSupported();

	async function startListening() {
		assistantState = { status: 'listening' };
		let query: string;
		try {
			query = await listenOnce();
		} catch {
			assistantState = { status: 'error', message: "Didn't catch that." };
			return;
		}

		assistantState = { status: 'thinking', query };
		try {
			const { text } = await api.askAssistant(query);
			assistantState = { status: 'answered', query, answer: text };
			speak(text);
		} catch {
			assistantState = { status: 'error', message: "Couldn't get an answer." };
		}
	}

	function dismissAssistant() {
		assistantState = { status: 'idle' };
	}

	// Add/remove widgets: edit mode gains a "✕" per cell and a "+ Add widget"
	// tile that opens a small inline type picker. No naming/id prompt — the
	// backend generates the id.
	let addingWidget = $state(false);
	let widgetTypeOptions = $state<
		{ type: string; name: string; default_layout: { colSpan: number; rowSpan: number } }[]
	>([]);

	async function handleRemoveWidget(event: Event, widgetId: string) {
		event.stopPropagation();
		await api.removeWidget(widgetId);
		removeWidgetLocal(widgetId);
	}

	async function openAddWidget() {
		addingWidget = true;
		widgetTypeOptions = await api.widgetTypes();
	}

	function closeAddWidget() {
		addingWidget = false;
	}

	async function selectWidgetType(
		option: { type: string; default_layout: { colSpan: number; rowSpan: number } },
		tabId: string,
	) {
		const tabWidgets = $widgets.filter((w) => w.tab === tabId);
		const maxRow = Math.max(0, ...tabWidgets.map((w) => w.layout.row + w.layout.rowSpan - 1));
		const layout: WidgetLayout = { col: 1, row: maxRow + 1, ...option.default_layout };
		addingWidget = false;
		const newWidget = await api.addWidget(option.type, layout, tabId);
		addWidgetLocal(newWidget);
	}
</script>

<svelte:window
	onkeydown={onKeydown}
	onpointermove={(e) => {
		onCellPointerMove(e);
		onResizePointerMove(e);
	}}
	onpointerup={() => {
		onCellPointerUp();
		onResizePointerUp();
	}}
	onpointercancel={() => {
		onCellPointerUp();
		onResizePointerUp();
	}}
/>

<div class="top-bar">
	{#if micSupported}
		<button
			class="icon-button"
			class:active={assistantState.status === 'listening'}
			onclick={startListening}
			disabled={assistantState.status === 'listening' || assistantState.status === 'thinking'}
			aria-label="Ask a question"
		>
			🎙
		</button>
	{/if}
	<button class="icon-button" onclick={() => goto('/settings')} aria-label="Settings">
		⚙
		{#if updateAvailable}
			<span class="update-badge" aria-label="Update available"></span>
		{/if}
	</button>
	<button class="icon-button" onclick={cycleTheme} aria-label="Change theme">
		{THEME_ICONS[$theme] ?? '🎨'}
	</button>
	<button
		class="icon-button"
		class:active={editMode}
		onclick={toggleEditMode}
		aria-label={editMode ? 'Done rearranging' : 'Rearrange widgets'}
	>
		{editMode ? '✓' : '✎'}
	</button>
	{#if $user}
		<div class="profile-menu-wrap">
			<button
				class="icon-button"
				class:active={profileMenuOpen}
				onclick={toggleProfileMenu}
				aria-label="Profile"
			>
				{$user.avatar || $user.name.charAt(0).toUpperCase()}
			</button>
			{#if profileMenuOpen}
				<div class="profile-menu">
					<p class="profile-menu-name">{$user.name}</p>
					<button class="profile-menu-action" onclick={switchProfile}>Switch profile</button>
				</div>
			{/if}
		</div>
	{/if}
</div>

{#if assistantState.status !== 'idle'}
	<div class="assistant-overlay" role="status">
		{#if assistantState.status === 'listening'}
			<p>Listening…</p>
		{:else if assistantState.status === 'thinking'}
			<p class="query">{assistantState.query}</p>
			<p>Thinking…</p>
		{:else if assistantState.status === 'answered'}
			<p class="query">{assistantState.query}</p>
			<p>{assistantState.answer}</p>
			<button class="dismiss" onclick={dismissAssistant}>Dismiss</button>
		{:else if assistantState.status === 'error'}
			<p>{assistantState.message}</p>
			<button class="dismiss" onclick={dismissAssistant}>Dismiss</button>
		{/if}
	</div>
{/if}

<div class="tabs-viewport" role="presentation" ontouchstart={onTouchStart} ontouchend={onTouchEnd}>
	<div class="tabs-track" style="transform: translateX(-{clampedIndex * 100}vw)">
		{#each grouped as tab, tabIndex (tab.id)}
			<div class="tab-panel">
				<div
					class="grid"
					class:resize-active={resizeWidgetId !== null}
					style="--resize-scroll-buffer: {MAX_ROW_SPAN * 13}rem"
				>
					{#each tab.widgets as widget (widget.id)}
						{@const Tile = TILE_COMPONENTS[widget.type]}
						{@const layout = resizeWidgetId === widget.id && resizePreviewLayout ? resizePreviewLayout : widget.layout}
						<div
							class="cell"
							class:editing={editMode}
							class:dragging={dragWidgetId === widget.id}
							class:resizing={resizeWidgetId === widget.id}
							class:drop-target={dropTargetId === widget.id}
							data-widget-id={widget.id}
							role="presentation"
							style="grid-column: {layout.col} / span {layout.colSpan}; grid-row: {layout.row} / span {layout.rowSpan}; {dragWidgetId ===
							widget.id
								? `transform: translate(${dragDelta.x}px, ${dragDelta.y}px);`
								: ''}"
							onpointerdown={(e) => onCellPointerDown(e, widget.id)}
							onpointerup={onCellPointerUp}
							onpointercancel={onCellPointerUp}
						>
							{#if Tile}
								<Tile widgetId={widget.id} />
							{/if}
							{#if editMode}
								<div class="edit-overlay" aria-hidden="true"></div>
								<button
									class="remove-button"
									onpointerdown={(e) => e.stopPropagation()}
									onclick={(e) => handleRemoveWidget(e, widget.id)}
									aria-label="Remove widget"
								>
									✕
								</button>
								<button
									class="resize-handle"
									onpointerdown={(e) => onResizePointerDown(e, widget)}
									onpointerup={onResizePointerUp}
									onpointercancel={onResizePointerUp}
									aria-label="Resize widget"
								>
									⤡
								</button>
							{/if}
						</div>
					{/each}
					{#if dragWidgetId && tabIndex === clampedIndex}
						{@const emptyCells = computeEmptyCells(tab.widgets, dragWidgetId, GRID_COLUMNS)}
						{#each emptyCells as cell (cell.col + '-' + cell.row)}
							<div
								class="empty-cell"
								data-empty-cell="true"
								data-col={cell.col}
								data-row={cell.row}
								style="grid-column: {cell.col} / span 1; grid-row: {cell.row} / span 1;"
								role="presentation"
							></div>
						{/each}
						{#if dropEmptyCell}
							{@const source = $widgets.find((w) => w.id === dragWidgetId)}
							{#if source}
								<div
									class="drop-ghost"
									style="grid-column: {dropEmptyCell.col} / span {source.layout
										.colSpan}; grid-row: {dropEmptyCell.row} / span {source.layout.rowSpan};"
									aria-hidden="true"
								></div>
							{/if}
						{/if}
					{/if}
					{#if editMode && tabIndex === clampedIndex}
						<div class="cell add-widget-cell" style="grid-column: auto; grid-row: auto;">
							<button class="add-widget-button" onclick={openAddWidget}>+ Add widget</button>
							{#if addingWidget}
								<div class="widget-picker">
									{#each widgetTypeOptions as option (option.type)}
										<button class="widget-picker-option" onclick={() => selectWidgetType(option, tab.id)}>
											{option.name}
										</button>
									{/each}
									<button class="widget-picker-cancel" onclick={closeAddWidget}>Cancel</button>
								</div>
							{/if}
						</div>
					{/if}
				</div>
			</div>
		{/each}
	</div>
</div>

{#if grouped.length > 1}
	<div class="tab-dots">
		{#each grouped as tab, i (tab.id)}
			<button class="dot" class:active={i === clampedIndex} aria-label={tab.name} onclick={() => goToTab(i)}></button>
		{/each}
	</div>
{/if}

<style>
	.tabs-viewport {
		overflow: hidden;
		touch-action: pan-y;
		height: 100vh;
	}

	.tabs-track {
		display: flex;
		height: 100%;
		transition: transform 0.25s ease;
	}

	.tab-panel {
		flex: 0 0 100vw;
		min-width: 0;
		height: 100%;
		overflow-y: auto;
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		grid-auto-rows: 12rem;
		gap: 1rem;
		padding: 1.5rem;
		min-height: 100vh;
	}

	/* The col/row/colSpan/rowSpan layout each tile carries from dashboard.yaml
	   is a 2D arrangement designed for a wide kiosk touchscreen — it doesn't
	   have a sensible reflow at 4 columns' worth of width, so below this
	   breakpoint every tile is stacked full-width in DOM order instead,
	   overriding each `.cell`'s inline grid-column/grid-row (set per-widget
	   in the markup below) rather than trying to preserve their original
	   grid position. */
	@media (max-width: 700px) {
		.grid {
			grid-template-columns: 1fr;
			grid-auto-rows: minmax(12rem, auto);
			padding: 1rem;
		}

		.cell {
			grid-column: 1 / -1 !important;
			grid-row: auto !important;
		}
	}

	/* Reserves scroll room for the whole drag, not just what the resize has
	   grown so far — a bottom-row widget starts with zero overflow to scroll
	   into, so waiting for the resize to create room first is a deadlock. */
	.grid.resize-active {
		padding-bottom: calc(1.5rem + var(--resize-scroll-buffer, 52rem));
	}

	.tab-dots {
		position: fixed;
		bottom: 1rem;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		gap: 0.5rem;
		z-index: 10;
	}

	.dot {
		width: 0.6rem;
		height: 0.6rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		padding: 0;
		cursor: pointer;
	}

	.dot.active {
		background: var(--color-accent, var(--color-text));
	}

	.top-bar {
		position: fixed;
		top: 1rem;
		right: 1rem;
		display: flex;
		gap: 0.5rem;
		z-index: 10;
	}

	.icon-button {
		position: relative;
		width: 3rem;
		height: 3rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		font-size: 1.3rem;
		cursor: pointer;
	}

	.update-badge {
		position: absolute;
		top: 0.35rem;
		right: 0.35rem;
		width: 0.6rem;
		height: 0.6rem;
		border-radius: 50%;
		background: var(--color-error);
		border: 1px solid var(--color-surface);
	}

	.icon-button:active {
		background: var(--color-surface-hover);
	}

	.icon-button.active {
		background: var(--color-accent, var(--color-text));
		color: var(--color-surface);
	}

	.profile-menu-wrap {
		position: relative;
	}

	.profile-menu {
		position: absolute;
		top: calc(100% + 0.5rem);
		right: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		width: 10rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.75rem;
		z-index: 20;
	}

	.profile-menu-name {
		margin: 0;
		font-weight: 600;
		font-size: 0.9rem;
	}

	.profile-menu-action {
		background: none;
		border: none;
		color: var(--color-accent);
		cursor: pointer;
		font-size: 0.9rem;
		text-align: left;
		padding: 0;
	}

	.cell {
		position: relative;
		touch-action: pan-y;
		/* Grid items default to overflow:visible, which makes their automatic
		   minimum size track their content's min-content size — so an
		   oversized child silently grows the whole grid row past
		   grid-auto-rows. overflow:hidden here zeroes that automatic minimum
		   and lets grid-auto-rows actually cap the row height. */
		min-height: 0;
		overflow: hidden;
	}

	.cell.editing {
		touch-action: none;
	}

	.cell.dragging {
		pointer-events: none;
		opacity: 0.6;
		z-index: 20;
	}

	.cell.drop-target {
		outline: 3px dashed var(--color-accent, var(--color-text));
		outline-offset: 2px;
		border-radius: 1rem;
	}

	.cell.resizing {
		z-index: 20;
	}

	.empty-cell {
		min-width: 0;
		min-height: 0;
	}

	.drop-ghost {
		outline: 3px dashed var(--color-accent, var(--color-text));
		outline-offset: -2px;
		border-radius: 1rem;
		pointer-events: none;
		z-index: 1;
	}

	.resize-handle {
		position: absolute;
		/* Inset (not straddling the edge) since .cell clips overflow now. */
		bottom: 0.25rem;
		right: 0.25rem;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		font-size: 0.9rem;
		line-height: 1;
		cursor: nwse-resize;
		touch-action: none;
		z-index: 5;
	}

	.edit-overlay {
		position: absolute;
		inset: 0;
		cursor: grab;
		border-radius: 1rem;
		outline: 2px dashed var(--color-border);
		outline-offset: -2px;
	}

	.remove-button {
		position: absolute;
		/* Inset (not straddling the edge) since .cell clips overflow now. */
		top: 0.25rem;
		right: 0.25rem;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		font-size: 0.9rem;
		line-height: 1;
		cursor: pointer;
		z-index: 5;
	}

	.add-widget-cell {
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.add-widget-button {
		width: 100%;
		height: 100%;
		border-radius: 1rem;
		border: 2px dashed var(--color-border);
		background: transparent;
		color: var(--color-text-muted);
		font-size: 1rem;
		cursor: pointer;
	}

	.widget-picker {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		padding: 0.75rem;
		overflow-y: auto;
		background: var(--color-surface);
		border-radius: 1rem;
		border: 1px solid var(--color-border);
	}

	.widget-picker-option,
	.widget-picker-cancel {
		border: 1px solid var(--color-border);
		background: var(--color-surface-hover, transparent);
		color: var(--color-text);
		border-radius: 0.5rem;
		padding: 0.5rem;
		cursor: pointer;
		font-size: 0.9rem;
	}

	.widget-picker-cancel {
		color: var(--color-text-muted);
	}

	.assistant-overlay {
		position: fixed;
		bottom: 2rem;
		left: 50%;
		transform: translateX(-50%);
		z-index: 20;
		max-width: 26rem;
		width: calc(100vw - 3rem);
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1rem 1.25rem;
		box-shadow: 0 0.5rem 1.5rem rgba(0, 0, 0, 0.2);
	}

	.assistant-overlay p {
		margin: 0 0 0.5rem;
	}

	.assistant-overlay .query {
		color: var(--color-text-muted);
		font-size: 0.9rem;
	}

	.assistant-overlay .dismiss {
		background: none;
		border: none;
		color: var(--color-accent);
		cursor: pointer;
		padding: 0;
		font-size: 0.9rem;
	}
</style>
