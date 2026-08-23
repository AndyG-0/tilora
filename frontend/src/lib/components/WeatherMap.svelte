<script lang="ts">
	import 'leaflet/dist/leaflet.css';
	import type { Map as LeafletMap, TileLayer } from 'leaflet';
	import { theme } from '$lib/stores/theme';
	import { _ } from 'svelte-i18n';

	const RAINVIEWER_URL = 'https://api.rainviewer.com/public/weather-maps.json';
	const RADAR_COLOR = 2; // Universal Blue scheme
	const RADAR_OPTIONS = '1_1'; // smooth_1, snow_1
	const RADAR_TILE_SIZE = 256;
	const RADAR_OVERLAY_OPACITY = 0.65;
	const FRAME_INTERVAL_MS = 700;
	const PRELOAD_STAGGER_MS = 250;
	// RainViewer's 256px radar tiles only render real imagery up to zoom 7 --
	// past that it serves a baked-in "Zoom Level Not Supported" placeholder
	// image instead of a 404 (confirmed empirically; not documented). Capping
	// maxNativeZoom makes Leaflet upscale the z=7 tiles for deeper zooms
	// instead of fetching the placeholder, and the initial view is kept at
	// that same zoom so the overlay isn't broken from first load either.
	const RADAR_MAX_NATIVE_ZOOM = 7;
	const INITIAL_ZOOM = 7;
	// Themes whose --color-bg is dark (see frontend/src/lib/themes/*.css) --
	// standard OSM tiles are light-only, so these get an inverted filter
	// rather than pulling in a second, theme-matched tile provider/API key.
	// Same treatment as MappingMap.svelte/FlightsMap.svelte.
	const DARK_THEMES = new Set(['dark', 'contrast', 'ocean']);

	interface RainViewerFrame {
		time: number;
		path: string;
	}

	interface RainViewerResponse {
		host: string;
		radar: { past: RainViewerFrame[]; nowcast: RainViewerFrame[] };
	}

	let { latitude, longitude }: { latitude: number; longitude: number } = $props();

	type Leaflet = typeof import('leaflet');

	let map: LeafletMap | undefined;
	let leaflet: Leaflet | undefined;
	let baseTileLayer: TileLayer | undefined;
	let tilePane: HTMLElement | undefined;
	let host = '';
	let frames: RainViewerFrame[] = [];
	// Lazily-created, kept-around tile layer per frame -- switching frames
	// crossfades between cached layers instead of re-pointing one shared
	// layer at a new URL, so a frame already seen this session doesn't
	// re-hit the network (or blink) the next time it's shown.
	let radarLayers: (TileLayer | undefined)[] = [];
	let frameIndex = $state(0);
	let playing = $state(false);
	let hasFrames = $state(false);
	let playTimer: ReturnType<typeof setInterval> | undefined;
	let preloadTimer: ReturnType<typeof setTimeout> | undefined;

	function tileUrlFor(frame: RainViewerFrame): string {
		return `${host}${frame.path}/${RADAR_TILE_SIZE}/{z}/{x}/{y}/${RADAR_COLOR}/${RADAR_OPTIONS}.png`;
	}

	function currentFrameLabel(): string {
		if (!hasFrames) return '';
		return new Date(frames[frameIndex].time * 1000).toLocaleTimeString([], {
			hour: 'numeric',
			minute: '2-digit',
		});
	}

	function getOrCreateLayer(index: number): TileLayer | undefined {
		if (!map || !leaflet) return undefined;
		let layer = radarLayers[index];
		if (!layer) {
			layer = leaflet
				.tileLayer(tileUrlFor(frames[index]), {
					opacity: 0,
					zIndex: 500,
					maxNativeZoom: RADAR_MAX_NATIVE_ZOOM,
				})
				.addTo(map);
			radarLayers[index] = layer;
		}
		return layer;
	}

	function showFrame(index: number) {
		if (!hasFrames) return;
		const previous = radarLayers[frameIndex];
		frameIndex = index;
		const next = getOrCreateLayer(index);
		next?.setOpacity(RADAR_OVERLAY_OPACITY);
		if (previous && previous !== next) previous.setOpacity(0);
	}

	function play() {
		if (!hasFrames || playing) return;
		playing = true;
		playTimer = setInterval(() => {
			showFrame((frameIndex + 1) % frames.length);
		}, FRAME_INTERVAL_MS);
	}

	function pause() {
		playing = false;
		if (playTimer) clearInterval(playTimer);
		playTimer = undefined;
	}

	function stepForward() {
		pause();
		if (!hasFrames) return;
		showFrame((frameIndex + 1) % frames.length);
	}

	function stepBack() {
		pause();
		if (!hasFrames) return;
		showFrame((frameIndex - 1 + frames.length) % frames.length);
	}

	// Warms the tile layer cache (and the browser's HTTP cache -- RainViewer
	// tiles are served with a 48h max-age) for every frame not on screen
	// yet, one at a time, so replaying the loop doesn't need to fetch
	// anything. Staggered rather than fired all at once: RainViewer
	// rate-limits bursts of requests (empirically confirmed via 429s).
	function preloadRemainingFrames(order: number[]) {
		if (order.length === 0) return;
		const [next, ...rest] = order;
		preloadTimer = setTimeout(() => {
			getOrCreateLayer(next);
			preloadRemainingFrames(rest);
		}, PRELOAD_STAGGER_MS);
	}

	async function loadRadarFrames() {
		try {
			const res = await fetch(RAINVIEWER_URL);
			if (!res.ok) throw new Error(`RainViewer ${res.status}`);
			const json: RainViewerResponse = await res.json();
			const past = json.radar?.past ?? [];
			if (past.length === 0) return;
			if (!map || !leaflet) return;

			host = json.host;
			frames = past;
			frameIndex = frames.length - 1;
			radarLayers = new Array(frames.length);
			hasFrames = true;

			getOrCreateLayer(frameIndex)?.setOpacity(RADAR_OVERLAY_OPACITY);

			const otherFrameIndexes = frames.map((_, i) => i).filter((i) => i !== frameIndex);
			preloadRemainingFrames(otherFrameIndexes);
		} catch {
			// Supplementary feature, not core weather data -- fall back to the
			// bare OSM map with no radar overlay/controls rather than erroring.
		}
	}

	function applyThemeFilter(themeName: string) {
		if (!tilePane) return;
		tilePane.style.filter = DARK_THEMES.has(themeName)
			? 'invert(1) hue-rotate(180deg) brightness(0.95) contrast(0.9)'
			: 'none';
	}

	function attachMap(node: HTMLDivElement) {
		let destroyed = false;
		let unsubscribeTheme: (() => void) | undefined;

		// Leaflet reads `window`/`document` as soon as `L.map(...)` runs, so
		// (same reason MappingMap.svelte/FlightsMap.svelte defer it) it's
		// loaded here rather than statically at the top of the file.
		import('leaflet').then(async (mod) => {
			if (destroyed) return;
			leaflet = mod.default;

			map = leaflet.map(node).setView([latitude, longitude], INITIAL_ZOOM);
			baseTileLayer = leaflet
				.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
					attribution: '&copy; OpenStreetMap contributors | Radar &copy; RainViewer.com',
					maxZoom: 18,
				})
				.addTo(map);
			tilePane = baseTileLayer.getContainer() ?? undefined;
			unsubscribeTheme = theme.subscribe((value) => applyThemeFilter(value));

			await loadRadarFrames();
		});

		return {
			destroy() {
				destroyed = true;
				pause();
				if (preloadTimer) clearTimeout(preloadTimer);
				unsubscribeTheme?.();
				map?.remove();
				map = undefined;
				leaflet = undefined;
				baseTileLayer = undefined;
				radarLayers = [];
				tilePane = undefined;
			},
		};
	}

	$effect(() => {
		const lat = latitude;
		const lon = longitude;
		map?.setView([lat, lon], map.getZoom());
	});
</script>

<div class="map-wrap" role="region" aria-label={$_('weather.detail.radar_map_label')}>
	<div class="map" use:attachMap></div>
	{#if hasFrames}
		<div class="radar-controls">
			<button type="button" onclick={stepBack} aria-label={$_('weather.detail.radar_step_back')}>⏮</button>
			{#if playing}
				<button type="button" onclick={pause} aria-label={$_('weather.detail.radar_pause')}>⏸</button>
			{:else}
				<button type="button" onclick={play} aria-label={$_('weather.detail.radar_play')}>▶</button>
			{/if}
			<button type="button" onclick={stepForward} aria-label={$_('weather.detail.radar_step_forward')}>⏭</button>
			<span class="radar-time">{currentFrameLabel()}</span>
		</div>
	{/if}
</div>

<style>
	.map-wrap {
		position: relative;
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

	/* Crossfade radar tiles between frames instead of popping opacity --
	   the layer swap in showFrame() already avoids a network-bound blink,
	   this just smooths the visual transition on top of that. */
	.map-wrap :global(.leaflet-tile) {
		transition: opacity 200ms linear;
	}

	.radar-controls {
		position: absolute;
		left: 0.5rem;
		bottom: 0.5rem;
		z-index: 1000;
		display: flex;
		align-items: center;
		gap: 0.4rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.3rem 0.6rem;
	}

	.radar-controls button {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.4rem;
		padding: 0.2rem 0.5rem;
		color: var(--color-accent);
		cursor: pointer;
		font-size: 0.9rem;
		line-height: 1;
	}

	.radar-time {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		white-space: nowrap;
	}
</style>
