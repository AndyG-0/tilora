// Maps Open-Meteo's WMO weather codes (see
// https://open-meteo.com/en/docs#weathervariables, and the condition-key
// grouping in backend/app/plugins/weather/plugin.py's
// _CONDITION_KEY_BY_CODE) to one of WeatherIcon.svelte's icon variants.
// Day/night only matters for the clear/partly-cloudy variants — the rest
// (fog, rain, snow, thunderstorm, ...) look the same regardless of time of
// day, matching common weather-icon conventions.
export type WeatherIconKey =
	| 'clear-day'
	| 'clear-night'
	| 'partly-cloudy-day'
	| 'partly-cloudy-night'
	| 'cloudy'
	| 'fog'
	| 'drizzle'
	| 'rain'
	| 'snow'
	| 'showers'
	| 'thunderstorm';

export function weatherIconKey(code: number, isDay: boolean): WeatherIconKey {
	if (code === 0) return isDay ? 'clear-day' : 'clear-night';
	if (code === 1 || code === 2) return isDay ? 'partly-cloudy-day' : 'partly-cloudy-night';
	if (code === 3) return 'cloudy';
	if (code === 45 || code === 48) return 'fog';
	if (code === 51 || code === 53 || code === 55) return 'drizzle';
	if (code === 61 || code === 63 || code === 65) return 'rain';
	if (code === 71 || code === 73 || code === 75) return 'snow';
	if (code === 80 || code === 81 || code === 82) return 'showers';
	if (code === 95 || code === 96 || code === 99) return 'thunderstorm';
	return 'cloudy';
}
