<script lang="ts">
	import { airlineLogoSrc } from '$lib/airlineLogos';
	import { _ } from 'svelte-i18n';

	interface FlightItem {
		callsign: string;
		airline_code: string | null;
		airline_name: string | null;
		aircraft_type: string | null;
		altitude_ft: number | null;
		speed_kts: number | null;
		distance_nm: number | null;
	}

	interface FlightsScreensaverData {
		location_name: string;
		radius_nm: number;
		count: number;
		flights: FlightItem[];
	}

	let { data, ledColor = '#ff8a00' }: { data: FlightsScreensaverData; ledColor?: string } = $props();

	// Fixed-width columns (padEnd) read as aligned only with a monospace-ish
	// font and `white-space: pre` below -- matches a real split-flap board's
	// column layout without a full table.
	function formatRow(flight: FlightItem): string {
		const callsign = flight.callsign.padEnd(9);
		const type = (flight.aircraft_type ?? '---').padEnd(7);
		const altitude =
			flight.altitude_ft !== null
				? `FL${Math.round(flight.altitude_ft / 100)
						.toString()
						.padStart(3, '0')}`
				: '-----';
		const distance = flight.distance_nm !== null ? `${flight.distance_nm.toFixed(1)}NM` : '--NM';
		return `${callsign}${type}${altitude.padEnd(8)}${distance}`;
	}
</script>

<div class="sign" style="--dotmatrix-color: {ledColor}">
	<div class="stack title">
		<span class="text glow" aria-hidden="true">{data.location_name.toUpperCase()}</span>
		<span class="text dots">{data.location_name.toUpperCase()}</span>
	</div>

	{#if data.flights.length === 0}
		<div class="stack">
			<span class="text glow" aria-hidden="true">{$_('flights.screensaver.no_aircraft')}</span>
			<span class="text dots">{$_('flights.screensaver.no_aircraft')}</span>
		</div>
	{:else}
		<div class="rows">
			{#each data.flights as flight (flight.callsign)}
				{@const logo = airlineLogoSrc(flight.airline_code)}
				<div class="row">
					{#if logo}
						<img class="logo" src={logo} alt="" />
					{:else}
						<span class="logo-spacer"></span>
					{/if}
					<div class="stack">
						<span class="text glow" aria-hidden="true">{formatRow(flight)}</span>
						<span class="text dots">{formatRow(flight)}</span>
					</div>
				</div>
			{/each}
		</div>
	{/if}
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

	.stack {
		position: relative;
		display: grid;
	}

	.title {
		font-size: clamp(1.25rem, 3.5vw, 2.25rem);
	}

	.text {
		grid-area: 1 / 1;
		margin: 0;
		white-space: pre;
		font-family: 'Doto Variable', 'Courier New', monospace;
		font-variation-settings: 'wght' 500;
		font-weight: 500;
		font-size: clamp(1rem, 2.4vw, 1.6rem);
		letter-spacing: 0.03em;
	}

	.title .text {
		font-variation-settings: 'wght' 700;
		font-weight: 700;
	}

	/* Blurred solid-color copy behind the dots -- the glow's own blur must
	   never touch the dot pattern itself, or it fills the gaps between dots
	   and washes the grid into a solid glow. */
	.glow {
		color: var(--dotmatrix-color);
		filter: blur(0.08em);
		opacity: 0.75;
	}

	.dots {
		color: var(--dotmatrix-color);
	}
</style>
