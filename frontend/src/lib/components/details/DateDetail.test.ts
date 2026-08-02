import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import DateDetail from './DateDetail.svelte';

describe('DateDetail', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2024-03-15T10:30:15Z'));
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('renders the date in the given timezone and a hint with the timezone name', () => {
		render(DateDetail, { props: { data: { timezone: 'UTC' } } });

		expect(screen.getByText('Friday, March 15, 2024')).toBeInTheDocument();
		expect(screen.getByText('UTC · change this in Settings')).toBeInTheDocument();
	});

	it('formats the date using the provided timezone, not just UTC', () => {
		render(DateDetail, { props: { data: { timezone: 'Pacific/Kiritimati' } } });

		expect(screen.getByText('Saturday, March 16, 2024')).toBeInTheDocument();
	});
});
