import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, updateWidgetSettings, listContainerIntegrations } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
	listContainerIntegrations: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetDetail, updateWidgetSettings, listContainerIntegrations } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'container' } } }));

import { user } from '$lib/stores/user';
import ContainerDetail from './ContainerDetail.svelte';

const dockerNotConnected = {
	network_integration_id: 'container-docker1',
	network_integration_name: 'Docker',
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
	network_integration_id: 'container-docker1',
	network_integration_name: 'Docker',
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
	network_integration_id: 'container-podman1',
	network_integration_name: 'Podman',
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

const hosts = [
	{ id: 'container-docker1', type: 'container', name: 'Docker', settings: {} },
	{ id: 'container-podman1', type: 'container', name: 'Podman', settings: {} },
];

describe('ContainerDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		listContainerIntegrations.mockResolvedValue(hosts);
		user.set({ id: 'admin-user', name: 'Admin', avatar: null, role: 'admin' });
	});

	it('shows a not-connected hint titled for the current engine', () => {
		render(ContainerDetail, { props: { data: dockerNotConnected } });

		expect(screen.getByText('Not connected yet — set up Docker in Network Settings.')).toBeInTheDocument();
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

	it('shows the host picker for an admin with the current host selected', async () => {
		render(ContainerDetail, { props: { data: dockerConnected } });

		const select = await screen.findByLabelText('Host');
		expect(select).toHaveValue('container-docker1');
		expect(screen.getByText('Docker', { selector: 'option' })).toBeInTheDocument();
		expect(screen.getByText('Podman', { selector: 'option' })).toBeInTheDocument();
	});

	it('switches hosts and refetches detail', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue(podmanConnected);

		render(ContainerDetail, { props: { data: dockerConnected } });

		const select = await screen.findByLabelText('Host');
		await fireEvent.change(select, { target: { value: 'container-podman1' } });

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('container', { network_integration_id: 'container-podman1' }),
		);
		expect(widgetDetail).toHaveBeenCalledWith('container');
	});

	it('shows an error if switching hosts fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(ContainerDetail, { props: { data: dockerConnected } });

		const select = await screen.findByLabelText('Host');
		await fireEvent.change(select, { target: { value: 'container-podman1' } });

		expect(await screen.findByText('Could not save the connection settings.')).toBeInTheDocument();
	});

	it('hides the host picker for a non-admin', async () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });

		render(ContainerDetail, { props: { data: dockerConnected } });

		await vi.waitFor(() => expect(listContainerIntegrations).toHaveBeenCalled());
		expect(screen.queryByLabelText('Host')).not.toBeInTheDocument();
	});
});
