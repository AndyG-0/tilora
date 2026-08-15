import { describe, expect, it } from 'vitest';
import { lookupAircraftName, formatSpeedTooltip, formatAircraftTooltip, formatAirlineTooltip } from './aircraftTypes';

describe('aircraftTypes', () => {
	it('looks up aircraft models by ICAO code', () => {
		expect(lookupAircraftName('B738')).toBe('Boeing 737-800');
		expect(lookupAircraftName('a320')).toBe('Airbus A320');
		expect(lookupAircraftName('b38m')).toBe('Boeing 737 MAX 8');
		expect(lookupAircraftName('C172')).toBe('Cessna 172 Skyhawk');
		expect(lookupAircraftName('E75L')).toBe('Embraer E175 (Enhanced Wingtips)');
		expect(lookupAircraftName('EC35')).toBe('Airbus Helicopters H135 / EC135');
		expect(lookupAircraftName('ZZZZ')).toBeNull();
		expect(lookupAircraftName(null)).toBeNull();
		expect(lookupAircraftName(undefined)).toBeNull();
	});

	it('formats speed tooltip based on unit preference', () => {
		// 450 kts * 1.15078 = 518 mph
		expect(formatSpeedTooltip(450, 'mph')).toBe('518 mph');
		// 450 kts * 1.852 = 833 km/h
		expect(formatSpeedTooltip(450, 'kmh')).toBe('833 km/h');
		expect(formatSpeedTooltip(null, 'mph')).toBe('');
		expect(formatSpeedTooltip(undefined, 'kmh')).toBe('');
	});

	it('formats aircraft tooltip with model, code, kind, and tail', () => {
		expect(
			formatAircraftTooltip(
				{
					aircraft_type: 'B738',
					aircraft_name: 'Boeing 737-800',
					aircraft_kind: 'jet',
					registration: 'N12345',
				},
				'Jet',
				'Tail',
			),
		).toBe('Boeing 737-800 (B738) · Tail: N12345');

		// Unknown aircraft type fallback
		expect(
			formatAircraftTooltip(
				{
					aircraft_type: 'UNKNOWN',
					aircraft_name: null,
					aircraft_kind: 'jet',
					registration: 'N999XX',
				},
				'Jet',
				'Tail',
			),
		).toBe('UNKNOWN (Jet) · Tail: N999XX');

		// No type code, only kind and registration
		expect(
			formatAircraftTooltip(
				{
					aircraft_type: null,
					aircraft_name: null,
					aircraft_kind: 'helicopter',
					registration: 'N555HE',
				},
				'Helicopter',
				'Tail',
			),
		).toBe('Helicopter · Tail: N555HE');
	});

	it('formats airline tooltip with airline name and code', () => {
		expect(formatAirlineTooltip({ airline_name: 'Delta Air Lines', airline_code: 'DAL' })).toBe(
			'Delta Air Lines (DAL)',
		);
		expect(formatAirlineTooltip({ airline_name: null, airline_code: 'XYZ' })).toBe('XYZ');
		expect(formatAirlineTooltip({ airline_name: null, airline_code: null })).toBe('');
	});
});
