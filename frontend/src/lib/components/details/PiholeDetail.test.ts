import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, updateWidgetSettings, piholeTestConnection, piholeSetBlocking } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
	piholeTestConnection: vi.fn(),
	piholeSetBlocking: vi.fn(),
}));
vi.mock('$lib/api', () => ({
	api: { widgetDetail, updateWidgetSettings, piholeTestConnection, piholeSetBlocking },
}));
vi.mock('$app/state', () => ({ page: { params: { id: 'pihole' } } }));

import PiholeDetail from './PiholeDetail.svelte';

const notConnected = {
	connected: false,
	host: '',
	port: 80,
	use_https: false,
	has_password: false,
	blocking_enabled: true,
	queries_today: 0,
	blocked_today: 0,
	percent_blocked: 0,
	unique_clients: 0,
	clients_total: 0,
	domains_blocked: 0,
	gravity_last_update: null,
	top_blocked_domains: [],
	top_permitted_domains: [],
};

const connected = {
	...notConnected,
	connected: true,
	host: 'pi.hole',
	has_password: true,
	queries_today: 1234,
	blocked_today: 321,
	percent_blocked: 26.0,
	unique_clients: 5,
	clients_total: 8,
	domains_blocked: 100000,
	top_blocked_domains: [{ domain: 'ads.example.com', count: 10 }],
	top_permitted_domains: [{ domain: 'good.example.com', count: 20 }],
};

describe('PiholeDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows a not-connected hint', () => {
		render(PiholeDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — tap "Edit connection" to set up Pi-hole.')).toBeInTheDocument();
	});

	it('renders stats and domain lists when connected', () => {
		render(PiholeDetail, { props: { data: connected } });

		expect(screen.getByText('● Blocking enabled')).toBeInTheDocument();
		expect(screen.getByText('1,234')).toBeInTheDocument();
		expect(screen.getByText('321')).toBeInTheDocument();
		expect(screen.getByText('26%')).toBeInTheDocument();
		expect(screen.getByText('5 / 8')).toBeInTheDocument();
		expect(screen.getByText('ads.example.com')).toBeInTheDocument();
		expect(screen.getByText('good.example.com')).toBeInTheDocument();
	});

	it('shows the paused state and lets the user re-enable blocking', async () => {
		piholeSetBlocking.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({ ...connected, blocking_enabled: true });

		render(PiholeDetail, { props: { data: { ...connected, blocking_enabled: false } } });

		expect(screen.getByText('⏸ Blocking paused')).toBeInTheDocument();

		await fireEvent.click(screen.getByText('Enable'));

		expect(piholeSetBlocking).toHaveBeenCalledWith('pihole', true, null);
		await vi.waitFor(() => expect(widgetDetail).toHaveBeenCalledWith('pihole'));
	});

	it('pauses blocking for a fixed duration', async () => {
		piholeSetBlocking.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue(connected);

		render(PiholeDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Pause 5m'));

		expect(piholeSetBlocking).toHaveBeenCalledWith('pihole', false, 300);
	});

	it('tests the connection and saves settings from the editor', async () => {
		piholeTestConnection.mockResolvedValue({ ok: true, version: '5.0', error: null });
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue(connected);

		render(PiholeDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Test connection'));

		expect(await screen.findByText('✓ Connected (Pi-hole 5.0)')).toBeInTheDocument();

		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(widgetDetail).toHaveBeenCalledWith('pihole');
	});

	it('shows a failed test-connection result', async () => {
		piholeTestConnection.mockResolvedValue({ ok: false, version: null, error: 'Pi-hole rejected credentials' });

		render(PiholeDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Test connection'));

		expect(await screen.findByText('✗ Pi-hole rejected credentials')).toBeInTheDocument();
	});
});
