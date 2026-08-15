import { describe, expect, it } from 'vitest';
import { computeEmptyCells, isRectFree, reorderNarrow, sortForNarrow } from './layout';
import type { WidgetSummaryMeta } from './api';

function widget(id: string, col: number, row: number, colSpan = 1, rowSpan = 1): WidgetSummaryMeta {
	return { id, type: 'clock', name: 'Clock', tab: 'main', layout: { col, row, colSpan, rowSpan } };
}

describe('computeEmptyCells', () => {
	it('lists every unoccupied cell up to one row past the tallest widget', () => {
		const widgets = [widget('a', 1, 1), widget('b', 2, 1)];

		const cells = computeEmptyCells(widgets, null, 4);

		expect(cells).toEqual([
			{ col: 3, row: 1 },
			{ col: 4, row: 1 },
			{ col: 1, row: 2 },
			{ col: 2, row: 2 },
			{ col: 3, row: 2 },
			{ col: 4, row: 2 },
		]);
	});

	it('excludes cells covered by multi-span widgets', () => {
		const widgets = [widget('a', 1, 1, 2, 2)];

		const cells = computeEmptyCells(widgets, null, 4);

		expect(cells).toEqual([
			{ col: 3, row: 1 },
			{ col: 4, row: 1 },
			{ col: 3, row: 2 },
			{ col: 4, row: 2 },
			{ col: 1, row: 3 },
			{ col: 2, row: 3 },
			{ col: 3, row: 3 },
			{ col: 4, row: 3 },
		]);
	});

	it('treats the excluded widget id as available (its own footprint)', () => {
		const widgets = [widget('a', 1, 1), widget('b', 2, 1)];

		const cells = computeEmptyCells(widgets, 'b', 4);

		expect(cells).toContainEqual({ col: 2, row: 1 });
	});
});

describe('isRectFree', () => {
	const widgets = [widget('a', 1, 1, 2, 1), widget('b', 1, 2)];

	it('is true for a rect that overlaps nothing', () => {
		expect(isRectFree(widgets, 'a', { col: 3, row: 1, colSpan: 1, rowSpan: 1 }, 4)).toBe(true);
	});

	it('is false when the rect overlaps another widget', () => {
		expect(isRectFree(widgets, 'excluded-none', { col: 2, row: 1, colSpan: 1, rowSpan: 1 }, 4)).toBe(false);
	});

	it('ignores the excluded widget when checking overlap', () => {
		expect(isRectFree(widgets, 'a', { col: 1, row: 1, colSpan: 2, rowSpan: 1 }, 4)).toBe(true);
	});

	it('is false when the rect runs past the right edge', () => {
		expect(isRectFree(widgets, 'a', { col: 4, row: 1, colSpan: 2, rowSpan: 1 }, 4)).toBe(false);
	});

	it('is false for col/row below 1', () => {
		expect(isRectFree(widgets, 'a', { col: 0, row: 1, colSpan: 1, rowSpan: 1 }, 4)).toBe(false);
		expect(isRectFree(widgets, 'a', { col: 1, row: 0, colSpan: 1, rowSpan: 1 }, 4)).toBe(false);
	});
});

describe('sortForNarrow', () => {
	it('orders by row', () => {
		const widgets = [widget('a', 1, 3), widget('b', 1, 1), widget('c', 1, 2)];
		expect(sortForNarrow(widgets).map((w) => w.id)).toEqual(['b', 'c', 'a']);
	});

	it('keeps existing relative order for tied rows', () => {
		const widgets = [widget('a', 1, 1), widget('b', 2, 1), widget('c', 1, 2)];
		expect(sortForNarrow(widgets).map((w) => w.id)).toEqual(['a', 'b', 'c']);
	});
});

describe('reorderNarrow', () => {
	it("moves the source widget to the target widget's position", () => {
		const widgets = [widget('a', 1, 1), widget('b', 1, 2), widget('c', 1, 3)];

		const updates = reorderNarrow(widgets, 'a', 'c');

		expect(updates.map((u) => u.id)).toEqual(['b', 'c', 'a']);
		expect(updates.map((u) => u.layout.row)).toEqual([1, 2, 3]);
	});

	it('moves a later widget earlier, shifting the ones in between down', () => {
		const widgets = [widget('a', 1, 1), widget('b', 1, 2), widget('c', 1, 3)];

		const updates = reorderNarrow(widgets, 'c', 'a');

		expect(updates.map((u) => u.id)).toEqual(['c', 'a', 'b']);
	});

	it('preserves colSpan/rowSpan, only changing row', () => {
		const widgets = [widget('a', 1, 1, 2, 3), widget('b', 1, 2)];

		const updates = reorderNarrow(widgets, 'a', 'b');

		const a = updates.find((u) => u.id === 'a')!;
		expect(a.layout).toEqual({ col: 1, row: 2, colSpan: 2, rowSpan: 3 });
	});

	it('returns empty for an unknown id or a no-op move', () => {
		const widgets = [widget('a', 1, 1), widget('b', 1, 2)];
		expect(reorderNarrow(widgets, 'a', 'missing')).toEqual([]);
		expect(reorderNarrow(widgets, 'a', 'a')).toEqual([]);
	});
});
