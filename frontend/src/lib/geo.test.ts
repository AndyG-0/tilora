import { describe, it, expect } from 'vitest';
import { greatCirclePoints } from './geo';

describe('greatCirclePoints', () => {
	it('starts and ends at the input coordinates', () => {
		// DFW -> ORD
		const points = greatCirclePoints(32.8998, -97.0403, 41.9786, -87.9048);
		expect(points[0][0]).toBeCloseTo(32.8998, 4);
		expect(points[0][1]).toBeCloseTo(-97.0403, 4);
		expect(points[points.length - 1][0]).toBeCloseTo(41.9786, 4);
		expect(points[points.length - 1][1]).toBeCloseTo(-87.9048, 4);
	});

	it('interpolates a point roughly midway along the route', () => {
		// Two points equidistant from the equator on the same meridian --
		// the great-circle midpoint should sit on the equator at that meridian.
		const points = greatCirclePoints(40, 0, -40, 0, 2);
		expect(points[1][0]).toBeCloseTo(0, 4);
		expect(points[1][1]).toBeCloseTo(0, 4);
	});

	it('does not jump more than 180 degrees of longitude between consecutive points', () => {
		// A route crossing the antimeridian (Tokyo -> Honolulu-ish longitudes).
		const points = greatCirclePoints(35.5, 179.5, 35.5, -179.5, 16);
		for (let i = 1; i < points.length; i++) {
			expect(Math.abs(points[i][1] - points[i - 1][1])).toBeLessThan(180);
		}
	});

	it('handles near-identical origin and destination without NaN', () => {
		const points = greatCirclePoints(32.8998, -97.0403, 32.8998, -97.0403);
		expect(points.length).toBeGreaterThan(0);
		for (const [lat, lon] of points) {
			expect(Number.isNaN(lat)).toBe(false);
			expect(Number.isNaN(lon)).toBe(false);
		}
	});
});
