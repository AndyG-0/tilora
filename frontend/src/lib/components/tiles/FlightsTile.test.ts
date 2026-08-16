import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { locale, waitLocale } from 'svelte-i18n';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import FlightsTile from './FlightsTile.svelte';

describe('FlightsTile', () => {
	afterEach(async () => {
		locale.set('en');
		await waitLocale();
	});

	it('translates static text when the locale changes', async () => {
		locale.set('es');
		await waitLocale();
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(FlightsTile, { props: { widgetId: 'flights', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Cargando vuelos…')).toBeInTheDocument();
	});

	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(FlightsTile, { props: { widgetId: 'flights', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Loading flights…')).toBeInTheDocument();
	});

	it('renders the fetched summary', async () => {
		widgetSummary.mockResolvedValue({
			location_name: 'Fort Worth, TX',
			radius_nm: 15,
			count: 1,
			flights: [
				{
					callsign: 'UAL123',
					airline_code: 'UAL',
					airline_name: 'United Airlines',
					aircraft_type: 'B738',
					aircraft_kind: 'jet',
					altitude_ft: 35000,
					distance_nm: 4.2,
					origin: { iata: null, icao: 'KABQ', city: 'Albuquerque' },
					destination: { iata: null, icao: 'KHOU', city: 'Houston' },
				},
			],
		});

		render(FlightsTile, { props: { widgetId: 'flights', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('FORT WORTH, TX', { selector: '.dots' })).toBeInTheDocument();
		expect(screen.getByText('1 nearby')).toBeInTheDocument();
		expect(screen.getByText('UAL123', { selector: '.dots' })).toBeInTheDocument();
		expect(screen.getByText('35,000 FT', { selector: '.dots' })).toBeInTheDocument();
		expect(screen.getByText('KABQ → KHOU', { selector: '.dots' })).toBeInTheDocument();
		expect(screen.getByRole('img', { name: 'Jet' })).toBeInTheDocument();
	});

	it('omits the route line when the flight has no known route', async () => {
		widgetSummary.mockResolvedValue({
			location_name: 'Fort Worth, TX',
			radius_nm: 15,
			count: 1,
			flights: [
				{
					callsign: 'N126JH',
					airline_code: null,
					airline_name: null,
					aircraft_type: 'C172',
					aircraft_kind: 'prop',
					altitude_ft: 4500,
					distance_nm: 2.1,
					origin: null,
					destination: null,
				},
			],
		});

		render(FlightsTile, { props: { widgetId: 'flights', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('N126JH', { selector: '.dots' })).toBeInTheDocument();
		expect(screen.queryByText('→', { exact: false })).not.toBeInTheDocument();
	});

	it('shows the empty state when no flights are nearby', async () => {
		widgetSummary.mockResolvedValue({
			location_name: 'Fort Worth, TX',
			radius_nm: 15,
			count: 0,
			flights: [],
		});

		render(FlightsTile, { props: { widgetId: 'flights', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('No aircraft nearby')).toBeInTheDocument();
	});

	it('keeps the last known value when a later poll fails', async () => {
		vi.useFakeTimers();
		try {
			widgetSummary.mockResolvedValueOnce({
				location_name: 'Fort Worth, TX',
				radius_nm: 15,
				count: 0,
				flights: [],
			});
			render(FlightsTile, { props: { widgetId: 'flights', refreshIntervalSeconds: 60 } });
			await vi.advanceTimersByTimeAsync(0); // flush the initial refresh() from onMount
			expect(screen.getByText('FORT WORTH, TX', { selector: '.dots' })).toBeInTheDocument();

			widgetSummary.mockRejectedValueOnce(new Error('network error'));
			await vi.advanceTimersByTimeAsync(60_000);

			expect(screen.getByText('FORT WORTH, TX', { selector: '.dots' })).toBeInTheDocument();
		} finally {
			vi.useRealTimers();
		}
	});
});
