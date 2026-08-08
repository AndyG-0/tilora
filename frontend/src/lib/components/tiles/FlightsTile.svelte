<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { airlineLogoSrc } from '$lib/airlineLogos';
	import { _ } from 'svelte-i18n';

	interface FlightItem {
		callsign: string;
		airline_code: string | null;
		airline_name: string | null;
		aircraft_type: string | null;
		altitude_ft: number | null;
		distance_nm: number | null;
	}

	interface FlightsSummary {
		location_name: string;
		radius_nm: number;
		count: number;
		flights: FlightItem[];
	}

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
</script>

<TileCard {widgetId}>
	{#if summary}
		<div class="header">
			<span class="location">{summary.location_name}</span>
			<span class="count">
				{summary.count > 0 ? $_('flights.tile.count', { values: { count: summary.count } }) : $_('flights.tile.empty')}
			</span>
		</div>
		<ul class="rows">
			{#each summary.flights.slice(0, 3) as flight (flight.callsign)}
				{@const logo = airlineLogoSrc(flight.airline_code)}
				<li class="row">
					{#if logo}
						<img class="logo" src={logo} alt={flight.airline_name ?? flight.airline_code} />
					{:else if flight.airline_code}
						<span class="badge">{flight.airline_code}</span>
					{/if}
					<span class="callsign">{flight.callsign}</span>
					{#if flight.altitude_ft !== null}
						<span class="altitude">{Math.round(flight.altitude_ft).toLocaleString()} ft</span>
					{/if}
				</li>
			{/each}
		</ul>
	{:else}
		<div class="count">{$_('flights.tile.loading')}</div>
	{/if}
</TileCard>

<style>
	.header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.5rem;
		font-size: clamp(0.75rem, 8cqh, 0.9rem);
	}

	.location {
		font-weight: 600;
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
		gap: 0.35rem;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: clamp(0.75rem, 9cqh, 1rem);
	}

	.logo {
		width: clamp(1.25rem, 12cqh, 1.75rem);
		height: auto;
		image-rendering: pixelated;
		flex-shrink: 0;
	}

	.badge {
		font-size: 0.7em;
		font-weight: 700;
		background: var(--color-surface-hover);
		border-radius: 0.25rem;
		padding: 0.1em 0.35em;
		flex-shrink: 0;
	}

	.callsign {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.altitude {
		margin-left: auto;
		color: var(--color-text-muted);
		flex-shrink: 0;
	}
</style>
