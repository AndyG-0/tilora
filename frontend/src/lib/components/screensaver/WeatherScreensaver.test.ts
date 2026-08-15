import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import WeatherScreensaver from './WeatherScreensaver.svelte';

const baseData = {
	location_name: 'Austin',
	temperature: 71.4,
	condition: 'Partly cloudy',
	weather_code: 2,
	is_day: true,
	daily_forecast: [
		{ date: 'Mon', high: 80, low: 60, condition: 'Sunny', weather_code: 0 },
		{ date: 'Tue', high: 75, low: 58, condition: 'Rain', weather_code: 63 },
	],
};

describe('WeatherScreensaver', () => {
	it('renders a current-conditions icon and one icon per forecast day', () => {
		const { container } = render(WeatherScreensaver, { props: { data: baseData } });

		const currentIcon = container.querySelector('.current-icon .weather-icon');
		expect(currentIcon).toBeTruthy();
		expect(currentIcon?.getAttribute('aria-label')).toBe('Partly cloudy');

		const dayIcons = container.querySelectorAll('.day-icon .weather-icon');
		expect(dayIcons).toHaveLength(2);
		expect(dayIcons[0].getAttribute('aria-label')).toBe('Sunny');
		expect(dayIcons[1].getAttribute('aria-label')).toBe('Rain');
	});
});
