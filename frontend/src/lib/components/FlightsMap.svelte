<script lang="ts">
	import 'leaflet/dist/leaflet.css';
	import type { Map as LeafletMap, LayerGroup } from 'leaflet';
	import { theme } from '$lib/stores/theme';
	import { _ } from 'svelte-i18n';

	interface FlightItem {
		callsign: string;
		aircraft_type: string | null;
		altitude_ft: number | null;
		speed_kts: number | null;
		heading: number | null;
		latitude: number | null;
		longitude: number | null;
	}

	interface FlightsMapData {
		latitude: number;
		longitude: number;
		radius_nm: number;
		flights: FlightItem[];
	}

	let { data }: { data: FlightsMapData } = $props();

	const LED_COLOR = '#ff8a00';
	const NM_TO_METERS = 1852;
	// Themes whose --color-bg is dark (see frontend/src/lib/themes/*.css) —
	// standard OSM tiles are light-only, so these get an inverted filter
	// rather than pulling in a second, theme-matched tile provider/API key.
	const DARK_THEMES = new Set(['dark', 'contrast', 'ocean']);

	type Leaflet = typeof import('leaflet');

	let map: LeafletMap | undefined;
	let markerLayer: LayerGroup | undefined;
	let tilePane: HTMLElement | undefined;

	function aircraftIconHtml(heading: number | null): string {
		const rotation = heading ?? 0;
		return (
			`<svg viewBox="0 0 24 24" width="22" height="22" style="transform: rotate(${rotation}deg)">` +
			`<path d="M12 2 L15 10 L22 14 L22 16 L15 14 L15 19 L18 22 L18 23.5 L12 21.5 L6 23.5 L6 22 L9 19 L9 14 L2 16 L2 14 L9 10 Z" fill="${LED_COLOR}" /></svg>`
		);
	}

	function popupHtml(flight: FlightItem): string {
		const altitude = flight.altitude_ft !== null ? `${Math.round(flight.altitude_ft).toLocaleString()} ft` : '—';
		const speed = flight.speed_kts !== null ? `${Math.round(flight.speed_kts)} kts` : '—';
		return `<strong>${flight.callsign}</strong><br>${flight.aircraft_type ?? '—'}<br>${altitude} &middot; ${speed}`;
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
			L.marker([flight.latitude, flight.longitude], {
				icon: L.divIcon({
					className: 'aircraft-marker',
					html: aircraftIconHtml(flight.heading),
					iconSize: [22, 22],
					iconAnchor: [11, 11],
				}),
			})
				.bindPopup(popupHtml(flight))
				.addTo(markerLayer);
			bounds.extend([flight.latitude, flight.longitude]);
		}

		map.fitBounds(bounds, { padding: [30, 30], maxZoom: 12 });
	}

	function attachMap(node: HTMLDivElement) {
		let destroyed = false;
		let unsubscribeTheme: (() => void) | undefined;

		// Leaflet reads `window`/`document` as soon as `L.map(...)` runs, so
		// (same reason mpegts.js is dynamically imported in
		// HDHomeRunPlayer.svelte) it's loaded here rather than statically at
		// the top of the file.
		import('leaflet').then((leaflet) => {
			if (destroyed) return;
			const L = leaflet.default;

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
			},
		};
	}

	$effect(() => {
		// Leaflet isn't reactive on its own -- rebuild markers/bounds by hand
		// whenever `data` changes (only happens on deliberate location/radius
		// edits here, not on a timer, so refitting bounds each time is fine).
		const current = data;
		if (map && markerLayer) {
			import('leaflet').then((leaflet) => renderMarkers(leaflet.default, current));
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
		height: 320px;
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

	:global(.leaflet-popup-content) {
		font-size: 0.85rem;
		line-height: 1.4;
	}
</style>
