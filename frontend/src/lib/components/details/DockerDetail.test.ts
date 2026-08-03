import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, updateWidgetSettings } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetDetail, updateWidgetSettings } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'docker' } } }));

import { user } from '$lib/stores/user';
import DockerDetail from './DockerDetail.svelte';

const notConnected = {
	connected: false,
	connection: 'socket',
	socket_path: '/var/run/docker.sock',
	host: '',
	port: 2375,
	containers: [],
	running_count: 0,
	stopped_count: 0,
	total_count: 0,
};

const connected = {
	connected: true,
	connection: 'tcp',
	socket_path: '/var/run/docker.sock',
	host: 'docker.local',
	port: 2375,
	containers: [
		{ id: 'abc123456789', name: 'web', image: 'nginx:latest', state: 'running', status: 'Up 2 hours' },
		{ id: 'def123456789', name: 'worker', image: 'myapp:latest', state: 'exited', status: 'Exited (0) 3 days ago' },
	],
	running_count: 1,
	stopped_count: 1,
	total_count: 2,
};

describe('DockerDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		user.set({ id: 'admin-user', name: 'Admin', avatar: null, role: 'admin' });
	});

	it('shows a not-connected hint', () => {
		render(DockerDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — tap "Edit connection" to set up Docker.')).toBeInTheDocument();
	});

	it('renders container counts and the container list when connected', () => {
		render(DockerDetail, { props: { data: connected } });

		expect(screen.getByText('web')).toBeInTheDocument();
		expect(screen.getByText('worker')).toBeInTheDocument();
		expect(screen.getByText('nginx:latest')).toBeInTheDocument();
		expect(screen.getByText('Up 2 hours')).toBeInTheDocument();
	});

	it('shows an error line when the plugin surfaces a fetch error', () => {
		render(DockerDetail, { props: { data: { ...connected, error: 'Could not reach the Docker API' } } });

		expect(screen.getByText('Could not reach the Docker API')).toBeInTheDocument();
	});

	it('opens the settings editor with the current connection values', async () => {
		render(DockerDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));

		expect(screen.getByPlaceholderText('docker.local')).toHaveValue('docker.local');
	});

	it('saves settings and refetches', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({ ...connected, host: 'newhost.local' });

		render(DockerDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.input(screen.getByPlaceholderText('docker.local'), {
			target: { value: 'newhost.local' },
		});
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('docker', {
				connection: 'tcp',
				socket_path: '/var/run/docker.sock',
				host: 'newhost.local',
				port: 2375,
			}),
		);
		expect(widgetDetail).toHaveBeenCalledWith('docker');
	});

	it('shows an error if saving settings fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(DockerDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not save the connection settings.')).toBeInTheDocument();
	});

	it('hides the edit-connection control for a non-admin', () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });

		render(DockerDetail, { props: { data: connected } });

		expect(screen.queryByText('Edit connection')).not.toBeInTheDocument();
	});
});
