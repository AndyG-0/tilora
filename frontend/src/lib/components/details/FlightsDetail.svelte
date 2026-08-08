<script lang="ts">
	import { page } from '$app/state';
	import { api, type CityResult } from '$lib/api';
	import { airlineLogoSrc } from '$lib/airlineLogos';
	import LedText from '$lib/components/LedText.svelte';
	import AircraftIcon from '$lib/components/AircraftIcon.svelte';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

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
		aircraft_kind: string | null;
		altitude_ft: number | null;
		speed_kts: number | null;
		distance_nm: number | null;
		origin: AirportRef | null;
		destination: AirportRef | null;
	}

	const LED_COLOR = '#ff8a00';

	function airportCode(airport: AirportRef): string {
		return airport.iata ?? airport.icao;
	}

	function routeText(flight: FlightItem): string {
		return flight.origin && flight.destination
			? `${airportCode(flight.origin)} → ${airportCode(flight.destination)}`
			: '—';
	}

	interface FlightsDetailData {
		location_name: string;
		radius_nm: number;
		count: number;
		flights: FlightItem[];
	}

	let { data: initialData }: { data: FlightsDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from selectCity/saveRadius.
	let flightsData = $state(initialData);

	let editingLocation = $state(false);
	let query = $state('');
	let results = $state<CityResult[]>([]);
	let searching = $state(false);
	let saving = $state(false);
	let error = $state<string | null>(null);

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once.
	let radiusInput = $state(initialData.radius_nm);
	let savingRadius = $state(false);

	let searchTimeout: ReturnType<typeof setTimeout>;

	function onQueryInput() {
		clearTimeout(searchTimeout);
		const trimmed = query.trim();
		if (trimmed.length < 2) {
			results = [];
			searching = false;
			return;
		}
		searching = true;
		searchTimeout = setTimeout(async () => {
			try {
				results = await api.searchCities(trimmed);
				error = null;
			} catch {
				error = get(_)('flights.detail.search_failed');
			} finally {
				searching = false;
			}
		}, 300);
	}

	function cityLabel(city: CityResult): string {
		const region = city.admin1 ?? city.country ?? '';
		return region ? `${city.name}, ${region}` : city.name;
	}

	async function selectCity(city: CityResult) {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(page.params.id!, {
				latitude: city.latitude,
				longitude: city.longitude,
				location_name: cityLabel(city),
			});
			flightsData = await api.widgetDetail<FlightsDetailData>(page.params.id!);
			editingLocation = false;
			query = '';
			results = [];
		} catch {
			error = get(_)('flights.detail.update_failed');
		} finally {
			saving = false;
		}
	}

	async function saveRadius() {
		savingRadius = true;
		error = null;
		try {
			await api.updateWidgetSettings(page.params.id!, { radius_nm: radiusInput });
			flightsData = await api.widgetDetail<FlightsDetailData>(page.params.id!);
		} catch {
			error = get(_)('flights.detail.update_failed');
		} finally {
			savingRadius = false;
		}
	}
</script>

<div class="header">
	<h1>{flightsData.location_name}</h1>
	<button class="change-location" onclick={() => (editingLocation = !editingLocation)}>
		{editingLocation ? $_('flights.detail.cancel') : $_('flights.detail.change_location')}
	</button>
</div>

{#if editingLocation}
	<div class="location-search">
		<input
			type="text"
			placeholder={$_('flights.detail.search_placeholder')}
			bind:value={query}
			oninput={onQueryInput}
		/>
		{#if searching}
			<p class="hint">{$_('flights.detail.searching')}</p>
		{:else if error}
			<p class="hint error">{error}</p>
		{:else if query.trim().length >= 2 && results.length === 0}
			<p class="hint">{$_('flights.detail.no_cities_found')}</p>
		{/if}
		{#if results.length > 0}
			<ul class="results">
				{#each results as city (city.latitude + ',' + city.longitude)}
					<li>
						<button disabled={saving} onclick={() => selectCity(city)}>
							{cityLabel(city)}
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
{/if}

<label class="radius">
	{$_('flights.detail.radius_label')}
	<input type="number" min="1" max="250" bind:value={radiusInput} disabled={savingRadius} onchange={saveRadius} />
</label>

{#if flightsData.flights.length === 0}
	<p class="empty">{$_('flights.detail.empty')}</p>
{:else}
	<div class="table">
		<div class="table-header">
			<span>{$_('flights.detail.column_flight')}</span>
			<span>{$_('flights.detail.column_type')}</span>
			<span>{$_('flights.detail.column_route')}</span>
			<span>{$_('flights.detail.column_altitude')}</span>
			<span>{$_('flights.detail.column_speed')}</span>
			<span>{$_('flights.detail.column_distance')}</span>
		</div>
		{#each flightsData.flights as flight (flight.callsign)}
			{@const logo = airlineLogoSrc(flight.airline_code)}
			<div class="table-row">
				<span class="flight-cell">
					{#if logo}
						<img class="logo" src={logo} alt={flight.airline_name ?? flight.airline_code} />
					{:else if flight.airline_code}
						<span class="badge">{flight.airline_code}</span>
					{/if}
					<LedText text={flight.callsign} color={LED_COLOR} weight={700} />
				</span>
				<span class="type-cell">
					<span class="icon">
						<AircraftIcon
							kind={flight.aircraft_kind}
							label={$_(`flights.aircraft_kind.${flight.aircraft_kind ?? 'unknown'}`)}
							color={LED_COLOR}
						/>
					</span>
					<LedText text={flight.aircraft_type ?? '—'} color={LED_COLOR} />
				</span>
				<LedText text={routeText(flight)} color={LED_COLOR} />
				<LedText
					text={flight.altitude_ft !== null ? `${Math.round(flight.altitude_ft).toLocaleString()} FT` : '—'}
					color={LED_COLOR}
				/>
				<LedText text={flight.speed_kts !== null ? `${Math.round(flight.speed_kts)} KTS` : '—'} color={LED_COLOR} />
				<LedText text={flight.distance_nm !== null ? `${flight.distance_nm.toFixed(1)} NM` : '—'} color={LED_COLOR} />
			</div>
		{/each}
	</div>
{/if}

<style>
	.header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
	}

	.header h1 {
		margin: 0;
	}

	.change-location {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.location-search {
		margin: 1rem 0;
	}

	.location-search input {
		width: 100%;
		max-width: 20rem;
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.hint {
		color: var(--color-text-muted);
		margin: 0.5rem 0 0;
	}

	.hint.error {
		color: var(--color-error);
	}

	.results {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0;
		max-width: 20rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.results button {
		width: 100%;
		text-align: left;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
		cursor: pointer;
	}

	.results button:active {
		background: var(--color-surface-hover);
	}

	.radius {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 1rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.radius input {
		width: 5rem;
		font: inherit;
		padding: 0.3rem 0.5rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.empty {
		color: var(--color-text-muted);
		margin-top: 2rem;
	}

	.table {
		margin-top: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.table-header,
	.table-row {
		display: grid;
		grid-template-columns: 2fr 1fr 1.4fr 1fr 1fr 1fr;
		gap: 0.75rem;
		align-items: center;
		padding: 0.5rem 0.75rem;
	}

	.table-header {
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
	}

	.table-row {
		background: #0a0a0a;
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
	}

	.flight-cell {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
	}

	.type-cell {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		min-width: 0;
	}

	.type-cell .icon {
		width: 1.5rem;
		height: 1.5rem;
		flex-shrink: 0;
	}

	.logo {
		width: 1.75rem;
		height: auto;
		image-rendering: pixelated;
		flex-shrink: 0;
	}

	.badge {
		font-size: 0.7rem;
		font-weight: 700;
		background: var(--color-surface-hover);
		border-radius: 0.25rem;
		padding: 0.1em 0.35em;
		flex-shrink: 0;
	}
</style>
