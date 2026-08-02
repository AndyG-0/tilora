import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import CalendarTile from './CalendarTile.svelte';

describe('CalendarTile', () => {
	it('shows a not-connected state', async () => {
		widgetSummary.mockResolvedValue({ connected: false, events: [] });

		render(CalendarTile, { props: { widgetId: 'calendar' } });

		expect(await screen.findByText('Not connected')).toBeInTheDocument();
	});

	it('shows a no-events state when connected', async () => {
		widgetSummary.mockResolvedValue({ connected: true, events: [] });

		render(CalendarTile, { props: { widgetId: 'calendar' } });

		expect(await screen.findByText('No upcoming events')).toBeInTheDocument();
	});

	it('renders upcoming events', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			events: [{ id: 'e1', title: 'Team sync', start: '2026-01-01T10:00:00Z', all_day: false, location: null }],
		});

		render(CalendarTile, { props: { widgetId: 'calendar' } });

		expect(await screen.findByText('Team sync')).toBeInTheDocument();
	});

	it('shows a formatted date/time and color dot per event', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			events: [
				{
					id: 'e1',
					title: 'Team sync',
					start: '2026-01-01T10:00:00Z',
					all_day: false,
					location: null,
					color: '#2a78d6',
				},
				{
					id: 'e2',
					title: 'Holiday',
					start: '2026-01-02',
					all_day: true,
					location: null,
					color: null,
				},
			],
		});

		render(CalendarTile, { props: { widgetId: 'calendar' } });

		await screen.findByText('Team sync');

		const timedFormatted = new Intl.DateTimeFormat(undefined, {
			weekday: 'short',
			hour: 'numeric',
			minute: '2-digit',
		}).format(new Date('2026-01-01T10:00:00Z'));
		const allDayFormatted = new Intl.DateTimeFormat(undefined, {
			weekday: 'short',
			month: 'short',
			day: 'numeric',
		}).format(new Date('2026-01-02'));

		expect(screen.getByText(timedFormatted)).toBeInTheDocument();
		expect(screen.getByText(allDayFormatted)).toBeInTheDocument();
	});
});
