import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, updateWidgetSettings } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetDetail, updateWidgetSettings } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'container' } } }));

import { user } from '$lib/stores/user';
import ContainerDetail from './ContainerDetail.svelte';

const dockerNotConnected = {
	engine: 'docker' as const,
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

const dockerConnected = {
	engine: 'docker' as const,
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

const podmanConnected = {
	engine: 'podman' as const,
	connected: true,
	connection: 'socket',
	socket_path: '/run/podman/podman.sock',
	host: '',
	port: 8080,
	containers: [{ id: 'c1', name: 'web', image: 'nginx:latest', status: 'Up 2 hours', state: 'running' }],
	running_count: 1,
	stopped_count: 0,
	total_count: 1,
};

describe('ContainerDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		user.set({ id: 'admin-user', name: 'Admin', avatar: null, role: 'admin' });
	});

	it('shows a not-connected hint titled for the current engine', () => {
		render(ContainerDetail, { props: { data: dockerNotConnected } });

		expect(screen.getByText('Not connected yet — tap "Edit connection" to set up Docker.')).toBeInTheDocument();
	});

	it('renders container counts and the container list when connected', () => {
		render(ContainerDetail, { props: { data: dockerConnected } });

		expect(screen.getByText('web')).toBeInTheDocument();
		expect(screen.getByText('worker')).toBeInTheDocument();
		expect(screen.getByText('nginx:latest')).toBeInTheDocument();
		expect(screen.getByText('Up 2 hours')).toBeInTheDocument();
	});

	it('shows an error line when the plugin surfaces a fetch error', () => {
		render(ContainerDetail, { props: { data: { ...dockerConnected, error: 'Could not reach the container API' } } });

		expect(screen.getByText('Could not reach the container API')).toBeInTheDocument();
	});

	it('shows a no-containers hint when connected with none', () => {
		render(ContainerDetail, {
			props: { data: { ...podmanConnected, containers: [], running_count: 0, total_count: 0 } },
		});

		expect(screen.getByText('No containers found.')).toBeInTheDocument();
	});

	it('opens the settings editor with the current connection values', async () => {
		render(ContainerDetail, { props: { data: dockerConnected } });

		await fireEvent.click(screen.getByText('Edit connection'));

		expect(screen.getByPlaceholderText('docker.local')).toHaveValue('docker.local');
	});

	it('saves settings including the engine and refetches', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({ ...dockerConnected, host: 'newhost.local' });

		render(ContainerDetail, { props: { data: dockerConnected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.input(screen.getByPlaceholderText('docker.local'), {
			target: { value: 'newhost.local' },
		});
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('container', {
				engine: 'docker',
				connection: 'tcp',
				socket_path: '/var/run/docker.sock',
				host: 'newhost.local',
				port: 2375,
			}),
		);
		expect(widgetDetail).toHaveBeenCalledWith('container');
	});

	it('shows an error if saving settings fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(ContainerDetail, { props: { data: dockerConnected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not save the connection settings.')).toBeInTheDocument();
	});

	it('hides the edit-connection control for a non-admin', () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });

		render(ContainerDetail, { props: { data: dockerConnected } });

		expect(screen.queryByText('Edit connection')).not.toBeInTheDocument();
	});

	it('switching the engine re-prefills the socket path and port to that engine defaults', async () => {
		render(ContainerDetail, {
			props: { data: { ...dockerConnected, connection: 'socket', host: '' } },
		});

		await fireEvent.click(screen.getByText('Edit connection'));
		expect(screen.getByPlaceholderText('/var/run/docker.sock')).toHaveValue('/var/run/docker.sock');

		await fireEvent.change(screen.getByDisplayValue('Docker'), { target: { value: 'podman' } });

		expect(screen.getByPlaceholderText('/run/podman/podman.sock')).toHaveValue('/run/podman/podman.sock');
	});

	it('does not clobber a socket path the user already customized when switching engines', async () => {
		render(ContainerDetail, {
			props: { data: { ...dockerConnected, connection: 'socket', host: '' } },
		});

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.input(screen.getByPlaceholderText('/var/run/docker.sock'), {
			target: { value: '/custom/docker.sock' },
		});

		await fireEvent.change(screen.getByDisplayValue('Docker'), { target: { value: 'podman' } });

		expect(screen.getByPlaceholderText('/run/podman/podman.sock')).toHaveValue('/custom/docker.sock');
	});

	it('saves settings for the podman engine', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue(podmanConnected);

		render(ContainerDetail, { props: { data: podmanConnected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('container', {
				engine: 'podman',
				connection: 'socket',
				socket_path: '/run/podman/podman.sock',
				host: '',
				port: 8080,
			}),
		);
		expect(widgetDetail).toHaveBeenCalledWith('container');
	});
});
