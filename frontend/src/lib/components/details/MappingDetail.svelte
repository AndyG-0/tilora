<script lang="ts">
	import { page } from '$app/state';
	import { api, ApiError, type DirectionsResult, type MapSearchResult, type NearbyPlace } from '$lib/api';
	import MappingMap from '$lib/components/MappingMap.svelte';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	interface MappingDetailData {
		location_name: string | null;
		latitude: number | null;
		longitude: number | null;
	}

	// Mirrors app.integrations.overpass_client.CATEGORY_TAGS -- the fixed
	// category vocabulary shared with the AI tool's enum and the REST
	// endpoint's validation.
	const CATEGORIES = [
		'restaurant',
		'cafe',
		'bar',
		'grocery',
		'gas_station',
		'pharmacy',
		'hospital',
		'atm_bank',
		'hotel',
		'attraction',
		'park',
	] as const;

	const TRAVEL_MODES = ['driving', 'walking', 'cycling'] as const;

	let { data: initialData }: { data: MappingDetailData } = $props();

	const DEFAULT_LOCATION: MappingDetailData = {
		location_name: 'Fort Worth, TX',
		latitude: 32.7555,
		longitude: -97.3308,
	};

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from selectHomeLocation.
	let home = $state(initialData);

	let panel = $state<'home' | 'search' | 'directions' | 'nearby'>(
		(page.url.searchParams.get('panel') as 'directions' | 'nearby' | null) ?? 'home',
	);

	// Home-location editor
	let editingHome = $state(false);
	let homeQuery = $state('');
	let homeResults = $state<MapSearchResult[]>([]);
	let homeSearching = $state(false);
	let savingHome = $state(false);
	let homeError = $state<string | null>(null);
	let homeSearchTimeout: ReturnType<typeof setTimeout>;

	// General search
	let searchQuery = $state('');
	let searchResults = $state<MapSearchResult[]>([]);
	let searching = $state(false);
	let searchError = $state<string | null>(null);
	let selectedPlace = $state<MapSearchResult | null>(null);
	let searchTimeout: ReturnType<typeof setTimeout>;

	// Directions -- destination/origin may arrive pre-filled from the AI
	// assistant's show_mapping_detail navigation tool (see MappingPlugin).
	let destinationInput = $state(page.url.searchParams.get('destination') ?? '');
	let originInput = $state(page.url.searchParams.get('origin') ?? '');
	let mode = $state<(typeof TRAVEL_MODES)[number]>('driving');
	let directionsLoading = $state(false);
	let directionsError = $state<string | null>(null);
	let directions = $state<DirectionsResult | null>(null);

	// Nearby
	const METERS_PER_MILE = 1609.344;
	let selectedCategory = $state<(typeof CATEGORIES)[number]>('restaurant');
	let radiusUnit = $state<'mi' | 'm'>('mi');
	let radiusInput = $state(25); // in radiusUnit's units
	const radiusM = $derived(radiusUnit === 'mi' ? Math.round(radiusInput * METERS_PER_MILE) : Math.round(radiusInput));

	// Converts the displayed number so the effective search radius stays put
	// when switching units, rather than silently keeping "25" and turning a
	// 25-mile search into a 25-meter one.
	function setRadiusUnit(unit: 'mi' | 'm') {
		if (unit === radiusUnit) return;
		radiusInput = unit === 'mi' ? Math.round((radiusM / METERS_PER_MILE) * 10) / 10 : Math.round(radiusM);
		radiusUnit = unit;
	}

	let nearbyLoading = $state(false);
	let nearbyError = $state<string | null>(null);
	let nearbyPlaces = $state<NearbyPlace[]>([]);
	let selectedNearbyPlace = $state<NearbyPlace | null>(null);

	// A 5xx means the downstream provider (Nominatim/OSRM/Overpass) itself is
	// down, not that the query had no matches -- worth a distinct message so
	// users don't read "no results" and assume they mistyped something.
	function isServiceUnavailable(err: unknown): boolean {
		return err instanceof ApiError && err.status >= 500;
	}

	function onHomeQueryInput() {
		clearTimeout(homeSearchTimeout);
		const trimmed = homeQuery.trim();
		if (trimmed.length < 2) {
			homeResults = [];
			homeSearching = false;
			return;
		}
		homeSearching = true;
		homeSearchTimeout = setTimeout(async () => {
			try {
				homeResults = await api.mappingSearch(trimmed);
				homeError = null;
			} catch (err) {
				homeError = isServiceUnavailable(err)
					? get(_)('mapping.detail.service_unavailable')
					: get(_)('mapping.detail.search_failed');
			} finally {
				homeSearching = false;
			}
		}, 300);
	}

	async function selectHomeLocation(place: MapSearchResult) {
		savingHome = true;
		homeError = null;
		try {
			await api.updateWidgetSettings(page.params.id!, {
				latitude: place.latitude,
				longitude: place.longitude,
				location_name: place.name,
			});
			home = { location_name: place.name, latitude: place.latitude, longitude: place.longitude };
			editingHome = false;
			homeQuery = '';
			homeResults = [];
		} catch {
			homeError = get(_)('mapping.detail.update_failed');
		} finally {
			savingHome = false;
		}
	}

	function onSearchQueryInput() {
		clearTimeout(searchTimeout);
		const trimmed = searchQuery.trim();
		if (trimmed.length < 2) {
			searchResults = [];
			searching = false;
			return;
		}
		searching = true;
		searchTimeout = setTimeout(async () => {
			try {
				searchResults = await api.mappingSearch(trimmed);
				searchError = null;
			} catch (err) {
				searchError = isServiceUnavailable(err)
					? get(_)('mapping.detail.service_unavailable')
					: get(_)('mapping.detail.search_failed');
			} finally {
				searching = false;
			}
		}, 300);
	}

	function selectSearchResult(place: MapSearchResult) {
		selectedPlace = place;
	}

	// `destinationOverride` carries exact coordinates from a nearby-place
	// popup click, so the destination skips Nominatim geocoding entirely
	// (re-geocoding by name risks landing on a different, same-named place).
	async function getDirections(destinationOverride?: NearbyPlace) {
		const destination = destinationOverride?.name ?? destinationInput.trim();
		if (!destination) return;
		const origin = originInput.trim() || home.location_name || '';
		if (!origin) {
			directionsError = get(_)('mapping.detail.no_home_location');
			return;
		}
		directionsLoading = true;
		directionsError = null;
		const useHomeCoords = !originInput.trim() && home.latitude !== null && home.longitude !== null;
		try {
			directions = await api.mappingDirections(destination, origin, mode, {
				destinationLat: destinationOverride?.latitude,
				destinationLon: destinationOverride?.longitude,
				originLat: useHomeCoords ? (home.latitude ?? undefined) : undefined,
				originLon: useHomeCoords ? (home.longitude ?? undefined) : undefined,
			});
		} catch (err) {
			directionsError = isServiceUnavailable(err)
				? get(_)('mapping.detail.service_unavailable')
				: get(_)('mapping.detail.directions_failed');
			directions = null;
		} finally {
			directionsLoading = false;
		}
	}

	// Fetch immediately if the directions panel was opened with a destination
	// already filled in (see destinationInput's initializer above) -- runs
	// once at mount, not on every panel switch.
	if (panel === 'directions' && destinationInput) {
		void getDirections();
	}

	function getDirectionsToPlace(place: NearbyPlace) {
		panel = 'directions';
		destinationInput = place.name;
		originInput = '';
		void getDirections(place);
	}

	async function findNearby() {
		if (home.latitude === null || home.longitude === null) {
			nearbyError = get(_)('mapping.detail.no_home_location');
			return;
		}
		nearbyLoading = true;
		nearbyError = null;
		selectedNearbyPlace = null;
		try {
			nearbyPlaces = await api.mappingNearby(home.latitude, home.longitude, selectedCategory, radiusM);
		} catch (err) {
			nearbyError = isServiceUnavailable(err)
				? get(_)('mapping.detail.service_unavailable')
				: get(_)('mapping.detail.nearby_failed');
			nearbyPlaces = [];
		} finally {
			nearbyLoading = false;
		}
	}

	function selectNearbyPlace(place: NearbyPlace) {
		selectedNearbyPlace = selectedNearbyPlace === place ? null : place;
	}

	const effectiveHome = $derived(
		home.latitude !== null && home.longitude !== null
			? { latitude: home.latitude, longitude: home.longitude, location_name: home.location_name }
			: DEFAULT_LOCATION,
	);

	const mapData = $derived({
		latitude: selectedPlace?.latitude ?? effectiveHome.latitude!,
		longitude: selectedPlace?.longitude ?? effectiveHome.longitude!,
		location_name: selectedPlace?.name ?? effectiveHome.location_name,
		route: panel === 'directions' ? directions : null,
		nearby: panel === 'nearby' ? nearbyPlaces : [],
		focusedNearby: panel === 'nearby' ? selectedNearbyPlace : null,
	});

	// Re-fetch (debounced, so typing a radius doesn't spam Overpass) whenever
	// the nearby tab is active and its inputs change, including the very
	// first time it's opened -- the category chips already show a selection,
	// so opening the tab should reflect it rather than showing a stale
	// "no results" hint.
	$effect(() => {
		if (panel !== 'nearby') return;
		void selectedCategory;
		void radiusM;
		void home.latitude;
		void home.longitude;
		const timeout = setTimeout(() => findNearby(), 300);
		return () => clearTimeout(timeout);
	});
</script>

<div class="header">
	<h1>{home.location_name ?? $_('mapping.detail.no_location')}</h1>
	<button class="change-location" onclick={() => (editingHome = !editingHome)}>
		{editingHome ? $_('mapping.detail.cancel') : $_('mapping.detail.change_home')}
	</button>
</div>

{#if editingHome}
	<div class="location-search">
		<input
			type="text"
			placeholder={$_('mapping.detail.search_placeholder')}
			bind:value={homeQuery}
			oninput={onHomeQueryInput}
		/>
		{#if homeSearching}
			<p class="hint">{$_('mapping.detail.searching')}</p>
		{:else if homeError}
			<p class="hint error">{homeError}</p>
		{:else if homeQuery.trim().length >= 2 && homeResults.length === 0}
			<p class="hint">{$_('mapping.detail.no_results')}</p>
		{/if}
		{#if homeResults.length > 0}
			<ul class="results">
				{#each homeResults as place (place.latitude + ',' + place.longitude)}
					<li>
						<button disabled={savingHome} onclick={() => selectHomeLocation(place)}>
							{place.display_name}
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
{/if}

<MappingMap data={mapData} onGetDirections={getDirectionsToPlace} />

<div class="tabs" role="tablist">
	<button
		role="tab"
		aria-selected={panel === 'search'}
		class:active={panel === 'search'}
		onclick={() => (panel = 'search')}
	>
		{$_('mapping.detail.tab_search')}
	</button>
	<button
		role="tab"
		aria-selected={panel === 'directions'}
		class:active={panel === 'directions'}
		onclick={() => (panel = 'directions')}
	>
		{$_('mapping.detail.tab_directions')}
	</button>
	<button
		role="tab"
		aria-selected={panel === 'nearby'}
		class:active={panel === 'nearby'}
		onclick={() => (panel = 'nearby')}
	>
		{$_('mapping.detail.tab_nearby')}
	</button>
</div>

{#if panel === 'search'}
	<div class="panel">
		<input
			type="text"
			placeholder={$_('mapping.detail.search_placeholder')}
			bind:value={searchQuery}
			oninput={onSearchQueryInput}
		/>
		{#if searching}
			<p class="hint">{$_('mapping.detail.searching')}</p>
		{:else if searchError}
			<p class="hint error">{searchError}</p>
		{:else if searchQuery.trim().length >= 2 && searchResults.length === 0}
			<p class="hint">{$_('mapping.detail.no_results')}</p>
		{/if}
		{#if searchResults.length > 0}
			<ul class="results">
				{#each searchResults as place (place.latitude + ',' + place.longitude)}
					<li>
						<button onclick={() => selectSearchResult(place)}>{place.display_name}</button>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
{:else if panel === 'directions'}
	<div class="panel">
		<div class="form-row">
			<input type="text" placeholder={$_('mapping.detail.destination_placeholder')} bind:value={destinationInput} />
			<input
				type="text"
				placeholder={home.location_name
					? $_('mapping.detail.origin_placeholder_default', { values: { location: home.location_name } })
					: $_('mapping.detail.origin_placeholder')}
				bind:value={originInput}
			/>
			<div class="mode-toggle" role="group" aria-label={$_('mapping.detail.mode_label')}>
				{#each TRAVEL_MODES as m (m)}
					<button type="button" class="mode-btn" class:active={mode === m} onclick={() => (mode = m)}>
						{$_(`mapping.detail.mode_${m}`)}
					</button>
				{/each}
			</div>
			<button class="primary" disabled={directionsLoading || !destinationInput.trim()} onclick={() => getDirections()}>
				{$_('mapping.detail.get_directions')}
			</button>
		</div>
		{#if directionsLoading}
			<p class="hint">{$_('mapping.detail.loading')}</p>
		{:else if directionsError}
			<p class="hint error">{directionsError}</p>
		{:else if directions}
			<div class="directions-summary">
				<strong>{(directions.distance_meters / 1609.34).toFixed(1)} mi</strong>
				&middot;
				<span>{Math.round(directions.duration_seconds / 60)} min</span>
			</div>
			<ol class="steps">
				{#each directions.steps as step, i (i)}
					<li>{step.instruction} ({(step.distance_meters / 1609.34).toFixed(1)} mi)</li>
				{/each}
			</ol>
		{/if}
	</div>
{:else if panel === 'nearby'}
	<div class="panel">
		<div class="chips" role="group" aria-label={$_('mapping.detail.category_label')}>
			{#each CATEGORIES as category (category)}
				<button
					type="button"
					class="chip"
					class:active={selectedCategory === category}
					onclick={() => (selectedCategory = category)}
				>
					{$_(`mapping.category.${category}`)}
				</button>
			{/each}
		</div>
		<label class="radius-control">
			{$_('mapping.detail.radius_label')}
			{#if radiusUnit === 'mi'}
				<input type="number" min="0.5" max="50" step="0.5" bind:value={radiusInput} />
			{:else}
				<input type="number" min="100" max="80000" step="100" bind:value={radiusInput} />
			{/if}
			<div class="unit-toggle" role="group" aria-label={$_('mapping.detail.radius_unit_label')}>
				<button type="button" class="unit-btn" class:active={radiusUnit === 'mi'} onclick={() => setRadiusUnit('mi')}>
					{$_('mapping.detail.unit_mi')}
				</button>
				<button type="button" class="unit-btn" class:active={radiusUnit === 'm'} onclick={() => setRadiusUnit('m')}>
					{$_('mapping.detail.unit_m')}
				</button>
			</div>
		</label>
		{#if nearbyLoading}
			<p class="hint">{$_('mapping.detail.loading')}</p>
		{:else if nearbyError}
			<p class="hint error">{nearbyError}</p>
		{:else if nearbyPlaces.length === 0}
			<p class="hint">{$_('mapping.detail.no_nearby_results')}</p>
		{:else}
			<ul class="nearby-list">
				{#each nearbyPlaces as place (place.name + place.latitude)}
					<li>
						<button
							type="button"
							class="nearby-item"
							class:active={selectedNearbyPlace === place}
							onclick={() => selectNearbyPlace(place)}
						>
							<span class="name">{place.name}</span>
							{#if place.address}<span class="address">{place.address}</span>{/if}
							<span class="distance">{(place.distance_m / 1609.34).toFixed(1)} mi</span>
						</button>
					</li>
				{/each}
			</ul>
		{/if}
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

	.location-search input,
	.panel input[type='text'] {
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
		max-width: 24rem;
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

	.tabs {
		display: flex;
		gap: 0.5rem;
		margin-top: 1rem;
		border-bottom: 1px solid var(--color-border);
	}

	.tabs button {
		background: none;
		border: none;
		border-bottom: 2px solid transparent;
		padding: 0.5rem 0.25rem;
		color: var(--color-text-muted);
		cursor: pointer;
		font: inherit;
	}

	.tabs button.active {
		color: var(--color-accent);
		border-bottom-color: var(--color-accent);
	}

	.panel {
		margin-top: 1rem;
	}

	.form-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
	}

	.mode-toggle {
		display: inline-flex;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.15rem;
		gap: 0.15rem;
	}

	.mode-btn {
		background: none;
		border: none;
		border-radius: 0.35rem;
		padding: 0.3rem 0.6rem;
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.mode-btn.active {
		background: var(--color-accent);
		color: #fff;
	}

	button.primary {
		background: var(--color-accent);
		color: #fff;
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	button.primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.directions-summary {
		margin-top: 1rem;
		font-size: 1.1rem;
	}

	.steps {
		margin: 0.75rem 0 0;
		padding-left: 1.25rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.chip {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 0.3rem 0.75rem;
		font-size: 0.85rem;
		color: var(--color-text);
		cursor: pointer;
	}

	.chip.active {
		background: var(--color-accent);
		color: #fff;
		border-color: var(--color-accent);
	}

	.radius-control {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.75rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.radius-control input {
		width: 6rem;
		font: inherit;
		padding: 0.3rem 0.5rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.unit-toggle {
		display: inline-flex;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.15rem;
		gap: 0.15rem;
	}

	.unit-btn {
		background: none;
		border: none;
		border-radius: 0.35rem;
		padding: 0.2rem 0.5rem;
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.unit-btn.active {
		background: var(--color-accent);
		color: #fff;
	}

	.nearby-list {
		list-style: none;
		margin: 1rem 0 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.nearby-item {
		display: flex;
		flex-wrap: wrap;
		width: 100%;
		gap: 0.5rem;
		align-items: baseline;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
		font: inherit;
		color: inherit;
		text-align: left;
		cursor: pointer;
	}

	.nearby-item:hover {
		background: var(--color-surface-hover);
	}

	.nearby-item.active {
		border-color: var(--color-accent);
		box-shadow: 0 0 0 1px var(--color-accent);
	}

	.nearby-item .name {
		font-weight: 600;
	}

	.nearby-item .address {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.nearby-item .distance {
		margin-left: auto;
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}
</style>
