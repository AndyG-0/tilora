import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, createAlert, dismissAlert } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	createAlert: vi.fn(),
	dismissAlert: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetDetail, createAlert, dismissAlert } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'alert' } } }));

import AlertDetail from './AlertDetail.svelte';

const alert1 = {
	id: 1,
	widget_id: 'alert',
	severity: 'warning' as const,
	message: 'Freeze warning',
	created_at: '2026-01-01T00:00:00+00:00',
	expires_at: null,
	dismissed: false,
};

describe('AlertDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders each active alert', () => {
		render(AlertDetail, { props: { data: { alerts: [alert1] } } });

		expect(screen.getByText('Freeze warning')).toBeInTheDocument();
		expect(screen.getByText('warning')).toBeInTheDocument();
	});

	it('shows a hint when there are no active alerts', () => {
		render(AlertDetail, { props: { data: { alerts: [] } } });

		expect(screen.getByText('No active alerts.')).toBeInTheDocument();
	});

	it('dismisses an alert and refetches', async () => {
		dismissAlert.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({ alerts: [] });

		render(AlertDetail, { props: { data: { alerts: [alert1] } } });

		await fireEvent.click(screen.getByText('Dismiss'));

		await vi.waitFor(() => expect(dismissAlert).toHaveBeenCalledWith(1));
		expect(await screen.findByText('No active alerts.')).toBeInTheDocument();
	});

	it('creates a new alert from the form and refetches', async () => {
		createAlert.mockResolvedValue({ ...alert1, id: 2, message: 'New one' });
		widgetDetail.mockResolvedValue({ alerts: [{ ...alert1, id: 2, message: 'New one' }] });

		render(AlertDetail, { props: { data: { alerts: [] } } });

		await fireEvent.input(screen.getByPlaceholderText('Alert message…'), {
			target: { value: 'New one' },
		});
		await fireEvent.click(screen.getByText('Add alert'));

		await vi.waitFor(() => expect(createAlert).toHaveBeenCalledWith({ message: 'New one', severity: 'info' }));
		expect(await screen.findByText('New one')).toBeInTheDocument();
	});

	it('shows an error if creating an alert fails', async () => {
		createAlert.mockRejectedValue(new Error('boom'));

		render(AlertDetail, { props: { data: { alerts: [] } } });

		await fireEvent.input(screen.getByPlaceholderText('Alert message…'), {
			target: { value: 'Oops' },
		});
		await fireEvent.click(screen.getByText('Add alert'));

		expect(await screen.findByText('Could not create the alert.')).toBeInTheDocument();
	});
});
