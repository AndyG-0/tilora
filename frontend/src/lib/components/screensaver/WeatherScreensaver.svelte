<script lang="ts">
	interface DailyForecast {
		date: string;
		high: number;
		low: number;
		condition: string;
	}

	interface WeatherScreensaverData {
		location_name: string;
		temperature: number;
		condition: string;
		daily_forecast: DailyForecast[];
	}

	let { data }: { data: WeatherScreensaverData } = $props();
</script>

<div class="stage">
	<h1>{data.location_name}</h1>
	<p class="current">{Math.round(data.temperature)}°</p>
	<p class="condition">{data.condition}</p>

	<div class="forecast">
		{#each data.daily_forecast as day (day.date)}
			<div class="day">
				<div class="date">{day.date}</div>
				<div class="cond">{day.condition}</div>
				<div class="range">{Math.round(day.high)}° / {Math.round(day.low)}°</div>
			</div>
		{/each}
	</div>
</div>

<style>
	.stage {
		height: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
		gap: 0.5rem;
	}

	h1 {
		font-size: clamp(1.75rem, 5vw, 3rem);
		margin: 0;
	}

	.current {
		font-size: clamp(4rem, 14vw, 10rem);
		font-weight: 700;
		margin: 0;
		line-height: 1;
	}

	.condition {
		font-size: clamp(1.25rem, 3vw, 2rem);
		color: var(--color-text-muted);
		margin: 0 0 2rem;
	}

	.forecast {
		display: flex;
		gap: 1.5rem;
		flex-wrap: wrap;
		justify-content: center;
	}

	.day {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1.25rem 1.75rem;
		min-width: 9rem;
		font-size: 1.15rem;
	}

	.date {
		font-weight: 600;
	}

	.cond {
		color: var(--color-text-muted);
		margin: 0.4rem 0;
	}
</style>
