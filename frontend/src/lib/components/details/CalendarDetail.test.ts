import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

vi.mock('$env/dynamic/public', () => ({ env: { PUBLIC_API_BASE_URL: 'http://api.test' } }));

const { listCaldavCalendars, updateWidgetSettings, widgetDetail } = vi.hoisted(() => ({
	listCaldavCalendars: vi.fn(),
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { listCaldavCalendars, updateWidgetSettings, widgetDetail } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'calendar' } } }));

import CalendarDetail from './CalendarDetail.svelte';

describe('CalendarDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows a connect button when not connected', () => {
		render(CalendarDetail, { props: { data: { connected: false, events: [] } } });

		const link = screen.getByText('Connect Google Calendar');
		expect(link).toBeInTheDocument();
		expect(link).toHaveAttribute('href', 'http://api.test/api/calendar/auth/start');
	});

	it('renders a connect link for a microsoft widget that is not connected', () => {
		render(CalendarDetail, {
			props: { data: { connected: false, provider: 'microsoft', events: [] } },
		});

		const link = screen.getByText('Connect Outlook Calendar');
		expect(link).toBeInTheDocument();
		expect(link).toHaveAttribute('href', 'http://api.test/api/calendar/auth/microsoft/start');
	});

	it('points to settings when a caldav widget is not connected', () => {
		render(CalendarDetail, {
			props: { data: { connected: false, provider: 'caldav', events: [] } },
		});

		expect(screen.queryByText('Connect Google Calendar')).not.toBeInTheDocument();
		const link = screen.getByText('Open settings');
		expect(link).toHaveAttribute('href', '/settings');
	});

	it('renders upcoming events when connected', () => {
		render(CalendarDetail, {
			props: {
				data: {
					connected: true,
					events: [
						{
							id: 'e1',
							title: 'Team sync',
							start: '2026-01-01',
							all_day: true,
							location: 'Room 1',
						},
					],
				},
			},
		});

		expect(screen.getByText('Team sync')).toBeInTheDocument();
		expect(screen.getByText(/Room 1/)).toBeInTheDocument();
	});

	it('shows a hint when there are no upcoming events', () => {
		render(CalendarDetail, { props: { data: { connected: true, events: [] } } });

		expect(screen.getByText('No upcoming events.')).toBeInTheDocument();
	});

	it('does not show "Manage calendars" for a connected google widget', () => {
		render(CalendarDetail, {
			props: { data: { connected: true, provider: 'google', events: [] } },
		});

		expect(screen.queryByText('Manage calendars')).not.toBeInTheDocument();
	});

	it('shows a calendar label per event when multiple calendars are merged', () => {
		render(CalendarDetail, {
			props: {
				data: {
					connected: true,
					provider: 'caldav',
					events: [
						{ id: 'e1', title: 'Standup', start: '2026-01-01', all_day: true, location: null, calendar: 'Home' },
						{ id: 'e2', title: 'Review', start: '2026-01-02', all_day: true, location: null, calendar: 'Work' },
					],
				},
			},
		});

		expect(screen.getByText(/· Home/)).toBeInTheDocument();
		expect(screen.getByText(/· Work/)).toBeInTheDocument();
	});

	it('lets the user pick which caldav calendars feed the widget', async () => {
		listCaldavCalendars.mockResolvedValue([
			{ id: 'home-id', name: 'Home', color: '#2a78d6' },
			{ id: 'work-id', name: 'Work', color: '#1baf7a' },
		]);
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({
			connected: true,
			provider: 'caldav',
			calendar_ids: ['home-id', 'work-id'],
			events: [],
		});

		render(CalendarDetail, {
			props: {
				data: { connected: true, provider: 'caldav', calendar_ids: ['home-id'], events: [] },
			},
		});

		await fireEvent.click(screen.getByText('Manage calendars'));

		const home = await screen.findByLabelText('Home');
		const work = await screen.findByLabelText('Work');
		expect(home).toBeChecked();
		expect(work).not.toBeChecked();

		await fireEvent.click(work);
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('calendar', {
			calendar_ids: ['home-id', 'work-id'],
			calendar_colors: { 'home-id': '#2a78d6', 'work-id': '#1baf7a' },
		});
		expect(widgetDetail).toHaveBeenCalledWith('calendar');
	});

	it('lets the user override a calendar color before saving', async () => {
		listCaldavCalendars.mockResolvedValue([{ id: 'home-id', name: 'Home', color: '#2a78d6' }]);
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({
			connected: true,
			provider: 'caldav',
			calendar_ids: ['home-id'],
			calendar_colors: { 'home-id': '#ff0000' },
			events: [],
		});

		render(CalendarDetail, {
			props: {
				data: { connected: true, provider: 'caldav', calendar_ids: ['home-id'], events: [] },
			},
		});

		await fireEvent.click(screen.getByText('Manage calendars'));

		const colorInput = await screen.findByLabelText('Home color');
		await fireEvent.change(colorInput, { target: { value: '#ff0000' } });
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('calendar', {
			calendar_ids: ['home-id'],
			calendar_colors: { 'home-id': '#ff0000' },
		});
	});
});
