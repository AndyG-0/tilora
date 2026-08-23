import type { WidgetLayout, WidgetSummaryMeta } from '$lib/api';

// Returns every unoccupied single-cell {col, row} coordinate for a tab's
// widgets, from row 1 through one row past the current bottom (so there's
// always somewhere to drop a tile to start a new row). `excludeId` lets the
// widget currently being dragged count its own footprint as available.
export function computeEmptyCells(
	widgets: WidgetSummaryMeta[],
	excludeId: string | null,
	columns: number,
): { col: number; row: number }[] {
	const relevant = widgets.filter((w) => w.id !== excludeId);
	const maxRow = Math.max(1, ...relevant.map((w) => w.layout.row + w.layout.rowSpan - 1));

	const occupied = new Set<string>();
	for (const w of relevant) {
		for (let r = w.layout.row; r < w.layout.row + w.layout.rowSpan; r++) {
			for (let c = w.layout.col; c < w.layout.col + w.layout.colSpan; c++) {
				occupied.add(`${c},${r}`);
			}
		}
	}

	const cells: { col: number; row: number }[] = [];
	for (let row = 1; row <= maxRow + 1; row++) {
		for (let col = 1; col <= columns; col++) {
			if (!occupied.has(`${col},${row}`)) cells.push({ col, row });
		}
	}
	return cells;
}

// Whether `target` fits on the grid without running past the right edge and
// without overlapping any other widget's layout rectangle.
export function isRectFree(
	widgets: WidgetSummaryMeta[],
	excludeId: string,
	target: WidgetLayout,
	columns: number,
): boolean {
	if (target.col < 1 || target.row < 1 || target.col + target.colSpan - 1 > columns) {
		return false;
	}

	for (const w of widgets) {
		if (w.id === excludeId) continue;
		const overlapsCol = target.col < w.layout.col + w.layout.colSpan && w.layout.col < target.col + target.colSpan;
		const overlapsRow = target.row < w.layout.row + w.layout.rowSpan && w.layout.row < target.row + target.rowSpan;
		if (overlapsCol && overlapsRow) return false;
	}

	return true;
}

// Called live during a resize gesture (every pointermove/auto-scroll tick)
// and once more at pointer-up to compute the persisted result. `widgets`
// must already be filtered to the resizing tile's tab (same convention as
// isRectFree's/packWidgets' callers). `newLayout` is the resizing tile's
// candidate layout from computeResizedLayout and is treated as fixed —
// growth always starts from a fixed top-left anchor (the resize handle is
// bottom-right only), so the resizing tile itself is never pushed. Every
// other widget that column-overlaps and row-overlaps any currently-placed
// rect (the resizing tile or an already-pushed sibling) is pushed straight
// down to sit just below whichever collider is lowest — col/colSpan/rowSpan
// are never touched on a pushed sibling, only row (no `columns` edge check
// is needed here, unlike isRectFree: the resizing tile's own colSpan is
// already clamped to the grid width by computeResizedLayout, and pushed
// siblings never change column). This does not compact anything back up
// (see packWidgets/"Auto Arrange" for that): a sibling that never collides
// doesn't move, and a sibling pushed down here stays put even after a
// later shrink.
export function resolveResizePush(
	widgets: WidgetSummaryMeta[],
	resizingId: string,
	newLayout: WidgetLayout,
): { id: string; layout: WidgetLayout }[] {
	if (!widgets.some((w) => w.id === resizingId)) return [];

	const current = new Map<string, WidgetLayout>(widgets.map((w) => [w.id, w.layout]));
	current.set(resizingId, newLayout);

	// A widget only moves if it collides with the resizing tile or with a
	// sibling that has itself already been pushed by this cascade — a
	// pre-existing overlap between two untouched siblings the resize never
	// reaches is left alone (that's packWidgets/"Auto Arrange" territory).
	const moved = new Set<string>([resizingId]);

	// Settle siblings top-to-bottom (by original row, then col) so each one
	// is resolved against everything already placed/settled before it and
	// never has to move again once processed.
	const ordered = widgets
		.filter((w) => w.id !== resizingId)
		.sort((a, b) => a.layout.row - b.layout.row || a.layout.col - b.layout.col);

	for (const widget of ordered) {
		const rect = current.get(widget.id)!;
		let row = rect.row;

		// Drop the widget down past every already-moved rect it lands on,
		// re-checking after each bump since clearing one collider can land
		// it on another (e.g. the sibling that was just pushed below it).
		let bumped = true;
		while (bumped) {
			bumped = false;
			for (const otherId of moved) {
				const other = current.get(otherId)!;
				const colOverlap = rect.col < other.col + other.colSpan && other.col < rect.col + rect.colSpan;
				const rowOverlap = row < other.row + other.rowSpan && other.row < row + rect.rowSpan;
				if (colOverlap && rowOverlap) {
					const below = other.row + other.rowSpan;
					if (below > row) {
						row = below;
						bumped = true;
					}
				}
			}
		}

		if (row !== rect.row) {
			current.set(widget.id, { ...rect, row });
			moved.add(widget.id);
		}
	}

	const updates: { id: string; layout: WidgetLayout }[] = [];
	for (const w of widgets) {
		const final = current.get(w.id)!;
		if (w.id === resizingId || final.row !== w.layout.row) {
			updates.push({ id: w.id, layout: final });
		}
	}
	return updates;
}

// Repositions every widget's existing colSpan/rowSpan into the first free
// slot scanning row-major top-left to bottom-right, eliminating gaps and
// overlaps without resizing anything. Widgets are visited in (row, then col)
// order so the result reads in roughly the same order as before. Reuses
// `isRectFree` against the widgets already placed so far as the running
// occupancy check, mirroring the same collision logic drag/resize already use.
export function packWidgets(widgets: WidgetSummaryMeta[], columns: number): { id: string; layout: WidgetLayout }[] {
	const ordered = [...widgets].sort((a, b) => a.layout.row - b.layout.row || a.layout.col - b.layout.col);
	const placed: WidgetSummaryMeta[] = [];
	const updates: { id: string; layout: WidgetLayout }[] = [];

	for (const widget of ordered) {
		// Clamp defensively: a span wider than the grid would otherwise leave
		// no valid starting column and spin the row scan forever.
		const colSpan = Math.min(widget.layout.colSpan, columns);
		const rowSpan = widget.layout.rowSpan;
		const maxCol = columns - colSpan + 1;

		let layout: WidgetLayout | null = null;
		for (let row = 1; !layout; row++) {
			for (let col = 1; col <= maxCol; col++) {
				const candidate: WidgetLayout = { col, row, colSpan, rowSpan };
				if (isRectFree(placed, widget.id, candidate, columns)) {
					layout = candidate;
					break;
				}
			}
		}

		placed.push({ ...widget, layout });
		updates.push({ id: widget.id, layout });
	}

	return updates;
}

// At the narrow breakpoint, `.cell` is forced to `grid-row: auto` (see
// +page.svelte's media query) — a tile's visual stacking position there is
// its position in this array, not its `row`. This sorts a tab's widgets
// into that stacking order using `row` as a plain sequence number rather
// than a 2D grid coordinate, falling back to the array's existing relative
// order when rows tie (e.g. two widgets that still share a wide-grid row
// because neither has ever been reordered on a phone yet).
export function sortForNarrow(widgets: WidgetSummaryMeta[]): WidgetSummaryMeta[] {
	return [...widgets].sort((a, b) => a.layout.row - b.layout.row);
}

// The narrow-breakpoint equivalent of the wide grid's "swap two widgets'
// layouts" drop: moves `sourceId` to sit where `targetId` currently is in
// `orderedWidgets` (already in narrow stacking order, e.g. via
// `sortForNarrow`) and returns fresh sequential `row` values — a list
// reorder instead of a 2D swap, since col/row don't correspond to anything
// visible at this breakpoint. Returns every widget's new layout, not just
// the two that moved, since a single insert can shift everyone between the
// old and new position.
export function reorderNarrow(
	orderedWidgets: WidgetSummaryMeta[],
	sourceId: string,
	targetId: string,
): { id: string; layout: WidgetLayout }[] {
	const ids = orderedWidgets.map((w) => w.id);
	const from = ids.indexOf(sourceId);
	const to = ids.indexOf(targetId);
	if (from === -1 || to === -1 || from === to) return [];

	const reordered = [...ids];
	reordered.splice(from, 1);
	reordered.splice(to, 0, sourceId);

	const byId = new Map(orderedWidgets.map((w) => [w.id, w]));
	return reordered.map((id, index) => ({
		id,
		layout: { ...byId.get(id)!.layout, row: index + 1 },
	}));
}
