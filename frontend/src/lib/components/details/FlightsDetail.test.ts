import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { locale, waitLocale } from 'svelte-i18n';

const { updateWidgetSettings, widgetDetail, searchCities } = vi.hoisted(() => ({
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
	searchCities: vi.fn(),
}));

vi.mock('$app/state', () => ({
	page: { params: { id: 'flights-widget-1' } },
}));

vi.mock('$lib/api', () => ({
	api: {
		updateWidgetSettings,
		widgetDetail,
		searchCities,
	},
}));

import { user } from '$lib/stores/user';
import FlightsDetail from './FlightsDetail.svelte';

const SAMPLE_DATA = {
	location_name: 'Dallas / Fort Worth, TX',
	latitude: 32.8998,
	longitude: -97.0403,
	radius_nm: 25,
	speed_unit: 'mph' as const,
	count: 2,
	flights: [
		{
			callsign: 'AAL100',
			airline_code: 'AAL',
			airline_name: 'American Airlines',
			aircraft_type: 'B789',
			aircraft_name: 'Boeing 787-9 Dreamliner',
			aircraft_kind: 'jet',
			registration: 'N835AN',
			altitude_ft: 34000,
			speed_kts: 480,
			distance_nm: 12.4,
			heading: 270,
			latitude: 32.9,
			longitude: -97.1,
			origin: { iata: 'DFW', icao: 'KDFW', city: 'Dallas-Fort Worth' },
			destination: { iata: 'LHR', icao: 'EGLL', city: 'London' },
		},
		{
			callsign: 'N12345',
			airline_code: null,
			airline_name: null,
			aircraft_type: 'C172',
			aircraft_name: 'Cessna 172 Skyhawk',
			aircraft_kind: 'prop',
			registration: 'N12345',
			altitude_ft: 4500,
			speed_kts: 120,
			distance_nm: 5.2,
			heading: 180,
			latitude: 32.8,
			longitude: -97.0,
			origin: null,
			destination: null,
		},
	],
};

describe('FlightsDetail', () => {
	beforeEach(() => {
		user.set({ id: 'admin-user', name: 'Admin', avatar: null, role: 'admin' });
	});

	afterEach(async () => {
		locale.set('en');
		await waitLocale();
		vi.clearAllMocks();
	});

	it('renders flights table with airline full name tooltip', async () => {
		render(FlightsDetail, { props: { data: SAMPLE_DATA } });

		const flightCell = screen.getByText('AAL100', { selector: '.dots' }).closest('.flight-cell');
		expect(flightCell?.querySelector('.cell-popover')).toHaveTextContent('American Airlines (AAL)');
	});

	it('renders speed tooltip converted to MPH when speed_unit is mph', async () => {
		render(FlightsDetail, { props: { data: SAMPLE_DATA } });

		// 480 kts * 1.15078 = 552 mph
		const speedCell = screen.getByText('480 KTS', { selector: '.dots' }).closest('.speed-cell');
		expect(speedCell?.querySelector('.cell-popover')).toHaveTextContent('552 mph');
	});

	it('switches speed tooltip to KM/H and saves widget setting when toggled', async () => {
		updateWidgetSettings.mockResolvedValue({});

		render(FlightsDetail, { props: { data: SAMPLE_DATA } });

		const kmhBtn = screen.getByRole('button', { name: 'KM/H' });
		expect(kmhBtn).not.toHaveClass('active');

		await fireEvent.click(kmhBtn);

		expect(updateWidgetSettings).toHaveBeenCalledWith('flights-widget-1', { speed_unit: 'kmh' });
		expect(kmhBtn).toHaveClass('active');

		// 480 kts * 1.852 = 889 km/h
		const speedCell = screen.getByText('480 KTS', { selector: '.dots' }).closest('.speed-cell');
		expect(speedCell?.querySelector('.cell-popover')).toHaveTextContent('889 km/h');
	});

	it('renders aircraft details tooltip with model name, code, and tail registration', async () => {
		render(FlightsDetail, { props: { data: SAMPLE_DATA } });

		const typeCell = screen.getByText('B789', { selector: '.dots' }).closest('.type-cell');
		expect(typeCell?.querySelector('.cell-popover')).toHaveTextContent('Boeing 787-9 Dreamliner (B789) · Tail: N835AN');

		const propTypeCell = screen.getByText('C172', { selector: '.dots' }).closest('.type-cell');
		expect(propTypeCell?.querySelector('.cell-popover')).toHaveTextContent('Cessna 172 Skyhawk (C172) · Tail: N12345');
	});

	it('handles unmapped aircraft types and displays category fallback', async () => {
		const customData = {
			...SAMPLE_DATA,
			flights: [
				{
					callsign: 'TEST99',
					airline_code: 'XYZ',
					airline_name: null,
					aircraft_type: 'UNKN',
					aircraft_name: null,
					aircraft_kind: 'jet',
					registration: null,
					altitude_ft: 20000,
					speed_kts: null,
					distance_nm: 8.0,
					heading: null,
					latitude: null,
					longitude: null,
					origin: null,
					destination: null,
				},
			],
		};

		render(FlightsDetail, { props: { data: customData } });

		const flightCell = screen.getByText('TEST99', { selector: '.dots' }).closest('.flight-cell');
		expect(flightCell?.querySelector('.cell-popover')).toHaveTextContent('XYZ');

		const typeCell = screen.getByText('UNKN', { selector: '.dots' }).closest('.type-cell');
		expect(typeCell?.querySelector('.cell-popover')).toHaveTextContent('UNKN (Jet)');

		const row = screen.getByText('TEST99', { selector: '.dots' }).closest('.table-row');
		const speedCell = row?.querySelector('.speed-cell');
		expect(speedCell?.querySelector('.cell-popover')).toBeNull();
	});

	it('shows edit controls for non-admin members', () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });
		render(FlightsDetail, { props: { data: SAMPLE_DATA } });

		expect(screen.getByText('Change location')).toBeInTheDocument();
		expect(screen.getByLabelText('Search radius (nm)')).toBeInTheDocument();
	});
});
