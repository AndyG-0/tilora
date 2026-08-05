import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AnalogFace from './AnalogFace.svelte';

describe('AnalogFace', () => {
	it('rotates the hands to match the given time', () => {
		const now = new Date('2024-03-15T10:30:15Z');

		render(AnalogFace, { props: { now, timezone: 'UTC', size: 'tile' } });

		const svg = screen.getByRole('img', { name: 'Analog clock face' });
		const secondHand = svg.querySelector('.hand.second');
		const minuteHand = svg.querySelector('.hand.minute');
		const hourHand = svg.querySelector('.hand.hour');

		// 10:30:15 -> second hand at 15*6=90deg, minute hand at (30+15/60)*6=181.5deg,
		// hour hand at (10 + 30/60)*30 = 315deg.
		expect(secondHand?.getAttribute('transform')).toBe('rotate(90 100 100)');
		expect(minuteHand?.getAttribute('transform')).toBe('rotate(181.5 100 100)');
		expect(hourHand?.getAttribute('transform')).toBe('rotate(315 100 100)');
	});
});
