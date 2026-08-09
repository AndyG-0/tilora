import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

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
	it('shows a not-connected hint', () => {
		render(AsusRouterDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — set up your router in Network Settings.')).toBeInTheDocument();
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
});
