import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import WeatherTile from './WeatherTile.svelte';

describe('WeatherTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(WeatherTile, { props: { widgetId: 'weather' } });

		expect(screen.getByText('Loading weather…')).toBeInTheDocument();
	});

	it('renders the fetched summary', async () => {
		widgetSummary.mockResolvedValue({
			location_name: 'Fort Worth, TX',
			temperature: 72.4,
			condition: 'Mainly clear',
		});

		render(WeatherTile, { props: { widgetId: 'weather' } });

		expect(await screen.findByText('Fort Worth, TX')).toBeInTheDocument();
		expect(screen.getByText('72°')).toBeInTheDocument();
		expect(screen.getByText('Mainly clear')).toBeInTheDocument();
	});

	it('keeps the last known value when a later poll fails', async () => {
		vi.useFakeTimers();
		try {
			widgetSummary.mockResolvedValueOnce({
				location_name: 'Fort Worth, TX',
				temperature: 72,
				condition: 'Clear sky',
			});
			render(WeatherTile, { props: { widgetId: 'weather' } });
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
