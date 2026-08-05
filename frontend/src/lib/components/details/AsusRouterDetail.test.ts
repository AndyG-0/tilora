import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, updateWidgetSettings, asusRouterTestConnection } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
	asusRouterTestConnection: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetDetail, updateWidgetSettings, asusRouterTestConnection } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'asus_router' } } }));

import { user } from '$lib/stores/user';
import AsusRouterDetail from './AsusRouterDetail.svelte';

const notConnected = {
	connected: false,
	wan_connected: false,
	client_count: 0,
	host: '',
	ssh_port: 22,
	username: '',
	has_password: false,
	wan_ip: null,
	clients: [],
	rx_bytes: 0,
	tx_bytes: 0,
};

const connected = {
	connected: true,
	wan_connected: true,
	client_count: 2,
	host: 'router.local',
	ssh_port: 22,
	username: 'admin',
	has_password: true,
	wan_ip: '203.0.113.5',
	clients: [
		{ name: 'Laptop', ip: '192.168.1.10', online: true },
		{ name: 'Phone', ip: '192.168.1.11', online: false },
	],
	rx_bytes: 1_500_000,
	tx_bytes: 500_000,
};

describe('AsusRouterDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		user.set({ id: 'admin-user', name: 'Admin', avatar: null, role: 'admin' });
	});

	it('shows a not-connected hint', () => {
		render(AsusRouterDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — tap "Edit connection" to set up your router.')).toBeInTheDocument();
	});

	it('renders WAN status and clients when connected', () => {
		render(AsusRouterDetail, { props: { data: connected } });

		expect(screen.getByText('Connected')).toBeInTheDocument();
		expect(screen.getByText('203.0.113.5')).toBeInTheDocument();
		expect(screen.getByText('Laptop')).toBeInTheDocument();
		expect(screen.getByText('Phone')).toBeInTheDocument();
	});

	it('shows an error line when the plugin surfaces a fetch error', () => {
		render(AsusRouterDetail, { props: { data: { ...connected, error: 'Could not reach the router' } } });

		expect(screen.getByText('Could not reach the router')).toBeInTheDocument();
	});

	it('opens the settings editor with the current connection values', async () => {
		render(AsusRouterDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));

		expect(screen.getByPlaceholderText('router.asus.com')).toHaveValue('router.local');
		expect(screen.getByPlaceholderText('admin')).toHaveValue('admin');
	});

	it('tests the connection', async () => {
		asusRouterTestConnection.mockResolvedValue({ ok: true, product_id: 'RT-AX88U', error: null });

		render(AsusRouterDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Test connection'));

		expect(await screen.findByText('✓ Connected (RT-AX88U)')).toBeInTheDocument();
	});

	it('saves settings and refetches', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({ ...connected, host: 'newhost.local' });

		render(AsusRouterDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.input(screen.getByPlaceholderText('router.asus.com'), {
			target: { value: 'newhost.local' },
		});
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('asus_router', {
				host: 'newhost.local',
				ssh_port: 22,
				username: 'admin',
			}),
		);
		expect(widgetDetail).toHaveBeenCalledWith('asus_router');
	});

	it('shows an error if saving settings fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(AsusRouterDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not save the connection settings.')).toBeInTheDocument();
	});

	it('hides the edit-connection control for a non-admin', () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });

		render(AsusRouterDetail, { props: { data: connected } });

		expect(screen.queryByText('Edit connection')).not.toBeInTheDocument();
	});
});
