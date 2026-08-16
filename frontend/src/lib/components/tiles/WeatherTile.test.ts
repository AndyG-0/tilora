import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { locale, waitLocale } from 'svelte-i18n';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import WeatherTile from './WeatherTile.svelte';

describe('WeatherTile', () => {
	afterEach(async () => {
		locale.set('en');
		await waitLocale();
	});

	it('translates static text when the locale changes', async () => {
		locale.set('es');
		await waitLocale();
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(WeatherTile, { props: { widgetId: 'weather', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Cargando el clima…')).toBeInTheDocument();
	});

	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(WeatherTile, { props: { widgetId: 'weather', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Loading weather…')).toBeInTheDocument();
	});

	it('renders the fetched summary', async () => {
		widgetSummary.mockResolvedValue({
			location_name: 'Fort Worth, TX',
			temperature: 72.4,
			condition: 'Mainly clear',
			weather_code: 1,
			is_day: true,
		});

		render(WeatherTile, { props: { widgetId: 'weather', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Fort Worth, TX')).toBeInTheDocument();
		expect(screen.getByText('72°')).toBeInTheDocument();
		expect(screen.getByText('Mainly clear')).toBeInTheDocument();
		expect(screen.getByRole('img', { name: 'Mainly clear' })).toBeInTheDocument();
	});

	it('keeps the last known value when a later poll fails', async () => {
		vi.useFakeTimers();
		try {
			widgetSummary.mockResolvedValueOnce({
				location_name: 'Fort Worth, TX',
				temperature: 72,
				condition: 'Clear sky',
				weather_code: 0,
				is_day: true,
			});
			render(WeatherTile, { props: { widgetId: 'weather', refreshIntervalSeconds: 60 } });
			await vi.advanceTimersByTimeAsync(0); // flush the initial refresh() from onMount
			expect(screen.getByText('Fort Worth, TX')).toBeInTheDocument();

			widgetSummary.mockRejectedValueOnce(new Error('network error'));
			await vi.advanceTimersByTimeAsync(60_000);

			expect(screen.getByText('Fort Worth, TX')).toBeInTheDocument();
		} finally {
			vi.useRealTimers();
		}
	});
});
