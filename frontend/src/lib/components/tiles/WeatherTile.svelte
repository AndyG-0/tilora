<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import WeatherIcon from '$lib/components/WeatherIcon.svelte';
	import { _ } from 'svelte-i18n';

	interface WeatherSummary {
		location_name: string;
		temperature: number;
		condition: string;
		weather_code: number;
		is_day: boolean;
	}

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<WeatherSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<WeatherSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);
</script>

<TileCard {widgetId}>
	{#if summary}
		<div class="location">{summary.location_name}</div>
		<div class="main">
			<div class="icon">
				<WeatherIcon code={summary.weather_code} isDay={summary.is_day} label={summary.condition} />
			</div>
			<div class="temp">{Math.round(summary.temperature)}°</div>
		</div>
		<div class="condition">{summary.condition}</div>
	{:else}
		<div class="condition">{$_('weather.tile.loading')}</div>
	{/if}
</TileCard>

<style>
	.location {
		font-size: clamp(0.75rem, 8cqh, 0.9rem);
		color: var(--color-text-muted);
	}

	.main {
		display: flex;
		align-items: center;
		gap: 0.25em;
	}

	.icon {
		width: clamp(1.75rem, 22cqh, 4rem);
		height: clamp(1.75rem, 22cqh, 4rem);
		flex-shrink: 0;
	}

	.temp {
		font-size: clamp(1.75rem, 26cqh, 3.5rem);
		font-weight: 600;
		line-height: 1.1;
	}

	.condition {
		font-size: clamp(0.75rem, 8cqh, 1rem);
		color: var(--color-text-muted);
	}
</style>
