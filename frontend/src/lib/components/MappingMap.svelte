<script lang="ts">
	import 'leaflet/dist/leaflet.css';
	import type { Map as LeafletMap, LayerGroup } from 'leaflet';
	import { theme } from '$lib/stores/theme';
	import type { DirectionsResult, NearbyPlace } from '$lib/api';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	const ACCENT_COLOR = '#3388ff';
	// Themes whose --color-bg is dark (see frontend/src/lib/themes/*.css) --
	// standard OSM tiles are light-only, so these get an inverted filter
	// rather than pulling in a second, theme-matched tile provider/API key.
	const DARK_THEMES = new Set(['dark', 'contrast', 'ocean']);

	interface MappingMapData {
		latitude: number;
		longitude: number;
		location_name: string | null;
		route?: DirectionsResult | null;
		nearby?: NearbyPlace[];
		nearbyOrigin?: { latitude: number; longitude: number } | null;
		focusedNearby?: NearbyPlace | null;
	}

	let { data, onGetDirections }: { data: MappingMapData; onGetDirections?: (place: NearbyPlace) => void } = $props();

	type Leaflet = typeof import('leaflet');

	let map: LeafletMap | undefined;
	let homeLayer: LayerGroup | undefined;
	let routeLayer: LayerGroup | undefined;
	let nearbyLayer: LayerGroup | undefined;
	let tilePane: HTMLElement | undefined;

	function homeMarkerHtml(): string {
		return '<span class="home-marker-dot"></span>';
	}

	// Built as a real DOM element (not an HTML string) so place.name/address --
	// which come from OSM tag data anyone can edit -- can't inject markup, and
	// so the "Get directions" button can get a real click listener instead of
	// an inline-HTML one.
	function nearbyPopupContent(place: NearbyPlace): HTMLElement {
		const root = document.createElement('div');
		root.className = 'nearby-popup';

		const name = document.createElement('strong');
		name.textContent = place.name;
		root.appendChild(name);

		if (place.address) {
			const address = document.createElement('div');
			address.textContent = place.address;
			root.appendChild(address);
		}

		if (place.phone) {
			const phone = document.createElement('a');
			phone.href = `tel:${place.phone}`;
			phone.textContent = place.phone;
			root.appendChild(phone);
		}

		if (place.website && /^https?:\/\//i.test(place.website)) {
			const website = document.createElement('a');
			website.href = place.website;
			website.target = '_blank';
			website.rel = 'noopener noreferrer';
			website.textContent = get(_)('mapping.detail.website_link');
			root.appendChild(website);
		}

		if (place.opening_hours) {
			const hours = document.createElement('div');
			hours.className = 'popup-hours';
			hours.textContent = place.opening_hours;
			root.appendChild(hours);
		}

		if (onGetDirections) {
			const directionsBtn = document.createElement('button');
			directionsBtn.type = 'button';
			directionsBtn.className = 'popup-directions-btn';
			directionsBtn.textContent = get(_)('mapping.detail.get_directions');
			directionsBtn.addEventListener('click', (event) => {
				event.stopPropagation();
				onGetDirections(place);
			});
			root.appendChild(directionsBtn);
		}

		return root;
	}

	function applyThemeFilter(themeName: string) {
		if (!tilePane) return;
		tilePane.style.filter = DARK_THEMES.has(themeName)
			? 'invert(1) hue-rotate(180deg) brightness(0.95) contrast(0.9)'
			: 'none';
	}

	function renderLayers(L: Leaflet, current: MappingMapData) {
		if (!map || !homeLayer || !routeLayer || !nearbyLayer) return;
		homeLayer.clearLayers();
		routeLayer.clearLayers();
		nearbyLayer.clearLayers();

		const bounds = L.latLngBounds([[current.latitude, current.longitude]]);

		L.marker([current.latitude, current.longitude], {
			icon: L.divIcon({ className: 'home-marker', html: homeMarkerHtml(), iconSize: [14, 14] }),
		})
			.bindPopup(current.location_name ?? '')
			.addTo(homeLayer);

		if (current.route) {
			const line = L.polyline(current.route.geometry, { color: ACCENT_COLOR, weight: 4 }).addTo(routeLayer);
			bounds.extend(line.getBounds());
		}

		let focusedMarker: ReturnType<Leaflet['marker']> | undefined;

		if (current.nearby) {
			for (const place of current.nearby) {
				const isFocused = current.focusedNearby === place;
				const marker = L.marker([place.latitude, place.longitude], {
					icon: L.divIcon({
						className: 'nearby-marker',
						html: `<span class="nearby-marker-dot${isFocused ? ' nearby-marker-dot-active' : ''}"></span>`,
						iconSize: isFocused ? [18, 18] : [10, 10],
					}),
				})
					.bindPopup(nearbyPopupContent(place))
					.addTo(nearbyLayer);
				bounds.extend([place.latitude, place.longitude]);
				if (isFocused) focusedMarker = marker;
			}
		}

		// A list click focuses a single marker rather than re-fitting the whole
		// view -- fitBounds would zoom back out and undo the point of clicking.
		if (focusedMarker && current.focusedNearby) {
			map.setView([current.focusedNearby.latitude, current.focusedNearby.longitude], Math.max(map.getZoom(), 16));
			focusedMarker.openPopup();
		} else {
			map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
		}
	}

	function attachMap(node: HTMLDivElement) {
		let destroyed = false;
		let unsubscribeTheme: (() => void) | undefined;

		// Leaflet reads `window`/`document` as soon as `L.map(...)` runs, so
		// (same reason FlightsMap.svelte defers it) it's loaded here rather
		// than statically at the top of the file.
		import('leaflet').then((leaflet) => {
			if (destroyed) return;
			const L = leaflet.default;

			map = L.map(node).setView([data.latitude, data.longitude], 13);
			const tileLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
				attribution: '&copy; OpenStreetMap contributors',
				maxZoom: 18,
			}).addTo(map);
			tilePane = tileLayer.getContainer() ?? undefined;

			homeLayer = L.layerGroup().addTo(map);
			routeLayer = L.layerGroup().addTo(map);
			nearbyLayer = L.layerGroup().addTo(map);
			renderLayers(L, data);
			unsubscribeTheme = theme.subscribe((value) => applyThemeFilter(value));
		});

		return {
			destroy() {
				destroyed = true;
				unsubscribeTheme?.();
				map?.remove();
				map = undefined;
				homeLayer = undefined;
				routeLayer = undefined;
				nearbyLayer = undefined;
				tilePane = undefined;
			},
		};
	}

	$effect(() => {
		// Leaflet isn't reactive on its own -- rebuild layers by hand whenever
		// `data` changes (search/directions/nearby results, not a poll timer).
		const current = data;
		if (map && homeLayer && routeLayer && nearbyLayer) {
			import('leaflet').then((leaflet) => renderLayers(leaflet.default, current));
		}
	});
</script>

<div class="map-wrap" role="region" aria-label={$_('mapping.detail.map_label')}>
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

	:global(.home-marker-dot) {
		display: block;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: #3388ff;
		border: 2px solid #fff;
		box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.4);
	}

	:global(.nearby-marker-dot) {
		display: block;
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: #ff8a00;
		border: 2px solid #fff;
		box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.4);
	}

	:global(.nearby-marker-dot-active) {
		width: 18px;
		height: 18px;
		background: #ff2d55;
		border-width: 3px;
		box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.5);
	}

	:global(.leaflet-popup-content) {
		font-size: 0.85rem;
		line-height: 1.4;
	}

	:global(.nearby-popup) {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	:global(.nearby-popup a) {
		color: var(--color-accent, #3388ff);
	}

	:global(.nearby-popup .popup-hours) {
		font-size: 0.8rem;
		opacity: 0.8;
	}

	:global(.popup-directions-btn) {
		margin-top: 0.35rem;
		align-self: flex-start;
		background: var(--color-accent, #3388ff);
		color: #fff;
		border: none;
		border-radius: 0.35rem;
		padding: 0.3rem 0.6rem;
		font: inherit;
		font-size: 0.8rem;
		cursor: pointer;
	}
</style>
