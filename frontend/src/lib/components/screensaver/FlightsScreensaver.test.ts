import { render } from '@testing-library/svelte';
import { tick } from 'svelte';
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';

import FlightsScreensaver from './FlightsScreensaver.svelte';

// LedText renders each string twice (a blurred glow copy plus the visible
// dots copy), so text queries via screen.getByText match twice -- assert on
// the wrapping structural elements instead.

const baseData = {
	location_name: 'Fort Worth, TX',
	latitude: 32.7555,
	longitude: -97.3308,
	radius_nm: 15,
	speed_unit: 'mph' as const,
	count: 1,
	flights: [
		{
			hex: 'abc123',
			callsign: 'AAL100',
			airline_code: 'AAL',
			airline_name: 'American Airlines',
			aircraft_type: 'B789',
			aircraft_kind: 'jet',
			registration: 'N835AN',
			altitude_ft: 34000,
			speed_kts: 480,
			distance_nm: 12.4,
			heading: 270,
			latitude: 32.8,
			longitude: -97.4,
			origin: null,
			destination: null,
		},
	],
};

describe('FlightsScreensaver', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		localStorage.clear();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('starts on the list phase with no stored cursor', () => {
		render(FlightsScreensaver, { props: { id: 'flights-1', data: baseData } });

		expect(document.querySelector('.title')).toBeInTheDocument();
		expect(document.querySelector('.map-wrap')).not.toBeInTheDocument();
	});

	it('rotates from list to map after textPauseSeconds elapses', async () => {
		render(FlightsScreensaver, { props: { id: 'flights-1', data: baseData, textPauseSeconds: 8 } });

		expect(document.querySelector('.title')).toBeInTheDocument();

		await vi.advanceTimersByTimeAsync(8000);

		expect(document.querySelector('.title')).not.toBeInTheDocument();
		expect(document.querySelector('.map-wrap')).toBeInTheDocument();
	});

	it('persists the phase cursor to localStorage as it rotates', async () => {
		render(FlightsScreensaver, { props: { id: 'flights-1', data: baseData, textPauseSeconds: 8 } });

		await vi.advanceTimersByTimeAsync(8000);

		expect(localStorage.getItem('screensaver:cursor:flights-1')).toBe('1');
	});

	it('resumes on the map phase from a previously stored cursor', () => {
		localStorage.setItem('screensaver:cursor:flights-1', '1');

		render(FlightsScreensaver, { props: { id: 'flights-1', data: baseData } });

		expect(document.querySelector('.title')).not.toBeInTheDocument();
		expect(document.querySelector('.map-wrap')).toBeInTheDocument();
	});

	it('keys the stored cursor by widget id, not globally', () => {
		localStorage.setItem('screensaver:cursor:flights-1', '1');

		render(FlightsScreensaver, { props: { id: 'flights-2', data: baseData } });

		expect(document.querySelector('.title')).toBeInTheDocument();
	});

	it('shows the no-aircraft message when there are no flights', () => {
		render(FlightsScreensaver, { props: { id: 'flights-1', data: { ...baseData, count: 0, flights: [] } } });

		expect(document.querySelector('.empty')).toBeInTheDocument();
	});

	it('jumps to the clicked phase instead of waiting for the rotation timer', async () => {
		const { container } = render(FlightsScreensaver, {
			props: { id: 'flights-1', data: baseData, textPauseSeconds: 8 },
		});

		expect(document.querySelector('.title')).toBeInTheDocument();

		const dots = container.querySelectorAll('.dot');
		expect(dots).toHaveLength(2);

		(dots[1] as HTMLButtonElement).click();
		await tick();

		expect(document.querySelector('.title')).not.toBeInTheDocument();
		expect(document.querySelector('.map-wrap')).toBeInTheDocument();
	});
});
