import { describe, expect, it } from 'vitest';
import { computeEmptyCells, isRectFree } from './layout';
import type { WidgetSummaryMeta } from './api';

function widget(id: string, col: number, row: number, colSpan = 1, rowSpan = 1): WidgetSummaryMeta {
	return { id, type: 'clock', tab: 'main', layout: { col, row, colSpan, rowSpan } };
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
