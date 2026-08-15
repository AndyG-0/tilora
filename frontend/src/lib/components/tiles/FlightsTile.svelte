<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import { formatAircraftTooltip, formatAirlineTooltip } from '$lib/aircraftTypes';
	import TileCard from '$lib/components/TileCard.svelte';
	import LedText from '$lib/components/LedText.svelte';
	import AircraftIcon from '$lib/components/AircraftIcon.svelte';
	import { _ } from 'svelte-i18n';

	interface AirportRef {
		iata: string | null;
		icao: string;
		city: string | null;
	}

	interface FlightItem {
		callsign: string;
		airline_code: string | null;
		airline_name: string | null;
		aircraft_type: string | null;
		aircraft_name?: string | null;
		aircraft_kind: string | null;
		registration?: string | null;
		altitude_ft: number | null;
		distance_nm: number | null;
		origin: AirportRef | null;
		destination: AirportRef | null;
	}

	interface FlightsSummary {
		location_name: string;
		radius_nm: number;
		count: number;
		flights: FlightItem[];
	}

	const LED_COLOR = '#ff8a00';

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<FlightsSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<FlightsSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);

	function airportCode(airport: AirportRef): string {
		return airport.iata ?? airport.icao;
	}
</script>

<TileCard {widgetId}>
	<div class="board">
		{#if summary}
			<div class="header">
				<LedText text={summary.location_name.toUpperCase()} color={LED_COLOR} weight={700} />
				<span class="count">
					{summary.count > 0
						? $_('flights.tile.count', { values: { count: summary.count } })
						: $_('flights.tile.empty')}
				</span>
			</div>
			<ul class="rows">
				{#each summary.flights.slice(0, 3) as flight (flight.callsign)}
					{@const airlineTitle = formatAirlineTooltip(flight)}
					{@const aircraftTitle = formatAircraftTooltip(
						flight,
						flight.aircraft_kind ? $_(`flights.aircraft_kind.${flight.aircraft_kind}`) : undefined,
					)}
					<li class="row">
						<span class="icon" title={aircraftTitle || undefined}>
							<AircraftIcon
								kind={flight.aircraft_kind}
								label={$_(`flights.aircraft_kind.${flight.aircraft_kind ?? 'unknown'}`)}
								color={LED_COLOR}
							/>
						</span>
						<div class="lines">
							<div class="line callsign" title={airlineTitle || undefined}>
								<LedText text={flight.callsign} color={LED_COLOR} weight={700} />
								{#if flight.altitude_ft !== null}
									<span class="altitude-text">
										<LedText text={`${Math.round(flight.altitude_ft).toLocaleString()} FT`} color={LED_COLOR} />
									</span>
								{/if}
							</div>
							{#if flight.origin && flight.destination}
								<div class="line route">
									<LedText
										text={`${airportCode(flight.origin)} → ${airportCode(flight.destination)}`}
										color={LED_COLOR}
									/>
								</div>
							{/if}
						</div>
					</li>
				{/each}
			</ul>
		{:else}
			<div class="count">{$_('flights.tile.loading')}</div>
		{/if}
	</div>
</TileCard>

<style>
	.board {
		margin: -1.25rem;
		padding: 1.25rem;
		width: calc(100% + 2.5rem);
		height: calc(100% + 2.5rem);
		background: #0a0a0a;
		box-sizing: border-box;
		overflow: hidden;
	}

	.header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.5rem;
		font-size: clamp(0.75rem, 8cqh, 0.9rem);
	}

	.header :global(.stack) {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.count {
		color: var(--color-text-muted);
		flex-shrink: 0;
	}

	.rows {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.icon {
		width: clamp(1.25rem, 12cqh, 1.75rem);
		height: clamp(1.25rem, 12cqh, 1.75rem);
		flex-shrink: 0;
	}

	.lines {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		min-width: 0;
		flex: 1;
	}

	.line {
		font-size: clamp(0.75rem, 9cqh, 1rem);
	}

	.callsign {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.altitude-text {
		font-size: 0.8em;
		flex-shrink: 0;
	}

	.route {
		font-size: 0.75em;
		opacity: 0.85;
	}
</style>
