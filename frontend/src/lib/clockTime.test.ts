import { describe, expect, it } from 'vitest';
import { wallTime, wordPhrase } from './clockTime';

describe('wallTime', () => {
	it('extracts hour/minute/second in the given timezone', () => {
		const date = new Date('2024-03-15T10:30:15Z');

		expect(wallTime(date, 'UTC')).toEqual({ hours: 10, minutes: 30, seconds: 15 });
		expect(wallTime(date, 'America/Chicago')).toEqual({ hours: 5, minutes: 30, seconds: 15 });
	});

	it('reports midnight as hour 0, not 24', () => {
		const date = new Date('2024-03-15T00:00:00Z');

		expect(wallTime(date, 'UTC').hours).toBe(0);
	});
});

describe('wordPhrase', () => {
	it("says the hour o'clock on the hour", () => {
		expect(wordPhrase(3, 0)).toBe("three o'clock");
	});

	it("says midnight and noon instead of zero/twelve o'clock", () => {
		expect(wordPhrase(0, 0)).toBe('midnight');
		expect(wordPhrase(12, 0)).toBe('noon');
	});

	it('phrases minutes past the hour', () => {
		expect(wordPhrase(3, 10)).toBe('ten past three');
		expect(wordPhrase(3, 15)).toBe('quarter past three');
		expect(wordPhrase(3, 30)).toBe('half past three');
	});

	it('phrases minutes to the next hour', () => {
		expect(wordPhrase(3, 45)).toBe('quarter to four');
		expect(wordPhrase(3, 55)).toBe('five to four');
	});

	it('rolls to the next hour name at :55-rounds-to-:60 wraparound', () => {
		expect(wordPhrase(11, 58)).toBe("twelve o'clock");
	});

	it('rounds minutes to the nearest 5', () => {
		expect(wordPhrase(3, 12)).toBe('ten past three');
		expect(wordPhrase(3, 13)).toBe('quarter past three');
	});
});
