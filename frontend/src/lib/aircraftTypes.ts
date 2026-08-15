// Maps standard 4-character ICAO aircraft type designators (e.g. "B738", "A321")
// to human-readable aircraft models and provides tooltip formatting helpers.

export const AIRCRAFT_TYPES: Record<string, string> = {
	// Boeing Commercial
	B737: 'Boeing 737-700',
	B738: 'Boeing 737-800',
	B739: 'Boeing 737-900',
	B37M: 'Boeing 737 MAX 7',
	B38M: 'Boeing 737 MAX 8',
	B39M: 'Boeing 737 MAX 9',
	B3XM: 'Boeing 737 MAX 10',
	B744: 'Boeing 747-400',
	B748: 'Boeing 747-8',
	B752: 'Boeing 757-200',
	B753: 'Boeing 757-300',
	B762: 'Boeing 767-200',
	B763: 'Boeing 767-300',
	B764: 'Boeing 767-400',
	B772: 'Boeing 777-200',
	B77L: 'Boeing 777-200LR',
	B773: 'Boeing 777-300',
	B77W: 'Boeing 777-300ER',
	B778: 'Boeing 777-8',
	B779: 'Boeing 777-9',
	B788: 'Boeing 787-8 Dreamliner',
	B789: 'Boeing 787-9 Dreamliner',
	B78X: 'Boeing 787-10 Dreamliner',
	B712: 'Boeing 717-200',
	// Airbus Commercial
	A318: 'Airbus A318',
	A319: 'Airbus A319',
	A320: 'Airbus A320',
	A321: 'Airbus A321',
	A19N: 'Airbus A319neo',
	A20N: 'Airbus A320neo',
	A21N: 'Airbus A321neo',
	A21X: 'Airbus A321XLR',
	A332: 'Airbus A330-200',
	A333: 'Airbus A330-300',
	A338: 'Airbus A330-800neo',
	A339: 'Airbus A330-900neo',
	A342: 'Airbus A340-200',
	A343: 'Airbus A340-300',
	A345: 'Airbus A340-500',
	A346: 'Airbus A340-600',
	A359: 'Airbus A350-900',
	A35K: 'Airbus A350-1000',
	A388: 'Airbus A380-800',
	BCS1: 'Airbus A220-100',
	BCS3: 'Airbus A220-300',
	A221: 'Airbus A220-100',
	A223: 'Airbus A220-300',
	// Embraer
	E170: 'Embraer E170',
	E75L: 'Embraer E175 (Enhanced Wingtips)',
	E75S: 'Embraer E175 (Standard)',
	E175: 'Embraer E175',
	E190: 'Embraer E190',
	E195: 'Embraer E195',
	E290: 'Embraer E190-E2',
	E295: 'Embraer E195-E2',
	E135: 'Embraer ERJ-135',
	E145: 'Embraer ERJ-145',
	// Bombardier / Regional
	CRJ1: 'Bombardier CRJ-100',
	CRJ2: 'Bombardier CRJ-200',
	CRJ7: 'Bombardier CRJ-700',
	CRJ9: 'Bombardier CRJ-900',
	CRJX: 'Bombardier CRJ-1000',
	// Turboprops
	DH8A: 'De Havilland Dash 8-100',
	DH8B: 'De Havilland Dash 8-200',
	DH8C: 'De Havilland Dash 8-300',
	DH8D: 'De Havilland Dash 8-400',
	DHC6: 'De Havilland DHC-6 Twin Otter',
	AT43: 'ATR 42-300',
	AT45: 'ATR 42-500',
	AT46: 'ATR 42-600',
	AT72: 'ATR 72-200',
	AT73: 'ATR 72-210',
	AT75: 'ATR 72-500',
	AT76: 'ATR 72-600',
	SF34: 'Saab 340',
	SB20: 'Saab 2000',
	// General Aviation
	C150: 'Cessna 150',
	C152: 'Cessna 152',
	C172: 'Cessna 172 Skyhawk',
	C182: 'Cessna 182 Skylane',
	C206: 'Cessna 206 Stationair',
	C208: 'Cessna 208 Caravan',
	C210: 'Cessna 210 Centurion',
	PA28: 'Piper PA-28 Cherokee',
	PA32: 'Piper PA-32 Saratoga',
	PA34: 'Piper PA-34 Seneca',
	PA44: 'Piper PA-44 Seminole',
	PA46: 'Piper PA-46 Malibu',
	SR20: 'Cirrus SR20',
	SR22: 'Cirrus SR22',
	SF50: 'Cirrus Vision Jet',
	BE33: 'Beechcraft Bonanza 33',
	BE35: 'Beechcraft Bonanza 35',
	BE36: 'Beechcraft Bonanza 36',
	BE55: 'Beechcraft Baron 55',
	BE58: 'Beechcraft Baron 58',
	BE9L: 'Beechcraft King Air 90',
	BE20: 'Beechcraft Super King Air 200',
	B350: 'Beechcraft Super King Air 350',
	BE40: 'Beechjet 400',
	PC12: 'Pilatus PC-12',
	PC24: 'Pilatus PC-24',
	TBM7: 'Daher TBM 700',
	TBM8: 'Daher TBM 850',
	TBM9: 'Daher TBM 900',
	DA20: 'Diamond DA20 Katana',
	DA40: 'Diamond DA40 Diamond Star',
	DA42: 'Diamond DA42 Twin Star',
	DA62: 'Diamond DA62',
	// Business Jets
	C510: 'Cessna Citation Mustang',
	C525: 'Cessna CitationJet / CJ1',
	C25A: 'Cessna Citation CJ2',
	C25B: 'Cessna Citation CJ3',
	C25C: 'Cessna Citation CJ4',
	C550: 'Cessna Citation II / Bravo',
	C560: 'Cessna Citation V / Ultra',
	C56X: 'Cessna Citation Excel / XLS',
	C680: 'Cessna Citation Sovereign',
	C68A: 'Cessna Citation Latitude',
	C700: 'Cessna Citation Longitude',
	C750: 'Cessna Citation X',
	CL30: 'Bombardier Challenger 300',
	CL35: 'Bombardier Challenger 350',
	CL60: 'Bombardier Challenger 600',
	GLEX: 'Bombardier Global Express',
	GL5T: 'Bombardier Global 5000',
	GL7T: 'Bombardier Global 7500',
	GLF4: 'Gulfstream IV / G450',
	GLF5: 'Gulfstream V / G550',
	GLF6: 'Gulfstream G650 / G700',
	G280: 'Gulfstream G280',
	FA50: 'Dassault Falcon 50',
	FA7X: 'Dassault Falcon 7X',
	FA8X: 'Dassault Falcon 8X',
	F900: 'Dassault Falcon 900',
	F2TH: 'Dassault Falcon 2000',
	LJ35: 'Learjet 35',
	LJ45: 'Learjet 45',
	LJ60: 'Learjet 60',
	LJ75: 'Learjet 75',
	E50P: 'Embraer Phenom 100',
	E55P: 'Embraer Phenom 300',
	E545: 'Embraer Legacy 450',
	E550: 'Embraer Legacy 500',
	HA420: 'HondaJet HA-420',
	// Helicopters
	R22: 'Robinson R22',
	R44: 'Robinson R44',
	R66: 'Robinson R66',
	B06: 'Bell 206 JetRanger',
	B407: 'Bell 407',
	B412: 'Bell 412',
	B429: 'Bell 429 GlobalRanger',
	EC20: 'Eurocopter EC120 Colibri',
	EC30: 'Eurocopter EC130',
	AS50: 'Eurocopter AS350 Écureuil',
	EC35: 'Airbus Helicopters H135 / EC135',
	H135: 'Airbus Helicopters H135',
	EC45: 'Airbus Helicopters H145 / EC145',
	H145: 'Airbus Helicopters H145',
	AS65: 'Eurocopter AS365 Dauphin',
	H155: 'Airbus Helicopters H155',
	H160: 'Airbus Helicopters H160',
	H225: 'Airbus Helicopters H225 Super Puma',
	AS32: 'Eurocopter AS332 Super Puma',
	S76: 'Sikorsky S-76',
	S92: 'Sikorsky S-92',
	UH60: 'Sikorsky UH-60 Black Hawk',
	CH47: 'Boeing CH-47 Chinook',
	A139: 'AgustaWestland AW139',
	AW139: 'AgustaWestland AW139',
	A109: 'AgustaWestland AW109',
	AW109: 'AgustaWestland AW109',
	AW169: 'AgustaWestland AW169',
	AW189: 'AgustaWestland AW189',
	MD52: 'MD Helicopters MD 500',
};

export function lookupAircraftName(code: string | null | undefined): string | null {
	if (!code) return null;
	return AIRCRAFT_TYPES[code.trim().toUpperCase()] ?? null;
}

export function formatSpeedTooltip(speedKts: number | null | undefined, unit: 'mph' | 'kmh'): string {
	if (speedKts === null || speedKts === undefined) return '';
	if (unit === 'kmh') {
		const kmh = Math.round(speedKts * 1.852);
		return `${kmh} km/h`;
	}
	const mph = Math.round(speedKts * 1.15078);
	return `${mph} mph`;
}

export interface AircraftTooltipFlight {
	aircraft_type?: string | null;
	aircraft_name?: string | null;
	aircraft_kind?: string | null;
	registration?: string | null;
}

export function formatAircraftTooltip(flight: AircraftTooltipFlight, kindLabel?: string, tailLabel = 'Tail'): string {
	const parts: string[] = [];
	const name = flight.aircraft_name ?? lookupAircraftName(flight.aircraft_type);

	if (name) {
		parts.push(name);
		if (flight.aircraft_type && !name.includes(flight.aircraft_type)) {
			parts.push(`(${flight.aircraft_type})`);
		}
	} else if (flight.aircraft_type) {
		parts.push(flight.aircraft_type);
		if (kindLabel) parts.push(`(${kindLabel})`);
	} else if (kindLabel) {
		parts.push(kindLabel);
	}

	if (flight.registration) {
		parts.push(`· ${tailLabel}: ${flight.registration}`);
	}

	return parts.join(' ') || (flight.aircraft_type ?? '');
}

export function formatAirlineTooltip(flight: { airline_name?: string | null; airline_code?: string | null }): string {
	if (flight.airline_name && flight.airline_code) {
		return `${flight.airline_name} (${flight.airline_code})`;
	}
	return flight.airline_name ?? flight.airline_code ?? '';
}
