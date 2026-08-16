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
