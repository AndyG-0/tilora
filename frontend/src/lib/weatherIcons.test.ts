import { describe, expect, it } from 'vitest';
import { weatherIconKey } from './weatherIcons';

describe('weatherIconKey', () => {
	it('picks the day/night clear variant based on is_day', () => {
		expect(weatherIconKey(0, true)).toBe('clear-day');
		expect(weatherIconKey(0, false)).toBe('clear-night');
	});

	it('picks the day/night partly-cloudy variant for mainly-clear and partly-cloudy codes', () => {
		expect(weatherIconKey(1, true)).toBe('partly-cloudy-day');
		expect(weatherIconKey(2, false)).toBe('partly-cloudy-night');
	});

	it('maps overcast to cloudy regardless of time of day', () => {
		expect(weatherIconKey(3, true)).toBe('cloudy');
		expect(weatherIconKey(3, false)).toBe('cloudy');
	});

	it('maps fog codes', () => {
		expect(weatherIconKey(45, true)).toBe('fog');
		expect(weatherIconKey(48, false)).toBe('fog');
	});

	it('maps drizzle, rain, and shower codes', () => {
		expect(weatherIconKey(51, true)).toBe('drizzle');
		expect(weatherIconKey(63, true)).toBe('rain');
		expect(weatherIconKey(80, true)).toBe('showers');
	});

	it('maps snow codes', () => {
		expect(weatherIconKey(71, true)).toBe('snow');
		expect(weatherIconKey(75, false)).toBe('snow');
	});

	it('maps thunderstorm codes', () => {
		expect(weatherIconKey(95, true)).toBe('thunderstorm');
		expect(weatherIconKey(99, false)).toBe('thunderstorm');
	});

	it('falls back to cloudy for unknown codes', () => {
		expect(weatherIconKey(999, true)).toBe('cloudy');
	});
});
