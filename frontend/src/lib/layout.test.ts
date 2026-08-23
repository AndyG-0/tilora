import { describe, expect, it } from 'vitest';
import { computeEmptyCells, isRectFree, packWidgets, reorderNarrow, resolveResizePush, sortForNarrow } from './layout';
import type { WidgetSummaryMeta } from './api';

function widget(id: string, col: number, row: number, colSpan = 1, rowSpan = 1): WidgetSummaryMeta {
	return {
		id,
		type: 'clock',
		name: 'Clock',
		tab: 'main',
		layout: { col, row, colSpan, rowSpan },
		refresh_interval_seconds: 60,
	};
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

describe('resolveResizePush', () => {
	function layoutOf(updates: { id: string; layout: WidgetSummaryMeta['layout'] }[], id: string) {
		return updates.find((u) => u.id === id)?.layout;
	}

	it('is a no-op when growing into empty space', () => {
		const widgets = [widget('a', 1, 1), widget('b', 3, 3)];

		const updates = resolveResizePush(widgets, 'a', { col: 1, row: 1, colSpan: 2, rowSpan: 2 });

		expect(updates).toEqual([{ id: 'a', layout: { col: 1, row: 1, colSpan: 2, rowSpan: 2 } }]);
	});

	it('pushes a single colliding sibling down below the resized tile', () => {
		const widgets = [widget('a', 1, 1), widget('b', 1, 2)];

		const updates = resolveResizePush(widgets, 'a', { col: 1, row: 1, colSpan: 1, rowSpan: 3 });

		expect(layoutOf(updates, 'b')).toEqual({ col: 1, row: 4, colSpan: 1, rowSpan: 1 });
	});

	it('cascades through multiple stacked siblings', () => {
		const widgets = [widget('a', 1, 1), widget('b', 1, 2), widget('c', 1, 3)];

		const updates = resolveResizePush(widgets, 'a', { col: 1, row: 1, colSpan: 1, rowSpan: 3 });

		expect(layoutOf(updates, 'b')?.row).toBe(4);
		expect(layoutOf(updates, 'c')?.row).toBe(5);
	});

	it('does not move a sibling in a different column', () => {
		const widgets = [widget('a', 1, 1), widget('b', 3, 1)];

		const updates = resolveResizePush(widgets, 'a', { col: 1, row: 1, colSpan: 2, rowSpan: 1 });

		expect(updates.map((u) => u.id)).toEqual(['a']);
	});

	it('pushes down (not sideways) for a colSpan-only growth that overlaps a same-row sibling', () => {
		const widgets = [widget('a', 1, 1), widget('b', 2, 1)];

		const updates = resolveResizePush(widgets, 'a', { col: 1, row: 1, colSpan: 3, rowSpan: 1 });

		expect(layoutOf(updates, 'b')).toEqual({ col: 2, row: 2, colSpan: 1, rowSpan: 1 });
	});

	it('never changes a pushed sibling col/colSpan/rowSpan, only row', () => {
		const widgets = [widget('a', 1, 1), widget('b', 1, 2, 2, 2)];

		const updates = resolveResizePush(widgets, 'a', { col: 1, row: 1, colSpan: 1, rowSpan: 2 });

		expect(layoutOf(updates, 'b')).toEqual({ col: 1, row: 3, colSpan: 2, rowSpan: 2 });
	});

	it('has no row ceiling — pushes as far down as needed', () => {
		const widgets = [widget('a', 1, 1), widget('b', 1, 2), widget('c', 1, 20)];

		const updates = resolveResizePush(widgets, 'a', { col: 1, row: 1, colSpan: 1, rowSpan: 8 });

		expect(layoutOf(updates, 'b')?.row).toBe(9);
		// 'c' sits well below both the resized tile and where 'b' lands, so it
		// never collides with anything and isn't touched at all.
		expect(layoutOf(updates, 'c')).toBeUndefined();
	});

	it('leaves pre-existing overlaps unrelated to the resize alone', () => {
		const widgets = [widget('a', 1, 1), widget('b', 3, 1), widget('c', 3, 1)];

		const updates = resolveResizePush(widgets, 'a', { col: 1, row: 1, colSpan: 1, rowSpan: 1 });

		expect(updates).toEqual([{ id: 'a', layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 } }]);
	});
});

describe('packWidgets', () => {
	function layoutOf(updates: { id: string; layout: WidgetSummaryMeta['layout'] }[], id: string) {
		return updates.find((u) => u.id === id)!.layout;
	}

	it('closes a gap between two widgets', () => {
		const widgets = [widget('a', 1, 1), widget('b', 3, 1)];

		const updates = packWidgets(widgets, 4);

		expect(layoutOf(updates, 'a')).toEqual({ col: 1, row: 1, colSpan: 1, rowSpan: 1 });
		expect(layoutOf(updates, 'b')).toEqual({ col: 2, row: 1, colSpan: 1, rowSpan: 1 });
	});

	it('resolves an overlap into two adjacent non-overlapping cells', () => {
		const widgets = [widget('a', 1, 1), widget('b', 1, 1)];

		const updates = packWidgets(widgets, 4);

		expect(layoutOf(updates, 'a')).toEqual({ col: 1, row: 1, colSpan: 1, rowSpan: 1 });
		expect(layoutOf(updates, 'b')).toEqual({ col: 2, row: 1, colSpan: 1, rowSpan: 1 });
	});

	it('preserves colSpan/rowSpan, only repositioning col/row', () => {
		const widgets = [widget('a', 1, 1), widget('b', 3, 1, 2, 2)];

		const updates = packWidgets(widgets, 4);

		expect(layoutOf(updates, 'b')).toEqual({ col: 2, row: 1, colSpan: 2, rowSpan: 2 });
	});

	it('skips a row where only a narrower gap remains for a multi-column widget', () => {
		// Row 1 has one free column (col 4) after 'a'; 'b' is 2 wide so it can't
		// fit there and must drop to row 2.
		const widgets = [widget('a', 1, 1, 3, 1), widget('b', 1, 2, 2, 1)];

		const updates = packWidgets(widgets, 4);

		expect(layoutOf(updates, 'a')).toEqual({ col: 1, row: 1, colSpan: 3, rowSpan: 1 });
		expect(layoutOf(updates, 'b')).toEqual({ col: 1, row: 2, colSpan: 2, rowSpan: 1 });
	});

	it('roughly preserves original reading order for tied rows', () => {
		const widgets = [widget('b', 2, 1), widget('a', 1, 1)];

		const updates = packWidgets(widgets, 4);

		expect(layoutOf(updates, 'a').col).toBeLessThan(layoutOf(updates, 'b').col);
	});

	it('is a no-op when the tab is already fully packed', () => {
		const widgets = [widget('a', 1, 1, 2, 1), widget('b', 3, 1, 2, 1), widget('c', 1, 2)];

		const updates = packWidgets(widgets, 4);

		expect(layoutOf(updates, 'a')).toEqual({ col: 1, row: 1, colSpan: 2, rowSpan: 1 });
		expect(layoutOf(updates, 'b')).toEqual({ col: 3, row: 1, colSpan: 2, rowSpan: 1 });
		expect(layoutOf(updates, 'c')).toEqual({ col: 1, row: 2, colSpan: 1, rowSpan: 1 });
	});
});
