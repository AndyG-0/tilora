<script lang="ts">
	import 'leaflet/dist/leaflet.css';
	import type { Map as LeafletMap, LayerGroup, Marker as LeafletMarker } from 'leaflet';
	import { theme } from '$lib/stores/theme';
	import { airlineLogoSrc } from '$lib/airlineLogos';
	import { lookupAircraftName, formatSpeedTooltip } from '$lib/aircraftTypes';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	interface AirportRef {
		iata: string | null;
		icao: string;
		city: string | null;
	}

	interface FlightItem {
		callsign: string;
		airline_code?: string | null;
		airline_name?: string | null;
		aircraft_type: string | null;
		aircraft_name?: string | null;
		aircraft_kind?: string | null;
		registration?: string | null;
		altitude_ft: number | null;
		speed_kts: number | null;
		distance_nm?: number | null;
		heading: number | null;
		latitude: number | null;
		longitude: number | null;
		origin?: AirportRef | null;
		destination?: AirportRef | null;
		photo_thumbnail_url?: string | null;
		photo_url?: string | null;
		photo_photographer?: string | null;
		photo_link?: string | null;
	}

	interface FlightsMapData {
		latitude: number;
		longitude: number;
		radius_nm: number;
		speed_unit?: 'mph' | 'kmh';
		flights: FlightItem[];
	}

	let {
		data,
		selectedCallsign = null,
		onselectflight,
	}: {
		data: FlightsMapData;
		selectedCallsign?: string | null;
		onselectflight?: (callsign: string | null) => void;
	} = $props();

	const LED_COLOR = '#ff8a00';
	const NM_TO_METERS = 1852;
	const DARK_THEMES = new Set(['dark', 'contrast', 'ocean']);

	type Leaflet = typeof import('leaflet');

	let map: LeafletMap | undefined;
	let markerLayer: LayerGroup | undefined;
	let tilePane: HTMLElement | undefined;
	let markersByCallsign = new Map<string, LeafletMarker>();
	let leafletInstance: Leaflet | undefined;

	function headingDirection(deg: number | null): string {
		if (deg === null || deg === undefined) return '—';
		const directions = [
			'N',
			'NNE',
			'NE',
			'ENE',
			'E',
			'ESE',
			'SE',
			'SSE',
			'S',
			'SSW',
			'SW',
			'WSW',
			'W',
			'WNW',
			'NW',
			'NNW',
		];
		const idx = Math.round(deg / 22.5) % 16;
		return `${Math.round(deg)}° ${directions[idx]}`;
	}

	function airportLabel(airport: AirportRef): string {
		const code = airport.iata ?? airport.icao;
		return airport.city ? `${code} (${airport.city})` : code;
	}

	function aircraftIconHtml(heading: number | null, isSelected: boolean): string {
		const rotation = heading ?? 0;
		const pulseRings = isSelected ? '<span class="selected-halo"></span><span class="pulse-ring"></span>' : '';
		const size = isSelected ? 24 : 20;
		return (
			`<div class="marker-container${isSelected ? ' is-selected' : ''}">` +
			pulseRings +
			`<svg class="plane-svg" viewBox="0 0 24 24" width="${size}" height="${size}" style="transform: rotate(${rotation}deg)">` +
			`<path d="M12 2 L15 10 L22 14 L22 16 L15 14 L15 19 L18 22 L18 23.5 L12 21.5 L6 23.5 L6 22 L9 19 L9 14 L2 16 L2 14 L9 10 Z" fill="${LED_COLOR}" stroke="${isSelected ? '#fff' : 'none'}" stroke-width="${isSelected ? '1' : '0'}" /></svg>` +
			`</div>`
		);
	}

	function popupHtml(flight: FlightItem, speedUnit: 'mph' | 'kmh' = 'mph'): string {
		const t = get(_);
		const altitude = flight.altitude_ft !== null ? `${Math.round(flight.altitude_ft).toLocaleString()} FT` : '—';
		const speedConverted = formatSpeedTooltip(flight.speed_kts, speedUnit);
		const speed =
			flight.speed_kts !== null
				? `${Math.round(flight.speed_kts)} KTS${speedConverted ? ` (${speedConverted})` : ''}`
				: '—';
		const heading = headingDirection(flight.heading);
		const distance =
			flight.distance_nm !== null && flight.distance_nm !== undefined ? `${flight.distance_nm.toFixed(1)} NM` : '—';
		const modelName = flight.aircraft_name ?? lookupAircraftName(flight.aircraft_type) ?? flight.aircraft_type ?? '—';

		const logo = airlineLogoSrc(flight.airline_code ?? null);
		const logoHtml = logo
			? `<img class="popup-airline-logo" src="${logo}" alt="${flight.airline_name ?? flight.airline_code ?? ''}" />`
			: flight.airline_code
				? `<span class="popup-airline-badge">${flight.airline_code}</span>`
				: '';

		const photoSection = flight.photo_thumbnail_url
			? `
				<div class="popup-photo-wrap">
					<img class="popup-photo" src="${flight.photo_thumbnail_url}" alt="${flight.callsign}" />
					${flight.photo_photographer ? `<span class="popup-photo-credit">&copy; ${flight.photo_photographer}</span>` : ''}
				</div>
			`
			: '';

		let routeHtml = '';
		if (flight.origin && flight.destination) {
			routeHtml = `
				<div class="popup-route">
					<span class="route-point">${airportLabel(flight.origin)}</span>
					<span class="route-arrow">➔</span>
					<span class="route-point">${airportLabel(flight.destination)}</span>
				</div>
			`;
		}

		return `
			<div class="flight-popup-card">
				${photoSection}
				<div class="popup-body">
					<div class="popup-header">
						<div class="popup-title">
							${logoHtml}
							<strong class="popup-callsign">${flight.callsign}</strong>
						</div>
						${flight.registration ? `<span class="popup-tail">Tail: ${flight.registration}</span>` : ''}
					</div>

					${flight.airline_name ? `<div class="popup-airline-name">${flight.airline_name}</div>` : ''}

					${routeHtml}

					<div class="popup-grid">
						<div class="grid-item full-width">
							<span class="item-label">${t('flights.detail.column_type')}</span>
							<span class="item-value" title="${modelName}">${modelName}</span>
						</div>
						<div class="grid-item">
							<span class="item-label">${t('flights.detail.column_altitude')}</span>
							<span class="item-value">${altitude}</span>
						</div>
						<div class="grid-item">
							<span class="item-label">${t('flights.detail.column_speed')}</span>
							<span class="item-value">${speed}</span>
						</div>
						<div class="grid-item">
							<span class="item-label">Heading</span>
							<span class="item-value">${heading}</span>
						</div>
						<div class="grid-item">
							<span class="item-label">${t('flights.detail.column_distance')}</span>
							<span class="item-value">${distance}</span>
						</div>
					</div>
				</div>
			</div>
		`;
	}

	function applyThemeFilter(themeName: string) {
		if (!tilePane) return;
		tilePane.style.filter = DARK_THEMES.has(themeName)
			? 'invert(1) hue-rotate(180deg) brightness(0.95) contrast(0.9)'
			: 'none';
	}

	function renderMarkers(L: Leaflet, current: FlightsMapData) {
		if (!map || !markerLayer) return;
		markerLayer.clearLayers();
		markersByCallsign.clear();

		const bounds = L.latLngBounds([[current.latitude, current.longitude]]);

		L.marker([current.latitude, current.longitude], {
			icon: L.divIcon({ className: 'home-marker', html: '<span></span>', iconSize: [12, 12] }),
		}).addTo(markerLayer);

		L.circle([current.latitude, current.longitude], {
			radius: current.radius_nm * NM_TO_METERS,
			color: LED_COLOR,
			weight: 1,
			fillOpacity: 0.05,
		}).addTo(markerLayer);

		for (const flight of current.flights) {
			if (flight.latitude === null || flight.longitude === null) continue;
			const isSelected = flight.callsign === selectedCallsign;
			const marker = L.marker([flight.latitude, flight.longitude], {
				icon: L.divIcon({
					className: `aircraft-marker-wrap${isSelected ? ' is-selected' : ''}`,
					html: aircraftIconHtml(flight.heading, isSelected),
					iconSize: [28, 28],
					iconAnchor: [14, 14],
					// Offset popup anchor so it floats cleanly above the plane icon without obscuring it
					popupAnchor: [0, -18],
				}),
				zIndexOffset: isSelected ? 10000 : 0,
			});

			marker.bindPopup(popupHtml(flight, current.speed_unit), {
				className: 'flight-leaflet-popup',
				maxWidth: 240,
				minWidth: 220,
				autoPan: true,
				autoPanPadding: L.point(20, 20),
			});

			marker.on('click', () => {
				onselectflight?.(flight.callsign);
			});

			marker.addTo(markerLayer);
			markersByCallsign.set(flight.callsign, marker);
			bounds.extend([flight.latitude, flight.longitude]);
		}

		map.fitBounds(bounds, { padding: [30, 30], maxZoom: 12 });
	}

	function attachMap(node: HTMLDivElement) {
		let destroyed = false;
		let unsubscribeTheme: (() => void) | undefined;

		import('leaflet').then((leaflet) => {
			if (destroyed) return;
			const L = leaflet.default;
			leafletInstance = L;

			map = L.map(node).setView([data.latitude, data.longitude], 11);
			const tileLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
				attribution: '&copy; OpenStreetMap contributors',
				maxZoom: 18,
			}).addTo(map);
			tilePane = tileLayer.getContainer() ?? undefined;

			markerLayer = L.layerGroup().addTo(map);
			renderMarkers(L, data);
			unsubscribeTheme = theme.subscribe((value) => applyThemeFilter(value));
		});

		return {
			destroy() {
				destroyed = true;
				unsubscribeTheme?.();
				map?.remove();
				map = undefined;
				markerLayer = undefined;
				tilePane = undefined;
				markersByCallsign.clear();
			},
		};
	}

	$effect(() => {
		const current = data;
		if (map && markerLayer && leafletInstance) {
			renderMarkers(leafletInstance, current);
		}
	});

	$effect(() => {
		// React to external selectedCallsign updates (e.g. row clicks in table)
		const targetCallsign = selectedCallsign;
		if (map && targetCallsign && markersByCallsign.has(targetCallsign)) {
			const marker = markersByCallsign.get(targetCallsign);
			if (marker) {
				const pos = marker.getLatLng();
				map.panTo(pos, { animate: true, duration: 0.4 });
				marker.openPopup();
			}
		}
	});
</script>

<div class="map-wrap" role="region" aria-label={$_('flights.detail.map_label')}>
	<div class="map" use:attachMap></div>
</div>

<style>
	.map-wrap {
		margin: 1rem 0;
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		overflow: hidden;
		height: 380px;
	}

	.map {
		height: 100%;
		width: 100%;
	}

	:global(.home-marker span) {
		display: block;
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: #ff8a00;
		border: 2px solid #fff;
		box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.4);
	}

	:global(.aircraft-marker-wrap) {
		background: none;
		border: none;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	:global(.marker-container) {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		cursor: pointer;
		filter: drop-shadow(0 1px 3px rgba(0, 0, 0, 0.6));
		transition: transform 0.2s ease;
	}

	:global(.marker-container .plane-svg) {
		position: relative;
		z-index: 2;
		filter: drop-shadow(0 0 2px rgba(0, 0, 0, 0.8));
	}

	:global(.marker-container.is-selected) {
		z-index: 10000;
	}

	:global(.marker-container.is-selected .plane-svg) {
		filter: drop-shadow(0 0 6px #ff8a00) drop-shadow(0 0 2px #ffffff);
	}

	:global(.marker-container .selected-halo) {
		position: absolute;
		width: 28px;
		height: 28px;
		border-radius: 50%;
		background: rgba(255, 138, 0, 0.25);
		border: 2px solid #ff8a00;
		box-shadow: 0 0 10px #ff8a00;
		z-index: 1;
	}

	:global(.marker-container .pulse-ring) {
		position: absolute;
		width: 28px;
		height: 28px;
		border-radius: 50%;
		border: 2px solid #ff8a00;
		box-shadow: 0 0 8px #ff8a00;
		animation: markerPulse 1.8s infinite ease-out;
		pointer-events: none;
		z-index: 0;
	}

	@keyframes markerPulse {
		0% {
			transform: scale(0.8);
			opacity: 1;
		}
		100% {
			transform: scale(2.2);
			opacity: 0;
		}
	}

	:global(.flight-leaflet-popup .leaflet-popup-content-wrapper) {
		padding: 0;
		border-radius: 0.65rem;
		background: #111111;
		color: #ffffff;
		border: 1px solid rgba(255, 138, 0, 0.4);
		box-shadow: 0 6px 24px rgba(0, 0, 0, 0.7);
		overflow: hidden;
	}

	:global(.flight-leaflet-popup .leaflet-popup-content) {
		margin: 0;
		line-height: 1.3;
		width: 230px !important;
	}

	:global(.flight-leaflet-popup .leaflet-popup-tip) {
		background: #111111;
		border: 1px solid rgba(255, 138, 0, 0.4);
		box-shadow: none;
	}

	:global(.flight-popup-card) {
		display: flex;
		flex-direction: column;
		width: 100%;
		font-family: inherit;
	}

	:global(.popup-photo-wrap) {
		position: relative;
		width: 100%;
		height: 72px;
		background: #1a1a1a;
		overflow: hidden;
		display: flex;
		align-items: center;
		justify-content: center;
		border-bottom: 1px solid rgba(255, 255, 255, 0.08);
	}

	:global(.popup-photo) {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}

	:global(.popup-photo-credit) {
		position: absolute;
		bottom: 0.2rem;
		right: 0.3rem;
		background: rgba(0, 0, 0, 0.75);
		color: rgba(255, 255, 255, 0.8);
		font-size: 0.55rem;
		padding: 0.05rem 0.3rem;
		border-radius: 0.2rem;
	}

	:global(.popup-body) {
		padding: 0.55rem 0.65rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	:global(.popup-header) {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.4rem;
	}

	:global(.popup-title) {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		min-width: 0;
	}

	:global(.popup-airline-logo) {
		width: 1.35rem;
		height: auto;
		image-rendering: pixelated;
		flex-shrink: 0;
	}

	:global(.popup-airline-badge) {
		font-size: 0.65rem;
		font-weight: 700;
		background: #262626;
		color: #ff8a00;
		padding: 0.05rem 0.3rem;
		border-radius: 0.2rem;
		flex-shrink: 0;
	}

	:global(.popup-callsign) {
		font-size: 0.95rem;
		font-weight: 700;
		color: #ff8a00;
		letter-spacing: 0.02em;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	:global(.popup-tail) {
		font-size: 0.7rem;
		color: rgba(255, 255, 255, 0.6);
		flex-shrink: 0;
	}

	:global(.popup-airline-name) {
		font-size: 0.72rem;
		color: rgba(255, 255, 255, 0.75);
		margin-top: -0.2rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	:global(.popup-route) {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		background: rgba(255, 255, 255, 0.06);
		padding: 0.25rem 0.4rem;
		border-radius: 0.35rem;
		font-size: 0.72rem;
		font-weight: 500;
		color: #ffffff;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	:global(.route-point) {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	:global(.route-arrow) {
		color: #ff8a00;
		font-size: 0.75rem;
		flex-shrink: 0;
	}

	:global(.popup-grid) {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.25rem 0.4rem;
		margin-top: 0.1rem;
		padding-top: 0.3rem;
		border-top: 1px solid rgba(255, 255, 255, 0.08);
	}

	:global(.grid-item) {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	:global(.grid-item.full-width) {
		grid-column: 1 / -1;
	}

	:global(.item-label) {
		font-size: 0.6rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: rgba(255, 255, 255, 0.5);
	}

	:global(.item-value) {
		font-size: 0.72rem;
		font-weight: 600;
		color: #ffffff;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
