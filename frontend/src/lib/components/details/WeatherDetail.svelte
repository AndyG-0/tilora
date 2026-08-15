<script lang="ts">
	import { page } from '$app/state';
	import { api, type CityResult } from '$lib/api';
	import WeatherIcon from '$lib/components/WeatherIcon.svelte';
	import { user } from '$lib/stores/user';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	interface DailyForecast {
		date: string;
		high: number;
		low: number;
		condition: string;
		weather_code: number;
	}

	interface AirQuality {
		us_aqi: number;
		us_aqi_category: string;
		pm2_5: number | null;
		pm10: number | null;
		ozone: number | null;
		primary_pollutant: string | null;
		pollen?: Record<string, number>;
	}

	interface WeatherDetailData {
		location_name: string;
		temperature: number;
		condition: string;
		weather_code: number;
		is_day: boolean;
		daily_forecast: DailyForecast[];
		severe_weather_alerts: boolean;
		air_quality?: AirQuality;
	}

	// US AQI thresholds (airnow.gov) mapped to a badge color.
	function aqiColor(us_aqi: number): string {
		if (us_aqi <= 50) return 'var(--color-success, #2e7d32)';
		if (us_aqi <= 100) return 'var(--color-warning, #f9a825)';
		if (us_aqi <= 150) return 'var(--color-warning, #ef6c00)';
		if (us_aqi <= 200) return 'var(--color-error, #c62828)';
		if (us_aqi <= 300) return 'var(--color-error, #6a1b9a)';
		return 'var(--color-error, #4a148c)';
	}

	const POLLEN_KEYS: Record<string, string> = {
		alder_pollen: 'weather.detail.pollen.alder',
		birch_pollen: 'weather.detail.pollen.birch',
		grass_pollen: 'weather.detail.pollen.grass',
		mugwort_pollen: 'weather.detail.pollen.mugwort',
		olive_pollen: 'weather.detail.pollen.olive',
		ragweed_pollen: 'weather.detail.pollen.ragweed',
	};

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

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from toggleSevereWeatherAlerts.
	let severeWeatherAlerts = $state(initialData.severe_weather_alerts);
	let savingSevereWeatherAlerts = $state(false);

	async function toggleSevereWeatherAlerts() {
		const next = !severeWeatherAlerts;
		severeWeatherAlerts = next;
		savingSevereWeatherAlerts = true;
		try {
			await api.updateWidgetSettings(page.params.id!, { severe_weather_alerts: next });
		} catch {
			severeWeatherAlerts = !next;
			error = get(_)('weather.detail.update_failed');
		} finally {
			savingSevereWeatherAlerts = false;
		}
	}

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
				error = get(_)('weather.detail.search_failed');
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
			error = get(_)('weather.detail.update_failed');
		} finally {
			saving = false;
		}
	}

	const isAdmin = $derived($user?.role === 'admin');
</script>

<div class="header">
	<h1>{weather.location_name}</h1>
	{#if isAdmin}
		<button class="change-city" onclick={() => (editingCity = !editingCity)}>
			{editingCity ? $_('weather.detail.cancel') : $_('weather.detail.change_city')}
		</button>
	{/if}
</div>

{#if isAdmin && editingCity}
	<div class="city-search">
		<input
			type="text"
			placeholder={$_('weather.detail.search_placeholder')}
			bind:value={query}
			oninput={onQueryInput}
		/>
		{#if searching}
			<p class="hint">{$_('weather.detail.searching')}</p>
		{:else if error}
			<p class="hint error">{error}</p>
		{:else if query.trim().length >= 2 && results.length === 0}
			<p class="hint">{$_('weather.detail.no_cities_found')}</p>
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

{#if isAdmin}
	<label class="severe-weather-toggle">
		<input
			type="checkbox"
			checked={severeWeatherAlerts}
			disabled={savingSevereWeatherAlerts}
			onchange={toggleSevereWeatherAlerts}
		/>
		{$_('weather.detail.severe_weather_alerts')}
	</label>
{/if}

<div class="current">
	<div class="current-icon">
		<WeatherIcon code={weather.weather_code} isDay={weather.is_day} label={weather.condition} />
	</div>
	<p class="current-text">{Math.round(weather.temperature)}° · {weather.condition}</p>
</div>

<div class="forecast">
	{#each weather.daily_forecast as day (day.date)}
		<div class="day">
			<div class="date">{day.date}</div>
			<div class="day-icon"><WeatherIcon code={day.weather_code} isDay={true} label={day.condition} /></div>
			<div class="condition">{day.condition}</div>
			<div class="range">{Math.round(day.high)}° / {Math.round(day.low)}°</div>
		</div>
	{/each}
</div>

{#if weather.air_quality}
	<div class="air-quality">
		<h2>{$_('weather.detail.air_quality_title')}</h2>
		<div class="aqi-badge" style="--aqi-color: {aqiColor(weather.air_quality.us_aqi)}">
			<span class="aqi-value">{weather.air_quality.us_aqi}</span>
			<span class="aqi-category">{weather.air_quality.us_aqi_category}</span>
		</div>
		<div class="pollutants">
			{#if weather.air_quality.pm2_5 !== null}
				<div class="pollutant">
					<span class="label">PM2.5</span>
					<span class="value">{weather.air_quality.pm2_5} µg/m³</span>
				</div>
			{/if}
			{#if weather.air_quality.pm10 !== null}
				<div class="pollutant">
					<span class="label">PM10</span>
					<span class="value">{weather.air_quality.pm10} µg/m³</span>
				</div>
			{/if}
			{#if weather.air_quality.ozone !== null}
				<div class="pollutant">
					<span class="label">O₃</span>
					<span class="value">{weather.air_quality.ozone} µg/m³</span>
				</div>
			{/if}
		</div>

		{#if weather.air_quality.pollen}
			<h3>{$_('weather.detail.pollen_title')}</h3>
			<div class="pollen">
				{#each Object.entries(weather.air_quality.pollen) as [field, value] (field)}
					<div class="pollutant">
						<span class="label">{$_(POLLEN_KEYS[field] ?? field)}</span>
						<span class="value">{value} grains/m³</span>
					</div>
				{/each}
			</div>
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
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 2rem;
	}

	.current-icon {
		width: 3.5rem;
		height: 3.5rem;
		flex-shrink: 0;
	}

	.current-text {
		font-size: 1.5rem;
		color: var(--color-text-muted);
		margin: 0;
	}

	.severe-weather-toggle {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 1rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
		cursor: pointer;
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

	.day-icon {
		width: 2.5rem;
		height: 2.5rem;
		margin: 0.25rem 0;
	}

	.condition {
		color: var(--color-text-muted);
		margin: 0.25rem 0;
	}

	.air-quality {
		margin-top: 2rem;
	}

	.air-quality h2 {
		font-size: 1.1rem;
		margin: 0 0 0.75rem;
	}

	.air-quality h3 {
		font-size: 1rem;
		color: var(--color-text-muted);
		margin: 1.25rem 0 0.75rem;
	}

	.aqi-badge {
		display: inline-flex;
		align-items: baseline;
		gap: 0.5rem;
		background: var(--aqi-color);
		color: #fff;
		border-radius: 0.75rem;
		padding: 0.5rem 1rem;
	}

	.aqi-value {
		font-size: 1.5rem;
		font-weight: 700;
	}

	.aqi-category {
		font-size: 0.9rem;
	}

	.pollutants,
	.pollen {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
		margin-top: 0.75rem;
	}

	.pollutant {
		display: flex;
		flex-direction: column;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.5rem 0.75rem;
		min-width: 5rem;
	}

	.pollutant .label {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.pollutant .value {
		font-weight: 600;
	}
</style>
