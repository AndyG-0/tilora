import type { WidgetLayout } from '$lib/api';

export const MAX_ROW_SPAN = 4;

// Converts a pointer drag delta (in pixels) into a resized colSpan/rowSpan,
// clamping so a tile can't grow past the grid's right edge or shrink below
// a 1x1 cell. `cellWidth`/`cellHeight` should include the grid gap (i.e. the
// distance from one cell's start to the next), so a drag of exactly one
// cell's width toggles exactly one column of span.
export function computeResizedLayout(
	startLayout: WidgetLayout,
	deltaX: number,
	deltaY: number,
	cellWidth: number,
	cellHeight: number,
	maxCol: number,
): WidgetLayout {
	const colDelta = Math.round(deltaX / cellWidth);
	const rowDelta = Math.round(deltaY / cellHeight);

	const maxColSpan = Math.max(1, maxCol - startLayout.col + 1);
	const colSpan = Math.min(maxColSpan, Math.max(1, startLayout.colSpan + colDelta));
	const rowSpan = Math.min(MAX_ROW_SPAN, Math.max(1, startLayout.rowSpan + rowDelta));

	return { ...startLayout, colSpan, rowSpan };
}
