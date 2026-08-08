// Maps the backend's ADS-B emitter-category classification
// (backend/app/plugins/flights/plugin.py's _aircraft_kind) straight through
// to AircraftIcon.svelte's icon variants -- the backend already buckets raw
// category codes into these five kinds, so no further mapping logic is
// needed here beyond typing the value.
export type AircraftKind = 'helicopter' | 'jet' | 'prop' | 'other' | 'unknown';

export function aircraftIconKey(kind: string | null | undefined): AircraftKind {
	if (kind === 'helicopter' || kind === 'jet' || kind === 'prop' || kind === 'other') return kind;
	return 'unknown';
}
