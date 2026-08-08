import { render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({ widgetSummary: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import DateTile from './DateTile.svelte';

describe('DateTile', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2024-03-15T10:30:15Z'));
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('renders the weekday and date in UTC before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(DateTile, { props: { widgetId: 'date' } });

		expect(screen.getByText('Friday')).toBeInTheDocument();
		expect(screen.getByText('March 15')).toBeInTheDocument();
		expect(screen.getByText('2024')).toBeInTheDocument();
	});

	it('renders the weekday and date in the fetched timezone once the summary resolves', async () => {
		// America/Chicago is still March 15 (Friday) at this instant, so use a
		// timezone that actually rolls the date over to prove the fetched
		// timezone is applied, not just the UTC fallback re-rendering.
		widgetSummary.mockResolvedValue({ timezone: 'Pacific/Kiritimati' });

		render(DateTile, { props: { widgetId: 'date' } });
		await vi.advanceTimersByTimeAsync(0); // flush the onMount fetch

		expect(screen.getByText('Saturday')).toBeInTheDocument();
		expect(screen.getByText('March 16')).toBeInTheDocument();
		expect(screen.getByText('2024')).toBeInTheDocument();
	});
});
