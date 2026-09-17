<script lang="ts">
	import { airlineLogoSrc } from '$lib/airlineLogos';
	import LedText from '$lib/components/LedText.svelte';
	import FlightsMap from '$lib/components/FlightsMap.svelte';
	import { getCursor, setCursor } from '$lib/stores/screensaverProgress';
	import ScreenIndicator from './ScreenIndicator.svelte';
	import { _ } from 'svelte-i18n';

	interface AirportRef {
		iata: string | null;
		icao: string;
		city: string | null;
		latitude: number | null;
		longitude: number | null;
	}

	interface FlightItem {
		hex?: string | null;
		callsign: string;
		airline_code: string | null;
		airline_name: string | null;
		aircraft_type: string | null;
		aircraft_kind: string | null;
		registration?: string | null;
		altitude_ft: number | null;
		speed_kts: number | null;
		distance_nm: number | null;
		heading: number | null;
		latitude: number | null;
		longitude: number | null;
		origin: AirportRef | null;
		destination: AirportRef | null;
	}

	interface FlightsScreensaverData {
		location_name: string;
		latitude: number;
		longitude: number;
		radius_nm: number;
		speed_unit?: 'mph' | 'kmh';
		count: number;
		flights: FlightItem[];
	}

	let {
		id,
		data,
		ledColor = '#ff8a00',
		textPauseSeconds = 8,
	}: { id: string; data: FlightsScreensaverData; ledColor?: string; textPauseSeconds?: number } = $props();

	const PHASES = ['list', 'map'] as const;
	type Phase = (typeof PHASES)[number];

	const initialCursor = getCursor(id);
	let phaseIndex = $state(initialCursor % PHASES.length);
	const phase = $derived<Phase>(PHASES[phaseIndex]);
	let advanceTimer: ReturnType<typeof setTimeout> | null = null;

	function scheduleAdvance() {
		if (advanceTimer) clearTimeout(advanceTimer);
		advanceTimer = setTimeout(
			() => {
				phaseIndex = (phaseIndex + 1) % PHASES.length;
			},
			Math.max(1, textPauseSeconds) * 1000,
		);
	}

	$effect(() => {
		// Depend on phaseIndex so a new timer is scheduled every phase change.
		void phaseIndex;
		scheduleAdvance();
		return () => {
			if (advanceTimer) clearTimeout(advanceTimer);
		};
	});

	$effect(() => {
		setCursor(id, phaseIndex);
	});

	function kindTag(kind: string | null): string {
		if (kind === 'helicopter') return 'HELI';
		if (kind === 'jet') return 'JET ';
		if (kind === 'prop') return 'PROP';
		if (kind === 'other') return 'A/C ';
		return '----';
	}

	function airportCode(airport: AirportRef): string {
		return airport.iata ?? airport.icao;
	}

	// 9 chars sized for the ICAO-fallback worst case, e.g. "KABQ-KHOU".
	function routeTag(flight: FlightItem): string {
		if (!flight.origin || !flight.destination) return '---------';
		return `${airportCode(flight.origin)}-${airportCode(flight.destination)}`.padEnd(9);
	}

	// Fixed-width columns (padEnd) read as aligned only with a monospace-ish
	// font and `white-space: pre` below -- matches a real split-flap board's
	// column layout without a full table.
	function formatRow(flight: FlightItem): string {
		const callsign = (flight.callsign || flight.registration || flight.hex || '').padEnd(9);
		const kind = kindTag(flight.aircraft_kind).padEnd(5);
		const type = (flight.aircraft_type ?? '---').padEnd(7);
		const route = routeTag(flight).padEnd(10);
		const altitude =
			flight.altitude_ft !== null
				? `FL${Math.round(flight.altitude_ft / 100)
						.toString()
						.padStart(3, '0')}`
				: '-----';
		const distance = flight.distance_nm !== null ? `${flight.distance_nm.toFixed(1)}NM` : '--NM';
		return `${callsign}${kind}${type}${route}${altitude.padEnd(8)}${distance}`;
	}
</script>

<div class="sign" style="--dotmatrix-color: {ledColor}">
	{#if phase === 'list'}
		<div class="title">
			<LedText text={data.location_name.toUpperCase()} color={ledColor} weight={700} />
		</div>

		{#if data.flights.length === 0}
			<div class="empty">
				<LedText text={$_('flights.screensaver.no_aircraft')} color={ledColor} />
			</div>
		{:else}
			<div class="rows">
				{#each data.flights as flight (flight.hex ?? flight.callsign)}
					{@const logo = airlineLogoSrc(flight.airline_code)}
					<div class="row">
						{#if logo}
							<img class="logo" src={logo} alt="" />
						{:else}
							<span class="logo-spacer"></span>
						{/if}
						<div class="row-text">
							<LedText text={formatRow(flight)} color={ledColor} />
						</div>
					</div>
				{/each}
			</div>
		{/if}
	{:else}
		<FlightsMap {data} interactive={false} fillHeight={true} />
	{/if}

	<ScreenIndicator current={phaseIndex} total={PHASES.length} onselect={(page) => (phaseIndex = page)} />
</div>

<style>
	.sign {
		height: 100%;
		width: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1.5rem;
		background: #0a0a0a;
		overflow: hidden;
		padding: 2rem;
		box-sizing: border-box;
		position: relative;
	}

	.rows {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.logo {
		width: 2.25rem;
		height: auto;
		image-rendering: pixelated;
		flex-shrink: 0;
	}

	.logo-spacer {
		width: 2.25rem;
		flex-shrink: 0;
	}

	.title {
		font-size: clamp(1.25rem, 3.5vw, 2.25rem);
	}

	.empty,
	.row-text {
		font-size: clamp(1rem, 2.4vw, 1.6rem);
	}
</style>
