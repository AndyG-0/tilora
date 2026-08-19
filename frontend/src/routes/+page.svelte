<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { widgets, applyLayoutUpdates, addWidgetLocal, removeWidgetLocal } from '$lib/stores/widgets';
	import { tabs } from '$lib/stores/tabs';
	import { activeTabIndex } from '$lib/stores/activeTab';
	import { theme, persistTheme } from '$lib/stores/theme';
	import { user, logout } from '$lib/stores/user';
	import { api, type WidgetLayout, type WidgetSummaryMeta } from '$lib/api';
	import { groupWidgetsByTab, resolveSwipe } from '$lib/tabNavigation';
	import { computeResizedLayout, MAX_ROW_SPAN } from '$lib/resize';
	import { computeEmptyCells, isRectFree, reorderNarrow, sortForNarrow } from '$lib/layout';
	import { breakpoint } from '$lib/stores/breakpoint';
	import {
		ensureMicrophonePermission,
		isSpeechRecognitionSupported,
		listenOnce,
		playChime,
		SpeechError,
		speak,
		startContinuousListening,
		stopSpeaking,
		type ContinuousListenHandle,
	} from '$lib/speech';
	import { voiceSelection } from '$lib/stores/voice';
	import { agentName, alwaysOnMic, sttAvailable } from '$lib/stores/assistant';
	import { TILE_COMPONENTS } from '$lib/widgetComponents';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	// Matches the `.grid`'s `grid-template-columns: repeat(4, 1fr)` below —
	// caps how wide a tile can grow when resizing.
	const GRID_COLUMNS = 4;

	// At the narrow breakpoint `.cell` is forced to `grid-row: auto` (see the
	// media query below) since a tile's `row` number was chosen for the wide
	// 2D grid and doesn't mean anything in a single-column stack — but that
	// override also discards `rowSpan`, a stylesheet `!important` always
	// beating a plain inline style, so a resize that grows rowSpan had no
	// visible effect at all on a phone. This computes an explicit min-height
	// instead so growth stays visible; `13` (= the `.grid`'s 12rem row height
	// + 1rem gap) matches the `--resize-scroll-buffer` constant below.
	function narrowRowHeight(rowSpan: number): string {
		return rowSpan > 1 ? `min-height: calc(${rowSpan} * 13rem - 1rem);` : '';
	}

	// Fallback matches the backend's default set; refreshed from /api/theme
	// on mount so new themes show up without a frontend redeploy.
	let themeIds = $state(['light', 'dark', 'sepia', 'contrast', 'forest', 'ocean']);
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

	// At the narrow breakpoint a tile's stacking position is its position in
	// this array (see the `.cell` media-query override below), so it's sorted
	// into narrow order here — the one place every consumer of `grouped`
	// (the template, and the empty-cell/reorder math above) reads from.
	const grouped = $derived(
		groupWidgetsByTab($widgets, $tabs).map((tab) => ({
			...tab,
			widgets: $breakpoint === 'narrow' ? sortForNarrow(tab.widgets) : tab.widgets,
		})),
	);
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
	// Captured at gesture-start rather than read live at pointer-up, so a
	// breakpoint change mid-drag (e.g. a tablet rotated) doesn't write the
	// gesture's result into the wrong breakpoint's saved layout.
	let dragBreakpoint = $state(get(breakpoint));

	function toggleEditMode() {
		editMode = !editMode;
	}

	function onCellPointerDown(event: PointerEvent, widgetId: string) {
		if (!editMode) return;
		event.preventDefault();
		(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
		dragWidgetId = widgetId;
		dragStart = { x: event.clientX, y: event.clientY };
		dragBreakpoint = get(breakpoint);
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

		// Empty-cell drop targets only make sense in the wide 2D grid — at the
		// narrow breakpoint every `.cell` is force-stacked full-width in DOM
		// order (see the `.cell` media-query override below), so the empty-cell
		// markers below (positioned via GRID_COLUMNS, the *wide* column count)
		// would sit at explicit grid coordinates that don't correspond to
		// anything visible, and — worse — those explicit placements are reserved
		// by CSS Grid's auto-placement algorithm ahead of the auto-flowed
		// `.cell` elements, shoving real tiles out of the positions this same
		// function's own `elementFromPoint` hit-test expects them to be in.
		if (dragBreakpoint === 'narrow') {
			dropEmptyCell = null;
			return;
		}

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

		if (targetId && dragBreakpoint === 'narrow') {
			const siblings = sortForNarrow($widgets.filter((w) => w.tab === source.tab));
			const updates = reorderNarrow(siblings, source.id, targetId);
			if (updates.length === 0) return;
			await api.updateWidgetsLayout(updates, dragBreakpoint);
			applyLayoutUpdates(updates);
		} else if (targetId) {
			const target = $widgets.find((w) => w.id === targetId);
			if (!target) return;
			const updates = [
				{ id: source.id, layout: target.layout },
				{ id: target.id, layout: source.layout },
			];
			await api.updateWidgetsLayout(updates, dragBreakpoint);
			applyLayoutUpdates(updates);
		} else if (emptyCell) {
			const updates = [{ id: source.id, layout: { ...source.layout, col: emptyCell.col, row: emptyCell.row } }];
			await api.updateWidgetsLayout(updates, dragBreakpoint);
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
	// Same gesture-start capture as dragBreakpoint above.
	let resizeBreakpoint = get(breakpoint);

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
		resizeBreakpoint = get(breakpoint);
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
		await api.updateWidgetsLayout(updates, resizeBreakpoint);
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
		| { status: 'listening'; mode?: 'native' | 'cloud_stt' }
		| { status: 'transcribing' }
		| { status: 'thinking'; query: string }
		| { status: 'answered'; query: string; answer: string }
		| { status: 'error'; message: string };

	let assistantState = $state<AssistantState>({ status: 'idle' });
	const micSupported = $derived(isSpeechRecognitionSupported($sttAvailable));
	let continuousListener: ContinuousListenHandle | null = null;
	const alwaysOnActive = $derived(micSupported && $alwaysOnMic);
	// Set right before navigating to a widget the assistant itself launched,
	// so onDestroy below knows not to cut off the answer that's still
	// speaking — the unmount is this page's own doing, not the user leaving.
	let navigatingFromAssistant = false;

	async function processAssistantQuery(query: string) {
		assistantState = { status: 'thinking', query };
		try {
			const { text, action } = await api.askAssistant(query);
			assistantState = { status: 'answered', query, answer: text };
			speak(text, $voiceSelection);
			if (action) {
				const params = new URLSearchParams();
				if (action.panel) params.set('panel', action.panel);
				if (action.destination) params.set('destination', action.destination);
				if (action.origin) params.set('origin', action.origin);
				const qs = params.toString();
				navigatingFromAssistant = true;
				goto(`/widget/${action.widget_id}${qs ? `?${qs}` : ''}`);
			}
		} catch (err) {
			const message = err instanceof Error && err.message ? err.message : get(_)('dashboard.assistant_error');
			assistantState = { status: 'error', message };
		} finally {
			if (alwaysOnActive) {
				continuousListener?.resume();
			}
		}
	}

	async function startListening() {
		continuousListener?.pause();
		assistantState = { status: 'listening', mode: 'native' };
		let query: string;
		try {
			query = await listenOnce({
				sttAvailable: $sttAvailable,
				onListeningMode: (mode) => {
					assistantState = { status: 'listening', mode };
				},
				onTranscribing: () => {
					assistantState = { status: 'transcribing' };
				},
			});
		} catch (err: unknown) {
			let message = get(_)('dashboard.mic_no_match');
			if (err instanceof SpeechError) {
				if (err.code === 'not-allowed') {
					message = get(_)('dashboard.mic_permission_denied');
				} else if (err.code === 'audio-capture') {
					message = get(_)('dashboard.mic_not_found');
				} else if (err.code === 'service-unavailable') {
					message = get(_)('dashboard.mic_service_unavailable');
				} else if (err.code === 'no-speech') {
					message = get(_)('dashboard.mic_no_match');
				}
			}
			assistantState = { status: 'error', message };
			if (alwaysOnActive) {
				continuousListener?.resume();
			}
			return;
		}

		await processAssistantQuery(query);
	}

	async function handleWakeWordDetected(commandQuery: string) {
		playChime();
		if (commandQuery) {
			await processAssistantQuery(commandQuery);
		} else {
			await startListening();
		}
	}

	function dismissAssistant() {
		stopSpeaking();
		assistantState = { status: 'idle' };
		if (alwaysOnActive) {
			continuousListener?.resume();
		}
	}

	$effect(() => {
		if (alwaysOnActive) {
			void ensureMicrophonePermission();
			if (!continuousListener) {
				continuousListener = startContinuousListening({
					getAgentName: () => get(agentName),
					onWakeWordDetected: (query) => {
						handleWakeWordDetected(query);
					},
				});
			}
		} else {
			if (continuousListener) {
				continuousListener.stop();
				continuousListener = null;
			}
		}
	});

	onDestroy(() => {
		if (continuousListener) {
			continuousListener.stop();
			continuousListener = null;
		}
		if (!navigatingFromAssistant) {
			stopSpeaking();
		}
	});

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
			class:active={assistantState.status === 'listening' || assistantState.status === 'transcribing'}
			class:standby={alwaysOnActive && assistantState.status === 'idle'}
			onclick={startListening}
			disabled={assistantState.status === 'listening' ||
				assistantState.status === 'transcribing' ||
				assistantState.status === 'thinking'}
			aria-label={alwaysOnActive && assistantState.status === 'idle'
				? $_('dashboard.always_on_standby_label', { values: { agentName: $agentName } })
				: $_('dashboard.ask_question')}
		>
			<svg
				viewBox="0 0 24 24"
				width="20"
				height="20"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
				<path d="M19 10v2a7 7 0 0 1-14 0v-2" />
				<line x1="12" y1="19" x2="12" y2="22" />
			</svg>
			{#if alwaysOnActive && assistantState.status === 'idle'}
				<span class="standby-badge" aria-hidden="true"></span>
			{/if}
		</button>
	{/if}
	<button class="icon-button" onclick={() => goto('/settings')} aria-label={$_('settings.page.title')}>
		<svg
			viewBox="0 0 24 24"
			width="20"
			height="20"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
			aria-hidden="true"
		>
			<circle cx="12" cy="12" r="3" />
			<path
				d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1Z"
			/>
		</svg>
		{#if updateAvailable}
			<span class="update-badge" aria-label={$_('dashboard.update_available')}></span>
		{/if}
	</button>
	<button class="icon-button" onclick={() => goto('/reports')} aria-label={$_('reports.title')}>
		<svg
			viewBox="0 0 24 24"
			width="20"
			height="20"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
			aria-hidden="true"
		>
			<line x1="18" y1="20" x2="18" y2="10" />
			<line x1="12" y1="20" x2="12" y2="4" />
			<line x1="6" y1="20" x2="6" y2="14" />
		</svg>
	</button>
	<button class="icon-button" onclick={cycleTheme} aria-label={$_('dashboard.change_theme')}>
		{#if $theme === 'dark'}
			<svg
				viewBox="0 0 24 24"
				width="20"
				height="20"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<circle cx="12" cy="12" r="4" />
				<line x1="12" y1="2" x2="12" y2="4" />
				<line x1="12" y1="20" x2="12" y2="22" />
				<line x1="4.93" y1="4.93" x2="6.34" y2="6.34" />
				<line x1="17.66" y1="17.66" x2="19.07" y2="19.07" />
				<line x1="2" y1="12" x2="4" y2="12" />
				<line x1="20" y1="12" x2="22" y2="12" />
				<line x1="4.93" y1="19.07" x2="6.34" y2="17.66" />
				<line x1="17.66" y1="6.34" x2="19.07" y2="4.93" />
			</svg>
		{:else if $theme === 'light'}
			<svg
				viewBox="0 0 24 24"
				width="20"
				height="20"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
			</svg>
		{:else if $theme === 'contrast'}
			<svg
				viewBox="0 0 24 24"
				width="20"
				height="20"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<circle cx="12" cy="12" r="9" />
				<path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" />
			</svg>
		{:else if $theme === 'sepia'}
			<svg
				viewBox="0 0 24 24"
				width="20"
				height="20"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<circle cx="12" cy="12" r="9" />
				<path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor" />
			</svg>
		{:else if $theme === 'forest'}
			<svg
				viewBox="0 0 24 24"
				width="20"
				height="20"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
				<path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
			</svg>
		{:else if $theme === 'ocean'}
			<svg
				viewBox="0 0 24 24"
				width="20"
				height="20"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5c2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1" />
				<path d="M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1" />
				<path d="M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1" />
			</svg>
		{:else}
			<svg
				viewBox="0 0 24 24"
				width="20"
				height="20"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<circle cx="13.5" cy="6.5" r=".5" fill="currentColor" />
				<circle cx="17.5" cy="10.5" r=".5" fill="currentColor" />
				<circle cx="8.5" cy="7.5" r=".5" fill="currentColor" />
				<circle cx="6.5" cy="12.5" r=".5" fill="currentColor" />
				<path
					d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"
				/>
			</svg>
		{/if}
	</button>
	<button
		class="icon-button"
		class:active={editMode}
		onclick={toggleEditMode}
		aria-label={editMode ? $_('dashboard.done_rearranging') : $_('dashboard.rearrange_widgets')}
	>
		{#if editMode}
			<svg
				viewBox="0 0 24 24"
				width="20"
				height="20"
				fill="none"
				stroke="currentColor"
				stroke-width="2.5"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<polyline points="20 6 9 17 4 12" />
			</svg>
		{:else}
			<svg
				viewBox="0 0 24 24"
				width="18"
				height="18"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
			</svg>
		{/if}
	</button>
	{#if $user}
		<div class="profile-menu-wrap">
			<button
				class="icon-button"
				class:active={profileMenuOpen}
				onclick={toggleProfileMenu}
				aria-label={$_('settings.profile.heading')}
			>
				{$user.avatar || $user.name.charAt(0).toUpperCase()}
			</button>
			{#if profileMenuOpen}
				<div class="profile-menu">
					<p class="profile-menu-name">{$user.name}</p>
					<button class="profile-menu-action" onclick={switchProfile}>{$_('dashboard.switch_profile')}</button>
					<button class="profile-menu-action profile-menu-logout" onclick={switchProfile}
						>{$_('dashboard.log_out')}</button
					>
				</div>
			{/if}
		</div>
	{/if}
</div>

{#if assistantState.status !== 'idle'}
	<div class="assistant-overlay" role="status">
		{#if assistantState.status === 'listening'}
			<p>{assistantState.mode === 'cloud_stt' ? $_('dashboard.listening_cloud_stt') : $_('dashboard.listening')}</p>
		{:else if assistantState.status === 'transcribing'}
			<p>{$_('dashboard.transcribing')}</p>
		{:else if assistantState.status === 'thinking'}
			<p class="query">{assistantState.query}</p>
			<p>{$_('dashboard.thinking')}</p>
		{:else if assistantState.status === 'answered'}
			<p class="query">{assistantState.query}</p>
			<p>{assistantState.answer}</p>
			<button class="dismiss" onclick={dismissAssistant}>{$_('common.dismiss')}</button>
		{:else if assistantState.status === 'error'}
			<p>{assistantState.message}</p>
			<button class="dismiss" onclick={dismissAssistant}>{$_('common.dismiss')}</button>
		{/if}
	</div>
{/if}

<div class="tabs-viewport" role="presentation" ontouchstart={onTouchStart} ontouchend={onTouchEnd}>
	<div class="tabs-track" style="transform: translateX(-{clampedIndex * 100}%)">
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
							style="grid-column: {layout.col} / span {layout.colSpan}; grid-row: {layout.row} / span {layout.rowSpan}; {$breakpoint ===
							'narrow'
								? narrowRowHeight(layout.rowSpan)
								: ''} {dragWidgetId === widget.id ? `transform: translate(${dragDelta.x}px, ${dragDelta.y}px);` : ''}"
							onpointerdown={(e) => onCellPointerDown(e, widget.id)}
							onpointerup={onCellPointerUp}
							onpointercancel={onCellPointerUp}
						>
							{#if Tile}
								<Tile widgetId={widget.id} refreshIntervalSeconds={widget.refresh_interval_seconds} />
							{/if}
							{#if editMode}
								<div class="edit-overlay" aria-hidden="true"></div>
								<button
									class="remove-button"
									onpointerdown={(e) => e.stopPropagation()}
									onclick={(e) => handleRemoveWidget(e, widget.id)}
									aria-label={$_('dashboard.remove_widget')}
								>
									✕
								</button>
								<button
									class="resize-handle"
									onpointerdown={(e) => onResizePointerDown(e, widget)}
									onpointerup={onResizePointerUp}
									onpointercancel={onResizePointerUp}
									aria-label={$_('dashboard.resize_widget')}
								>
									⤡
								</button>
							{/if}
						</div>
					{/each}
					{#if dragWidgetId && tabIndex === clampedIndex && dragBreakpoint === 'wide'}
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
							<button class="add-widget-button" onclick={openAddWidget}>{$_('dashboard.add_widget')}</button>
							{#if addingWidget}
								<div class="widget-picker">
									{#each widgetTypeOptions as option (option.type)}
										<button class="widget-picker-option" onclick={() => selectWidgetType(option, tab.id)}>
											{option.name}
										</button>
									{/each}
									<button class="widget-picker-cancel" onclick={closeAddWidget}>{$_('common.cancel')}</button>
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
		flex: 0 0 100%;
		min-width: 0;
		height: 100%;
		overflow-y: auto;
		overflow-x: hidden;
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
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 3rem;
		height: 3rem;
		border-radius: 50%;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
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

	.standby-badge {
		position: absolute;
		bottom: 0.35rem;
		right: 0.35rem;
		width: 0.55rem;
		height: 0.55rem;
		border-radius: 50%;
		background: var(--color-accent, #10b981);
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

	.profile-menu-logout {
		padding-top: 0.5rem;
		border-top: 1px solid var(--color-border);
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
