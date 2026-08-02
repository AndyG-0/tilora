import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { searchCities, updateWidgetSettings, widgetDetail } = vi.hoisted(() => ({
	searchCities: vi.fn(),
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { searchCities, updateWidgetSettings, widgetDetail } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'weather' } } }));

import WeatherDetail from './WeatherDetail.svelte';

const baseData = {
	location_name: 'Fort Worth, TX',
	temperature: 72.4,
	condition: 'Mainly clear',
	daily_forecast: [{ date: '2026-07-24', high: 85, low: 68, condition: 'Mainly clear' }],
};

describe('WeatherDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.useFakeTimers();
	});

	it('renders the current conditions and forecast', () => {
		render(WeatherDetail, { props: { data: baseData } });

		expect(screen.getByText('Fort Worth, TX')).toBeInTheDocument();
		expect(screen.getByText('72° · Mainly clear')).toBeInTheDocument();
	});

	it('searches cities after typing and lets the user pick one', async () => {
		searchCities.mockResolvedValue([
			{ name: 'Fort Worth', admin1: 'Texas', country: 'United States', latitude: 32.7555, longitude: -97.3308 },
		]);
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({ ...baseData, location_name: 'Fort Worth, Texas' });

		render(WeatherDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Change city'));
		await fireEvent.input(screen.getByPlaceholderText('Search for a city…'), {
			target: { value: 'Fort Worth' },
		});
		await vi.advanceTimersByTimeAsync(300);

		expect(searchCities).toHaveBeenCalledWith('Fort Worth');
		const option = await screen.findByText('Fort Worth, Texas');

		await fireEvent.click(option);
		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());

		expect(updateWidgetSettings).toHaveBeenCalledWith('weather', {
			latitude: 32.7555,
			longitude: -97.3308,
			location_name: 'Fort Worth, Texas',
		});
		expect(widgetDetail).toHaveBeenCalledWith('weather');
	});

	it('does not search until at least two characters are entered', async () => {
		render(WeatherDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Change city'));
		await fireEvent.input(screen.getByPlaceholderText('Search for a city…'), {
			target: { value: 'F' },
		});
		await vi.advanceTimersByTimeAsync(300);

		expect(searchCities).not.toHaveBeenCalled();
	});
});
