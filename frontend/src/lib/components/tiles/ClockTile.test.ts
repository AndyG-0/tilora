import { render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({ widgetSummary: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import ClockTile from './ClockTile.svelte';

describe('ClockTile', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2024-03-15T10:30:15Z'));
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('renders the digital time in UTC before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(ClockTile, { props: { widgetId: 'clock' } });

		expect(screen.getByText('10:30:15 AM')).toBeInTheDocument();
	});

	it('renders the time in the fetched timezone once the summary resolves', async () => {
		widgetSummary.mockResolvedValue({ timezone: 'America/Chicago', style: 'digital' });

		render(ClockTile, { props: { widgetId: 'clock' } });
		await vi.advanceTimersByTimeAsync(0); // flush the onMount fetch

		expect(screen.getByText('5:30:15 AM')).toBeInTheDocument();
	});

	it('ticks the displayed time forward every second', async () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(ClockTile, { props: { widgetId: 'clock' } });
		await vi.advanceTimersByTimeAsync(1000);

		expect(screen.getByText('10:30:16 AM')).toBeInTheDocument();
	});

	it('renders the fetched style once the summary resolves', async () => {
		widgetSummary.mockResolvedValue({ timezone: 'UTC', style: 'analog' });

		const { container } = render(ClockTile, { props: { widgetId: 'clock' } });
		await vi.advanceTimersByTimeAsync(0);

		expect(screen.getByRole('img', { name: 'Analog clock face' })).toBeInTheDocument();
		expect(container.querySelector('.clock-tile')).toBeInTheDocument();
	});

	it('renders binary, word, and matrix styles in the clock tile container', async () => {
		widgetSummary.mockResolvedValue({ timezone: 'UTC', style: 'binary' });
		const r1 = render(ClockTile, { props: { widgetId: 'clock' } });
		await vi.advanceTimersByTimeAsync(0);
		expect(screen.getByRole('img', { name: 'Binary clock face' })).toBeInTheDocument();
		r1.unmount();

		widgetSummary.mockResolvedValue({ timezone: 'UTC', style: 'word' });
		const r2 = render(ClockTile, { props: { widgetId: 'clock' } });
		await vi.advanceTimersByTimeAsync(0);
		expect(screen.getByText(/o'clock|half|past|to/i)).toBeInTheDocument();
		r2.unmount();

		widgetSummary.mockResolvedValue({ timezone: 'UTC', style: 'matrix' });
		const r3 = render(ClockTile, { props: { widgetId: 'clock' } });
		await vi.advanceTimersByTimeAsync(0);
		expect(screen.getByText('10:30:15')).toBeInTheDocument();
		r3.unmount();
	});
});
