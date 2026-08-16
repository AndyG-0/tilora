import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { searchCities, updateWidgetSettings, widgetDetail } = vi.hoisted(() => ({
	searchCities: vi.fn(),
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { searchCities, updateWidgetSettings, widgetDetail } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'weather' } } }));

import { user } from '$lib/stores/user';
import WeatherDetail from './WeatherDetail.svelte';

const baseData = {
	location_name: 'Fort Worth, TX',
	temperature: 72.4,
	condition: 'Mainly clear',
	weather_code: 1,
	is_day: true,
	daily_forecast: [{ date: '2026-07-24', high: 85, low: 68, condition: 'Mainly clear', weather_code: 1 }],
	severe_weather_alerts: true,
};

describe('WeatherDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.useFakeTimers();
		user.set({ id: 'admin-user', name: 'Admin', avatar: null, role: 'admin' });
	});

	it('renders the current conditions and forecast', () => {
		render(WeatherDetail, { props: { data: baseData } });

		expect(screen.getByText('Fort Worth, TX')).toBeInTheDocument();
		expect(screen.getByText('72° · Mainly clear')).toBeInTheDocument();
		expect(screen.getAllByRole('img', { name: 'Mainly clear' })).toHaveLength(2);
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

	it('does not render an air quality section when air_quality is absent', () => {
		render(WeatherDetail, { props: { data: baseData } });

		expect(screen.queryByText('Air Quality')).not.toBeInTheDocument();
	});

	it('renders the AQI badge and pollutant values when air_quality is present', () => {
		render(WeatherDetail, {
			props: {
				data: {
					...baseData,
					air_quality: {
						us_aqi: 42,
						us_aqi_category: 'Good',
						pm2_5: 8.1,
						pm10: 15,
						ozone: 30,
						primary_pollutant: 'pm2_5',
					},
				},
			},
		});

		expect(screen.getByText('Air Quality')).toBeInTheDocument();
		expect(screen.getByText('42')).toBeInTheDocument();
		expect(screen.getByText('Good')).toBeInTheDocument();
		expect(screen.getByText('8.1 µg/m³')).toBeInTheDocument();
		expect(screen.queryByText('Pollen')).not.toBeInTheDocument();
	});

	it('renders the pollen section only when pollen data is present', () => {
		render(WeatherDetail, {
			props: {
				data: {
					...baseData,
					air_quality: {
						us_aqi: 42,
						us_aqi_category: 'Good',
						pm2_5: 8.1,
						pm10: 15,
						ozone: 30,
						primary_pollutant: 'pm2_5',
						pollen: { birch_pollen: 12.5 },
					},
				},
			},
		});

		expect(screen.getByText('Pollen')).toBeInTheDocument();
		expect(screen.getByText('Birch')).toBeInTheDocument();
		expect(screen.getByText('12.5 grains/m³')).toBeInTheDocument();
	});

	it('toggles severe weather alerts and persists the setting', async () => {
		updateWidgetSettings.mockResolvedValue({});
		render(WeatherDetail, { props: { data: baseData } });

		const checkbox = screen.getByLabelText('Severe weather alerts') as HTMLInputElement;
		expect(checkbox.checked).toBe(true);

		await fireEvent.click(checkbox);

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('weather', { severe_weather_alerts: false }),
		);
	});

	it('reverts the toggle if saving the setting fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));
		render(WeatherDetail, { props: { data: baseData } });

		const checkbox = screen.getByLabelText('Severe weather alerts') as HTMLInputElement;
		await fireEvent.click(checkbox);

		await vi.waitFor(() => expect(checkbox.checked).toBe(true));
	});

	it('allows non-admin members to change city but hides severe weather alerts toggle', () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });
		render(WeatherDetail, { props: { data: baseData } });

		expect(screen.getByText('Change city')).toBeInTheDocument();
		expect(screen.queryByLabelText('Severe weather alerts')).not.toBeInTheDocument();
	});
});
