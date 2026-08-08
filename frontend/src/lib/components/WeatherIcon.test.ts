import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import WeatherIcon from './WeatherIcon.svelte';

describe('WeatherIcon', () => {
	it('renders an accessible svg labeled with the condition text', () => {
		render(WeatherIcon, { props: { code: 0, isDay: true, label: 'Clear sky' } });

		expect(screen.getByRole('img', { name: 'Clear sky' })).toBeInTheDocument();
	});

	it('renders without error for every icon variant', () => {
		const codes = [0, 1, 2, 3, 45, 51, 61, 71, 80, 95, 999];
		for (const code of codes) {
			const { unmount } = render(WeatherIcon, { props: { code, isDay: true, label: 'Condition' } });
			expect(screen.getByRole('img', { name: 'Condition' })).toBeInTheDocument();
			unmount();
		}
	});
});
