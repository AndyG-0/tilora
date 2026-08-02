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
