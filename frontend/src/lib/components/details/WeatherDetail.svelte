<script lang="ts">
	import { page } from '$app/state';
	import { api, type CityResult } from '$lib/api';

	interface DailyForecast {
		date: string;
		high: number;
		low: number;
		condition: string;
	}

	interface WeatherDetailData {
		location_name: string;
		temperature: number;
		condition: string;
		daily_forecast: DailyForecast[];
	}

	let { data: initialData }: { data: WeatherDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from selectCity's refetch.
	let weather = $state(initialData);

	let editingCity = $state(false);
	let query = $state('');
	let results = $state<CityResult[]>([]);
	let searching = $state(false);
	let saving = $state(false);
	let error = $state<string | null>(null);

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
				error = 'City search failed.';
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
			weather = await api.widgetDetail<WeatherDetailData>(page.params.id!);
			editingCity = false;
			query = '';
			results = [];
		} catch {
			error = 'Could not update the location.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>{weather.location_name}</h1>
	<button class="change-city" onclick={() => (editingCity = !editingCity)}>
		{editingCity ? 'Cancel' : 'Change city'}
	</button>
</div>

{#if editingCity}
	<div class="city-search">
		<input type="text" placeholder="Search for a city…" bind:value={query} oninput={onQueryInput} />
		{#if searching}
			<p class="hint">Searching…</p>
		{:else if error}
			<p class="hint error">{error}</p>
		{:else if query.trim().length >= 2 && results.length === 0}
			<p class="hint">No cities found.</p>
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

<p class="current">{Math.round(weather.temperature)}° · {weather.condition}</p>

<div class="forecast">
	{#each weather.daily_forecast as day (day.date)}
		<div class="day">
			<div class="date">{day.date}</div>
			<div class="condition">{day.condition}</div>
			<div class="range">{Math.round(day.high)}° / {Math.round(day.low)}°</div>
		</div>
	{/each}
</div>

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

	.change-city {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.city-search {
		margin: 1rem 0;
	}

	.city-search input {
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

	.current {
		font-size: 1.5rem;
		color: var(--color-text-muted);
		margin-bottom: 2rem;
	}

	.forecast {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.day {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1rem 1.5rem;
		min-width: 8rem;
	}

	.date {
		font-weight: 600;
	}

	.condition {
		color: var(--color-text-muted);
		margin: 0.25rem 0;
	}
</style>
