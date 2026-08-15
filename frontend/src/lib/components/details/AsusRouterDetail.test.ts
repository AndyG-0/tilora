import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('$env/dynamic/public', () => ({ env: { PUBLIC_API_BASE_URL: 'http://api.test' } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'asus_router' } } }));

import { api, type AsusRouterDetail as AsusRouterDetailType } from '$lib/api';
import AsusRouterDetail from './AsusRouterDetail.svelte';

const notConnected: AsusRouterDetailType = {
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

const connected: AsusRouterDetailType = {
	connected: true,
	wan_connected: true,
	client_count: 3,
	host: 'router.local',
	ssh_port: 22,
	username: 'admin',
	has_password: true,
	wan_ip: '203.0.113.5',
	clients: [
		{
			name: 'Laptop',
			ip: '192.168.1.10',
			mac: 'aa:bb:cc:dd:ee:ff',
			online: true,
			connection_type: 'wired',
			vendor: 'Apple',
			ip_type: 'static',
		},
		{
			name: "Andy's Phone",
			hostname: 'iPhone',
			alias: "Andy's Phone",
			ip: '192.168.1.11',
			mac: '28:cf:da:11:22:33',
			online: true,
			connection_type: 'wireless',
			wireless_band: '5GHz',
			rssi: -52,
			tx_rate: 866,
			rx_rate: 866,
			vendor: 'Apple',
			ip_type: 'dhcp',
		},
		{
			name: 'Smart Plug',
			ip: '192.168.1.12',
			mac: '18:fe:34:aa:bb:cc',
			online: false,
			connection_type: 'wireless',
			wireless_band: '2.4GHz',
			vendor: 'Espressif',
			ip_type: 'dhcp',
			internet_blocked: true,
		},
	],
	rx_bytes: 1_500_000,
	tx_bytes: 500_000,
};

describe('AsusRouterDetail', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it('shows a not-connected hint', () => {
		render(AsusRouterDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — set up your router in Network Settings.')).toBeInTheDocument();
	});

	it('renders WAN status and clients when connected', () => {
		render(AsusRouterDetail, { props: { data: connected } });

		expect(screen.getByText('Connected')).toBeInTheDocument();
		expect(screen.getByText('203.0.113.5')).toBeInTheDocument();
		expect(screen.getByText('Laptop')).toBeInTheDocument();
		expect(screen.getByText("Andy's Phone")).toBeInTheDocument();
		expect(screen.getByText('Smart Plug')).toBeInTheDocument();
		expect(screen.getByText('Wired')).toBeInTheDocument();
		expect(screen.getByText('5GHz')).toBeInTheDocument();
	});

	it('shows an error line when the plugin surfaces a fetch error', () => {
		render(AsusRouterDetail, { props: { data: { ...connected, error: 'Could not reach the router' } } });

		expect(screen.getByText('Could not reach the router')).toBeInTheDocument();
	});

	it('filters clients when filter pills are clicked', async () => {
		render(AsusRouterDetail, { props: { data: connected } });

		// Click Wired filter pill
		const wiredBtn = screen.getByText(/Wired \(1\)/);
		await fireEvent.click(wiredBtn);

		expect(screen.getByText('Laptop')).toBeInTheDocument();
		expect(screen.queryByText("Andy's Phone")).not.toBeInTheDocument();
		expect(screen.queryByText('Smart Plug')).not.toBeInTheDocument();

		// Click Wireless filter pill
		const wirelessBtn = screen.getByText(/Wireless \(2\)/);
		await fireEvent.click(wirelessBtn);

		expect(screen.queryByText('Laptop')).not.toBeInTheDocument();
		expect(screen.getByText("Andy's Phone")).toBeInTheDocument();
		expect(screen.getByText('Smart Plug')).toBeInTheDocument();
	});

	it('opens client modal when clicking a client card and performs actions', async () => {
		vi.spyOn(api, 'asusRouterScanPorts').mockResolvedValue({
			ip: '192.168.1.10',
			open_ports: [
				{
					port: 80,
					service: 'HTTP (Web)',
					protocol: 'tcp',
					is_web: true,
					web_url: 'http://192.168.1.10',
					title: 'Laptop Web Dashboard',
				},
				{
					port: 22,
					service: 'SSH (Secure Shell)',
					protocol: 'tcp',
					is_web: false,
				},
			],
			web_url: 'http://192.168.1.10',
			scanned_at: '2026-08-14T00:00:00Z',
		});

		vi.spyOn(api, 'asusRouterWakeOnLan').mockResolvedValue({
			ok: true,
			mac: 'aa:bb:cc:dd:ee:ff',
			message: 'WOL sent',
		});

		render(AsusRouterDetail, { props: { data: connected } });

		// Click the Laptop client row
		const laptopRow = screen.getByText('Laptop');
		await fireEvent.click(laptopRow);

		// Modal should be open
		const dialog = screen.getByRole('dialog');
		expect(dialog).toBeInTheDocument();
		expect(within(dialog).getByText('AA:BB:CC:DD:EE:FF')).toBeInTheDocument();
		expect(within(dialog).getByText('192.168.1.10')).toBeInTheDocument();

		// Trigger port scan
		const scanBtn = within(dialog).getByText('Scan Ports');
		await fireEvent.click(scanBtn);

		expect(api.asusRouterScanPorts).toHaveBeenCalledWith('asus_router', '192.168.1.10');

		// Web UI launch link and open ports should appear
		const launchBtn = await within(dialog).findByText('Launch Web UI');
		expect(launchBtn).toBeInTheDocument();
		expect(launchBtn.closest('a')).toHaveAttribute('href', 'http://192.168.1.10');
		expect(within(dialog).getByText('Laptop Web Dashboard', { exact: false })).toBeInTheDocument();

		// Send Wake-on-LAN
		const wolBtn = within(dialog).getByText('Wake on LAN');
		await fireEvent.click(wolBtn);
		expect(api.asusRouterWakeOnLan).toHaveBeenCalledWith('asus_router', 'aa:bb:cc:dd:ee:ff');

		// Close modal
		const closeBtn = within(dialog).getByLabelText('Close');
		await fireEvent.click(closeBtn);
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
	});
});
