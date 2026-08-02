import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, updateWidgetSettings, synologyTestConnection } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
	synologyTestConnection: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetDetail, updateWidgetSettings, synologyTestConnection } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'synology' } } }));

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
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows a not-connected hint', () => {
		render(SynologyDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — tap "Edit connection" to set up Synology.')).toBeInTheDocument();
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

	it('opens the settings editor with the current connection values', async () => {
		render(SynologyDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));

		expect(screen.getByPlaceholderText('synology.local')).toHaveValue('syno.local');
		expect(screen.getByPlaceholderText('admin')).toHaveValue('admin');
	});

	it('tests the connection', async () => {
		synologyTestConnection.mockResolvedValue({ ok: true, model: 'DS920+', error: null });

		render(SynologyDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Test connection'));

		expect(await screen.findByText('✓ Connected (DS920+)')).toBeInTheDocument();
		expect(synologyTestConnection).toHaveBeenCalledWith(
			'synology',
			expect.objectContaining({ host: 'syno.local', username: 'admin' }),
		);
	});

	it('shows a failed test-connection result', async () => {
		synologyTestConnection.mockResolvedValue({ ok: false, model: null, error: 'Synology rejected credentials' });

		render(SynologyDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Test connection'));

		expect(await screen.findByText('✗ Synology rejected credentials')).toBeInTheDocument();
	});

	it('saves settings and refetches', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({ ...connected, host: 'newhost.local' });

		render(SynologyDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.input(screen.getByPlaceholderText('synology.local'), {
			target: { value: 'newhost.local' },
		});
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('synology', {
				host: 'newhost.local',
				port: 5000,
				use_https: false,
				username: 'admin',
			}),
		);
		expect(widgetDetail).toHaveBeenCalledWith('synology');
	});

	it('shows an error if saving settings fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(SynologyDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not save the connection settings.')).toBeInTheDocument();
	});
});
