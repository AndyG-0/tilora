import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import ClockDetail from './ClockDetail.svelte';

describe('ClockDetail', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2024-03-15T10:30:15Z'));
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('renders the time in the given timezone and a hint with the timezone name', () => {
		render(ClockDetail, { props: { data: { timezone: 'UTC' } } });

		expect(screen.getByText('10:30:15 AM')).toBeInTheDocument();
		expect(screen.getByText('UTC · change this in Settings')).toBeInTheDocument();
	});

	it('formats the time using the provided timezone, not just UTC', () => {
		render(ClockDetail, { props: { data: { timezone: 'America/Chicago' } } });

		expect(screen.getByText('5:30:15 AM')).toBeInTheDocument();
	});

	it('ticks every second', async () => {
		render(ClockDetail, { props: { data: { timezone: 'UTC' } } });

		expect(screen.getByText('10:30:15 AM')).toBeInTheDocument();

		await vi.advanceTimersByTimeAsync(1000);

		expect(screen.getByText('10:30:16 AM')).toBeInTheDocument();
	});
});
