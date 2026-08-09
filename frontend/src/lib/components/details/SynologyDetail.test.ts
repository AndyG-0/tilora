import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import SynologyDetail from './SynologyDetail.svelte';

const notConnected = {
	connected: false,
	host: '',
	port: 5000,
	use_https: false,
	username: '',
	has_password: false,
	volumes: [],
	model: null,
	uptime: null,
	temperature_celsius: null,
};

const connected = {
	connected: true,
	host: 'syno.local',
	port: 5000,
	use_https: false,
	username: 'admin',
	has_password: true,
	volumes: [
		{ name: 'Volume 1', used_percent: 25.0, status: 'normal', total_bytes: 1000, used_bytes: 250 },
		{ name: 'Volume 2', used_percent: 90.0, status: 'warning', total_bytes: 2000, used_bytes: 1800 },
	],
	model: 'DS920+',
	uptime: '12:34:56',
	temperature_celsius: 42,
};

describe('SynologyDetail', () => {
	it('shows a not-connected hint', () => {
		render(SynologyDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — set up Synology in Network Settings.')).toBeInTheDocument();
	});

	it('renders volumes and system info when connected', () => {
		render(SynologyDetail, { props: { data: connected } });

		expect(screen.getByText('Volume 1')).toBeInTheDocument();
		expect(screen.getByText('Volume 2')).toBeInTheDocument();
		expect(screen.getByText('25%')).toBeInTheDocument();
		expect(screen.getByText('90%')).toBeInTheDocument();
		expect(screen.getByText('DS920+')).toBeInTheDocument();
		expect(screen.getByText('12:34:56')).toBeInTheDocument();
		expect(screen.getByText('42°C')).toBeInTheDocument();
	});

	it('shows an error line when the plugin surfaces a fetch error', () => {
		render(SynologyDetail, { props: { data: { ...connected, error: 'Could not reach the Synology NAS' } } });

		expect(screen.getByText('Could not reach the Synology NAS')).toBeInTheDocument();
	});
});
