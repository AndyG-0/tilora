import { describe, expect, it } from 'vitest';
import { computeResizedLayout } from './resize';

const layout = { col: 1, row: 1, colSpan: 1, rowSpan: 1 };
const cellWidth = 100;
const cellHeight = 100;

describe('computeResizedLayout', () => {
	it('grows colSpan and rowSpan by one cell per full cell dragged', () => {
		const result = computeResizedLayout(layout, 150, 220, cellWidth, cellHeight, 4);

		expect(result).toEqual({ col: 1, row: 1, colSpan: 3, rowSpan: 3 });
	});

	it('rounds partial drags to the nearest cell', () => {
		const result = computeResizedLayout(layout, 40, -40, cellWidth, cellHeight, 4);

		expect(result).toEqual({ col: 1, row: 1, colSpan: 1, rowSpan: 1 });
	});

	it('never shrinks below a 1x1 span', () => {
		const result = computeResizedLayout(layout, -500, -500, cellWidth, cellHeight, 4);

		expect(result).toEqual({ col: 1, row: 1, colSpan: 1, rowSpan: 1 });
	});

	it('clamps colSpan so the tile cannot grow past the grid edge', () => {
		const wideStart = { col: 3, row: 1, colSpan: 1, rowSpan: 1 };

		const result = computeResizedLayout(wideStart, 1000, 0, cellWidth, cellHeight, 4);

		expect(result.colSpan).toBe(2);
	});

	it('caps rowSpan at a sane maximum', () => {
		const result = computeResizedLayout(layout, 0, 1000, cellWidth, cellHeight, 4);

		expect(result.rowSpan).toBe(4);
	});

	it('leaves col/row untouched, only span changes', () => {
		const start = { col: 2, row: 3, colSpan: 1, rowSpan: 1 };

		const result = computeResizedLayout(start, 100, 100, cellWidth, cellHeight, 4);

		expect(result.col).toBe(2);
		expect(result.row).toBe(3);
	});
});
