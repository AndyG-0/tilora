import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, updateWidgetSettings } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetDetail, updateWidgetSettings } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'podman' } } }));

import { user } from '$lib/stores/user';
import PodmanDetail from './PodmanDetail.svelte';

const notConnected = {
	connected: false,
	connection: 'socket' as const,
	socket_path: '/run/podman/podman.sock',
	host: '',
	port: 8080,
	containers: [],
	running_count: 0,
	stopped_count: 0,
	total_count: 0,
};

const connected = {
	...notConnected,
	connected: true,
	containers: [{ id: 'c1', name: 'web', image: 'nginx:latest', status: 'Up 2 hours', state: 'running' }],
	running_count: 1,
	stopped_count: 0,
	total_count: 1,
};

describe('PodmanDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		user.set({ id: 'admin-user', name: 'Admin', avatar: null, role: 'admin' });
	});

	it('shows a not-connected hint', () => {
		render(PodmanDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — tap "Edit connection" to set up Podman.')).toBeInTheDocument();
	});

	it('renders counts and containers when connected', () => {
		render(PodmanDetail, { props: { data: connected } });

		expect(screen.getByText('web')).toBeInTheDocument();
		expect(screen.getByText('nginx:latest')).toBeInTheDocument();
		expect(screen.getByText('Up 2 hours')).toBeInTheDocument();
	});

	it('shows an error line when the plugin surfaces a fetch error', () => {
		render(PodmanDetail, { props: { data: { ...connected, error: 'Could not reach the Podman API' } } });

		expect(screen.getByText('Could not reach the Podman API')).toBeInTheDocument();
	});

	it('shows a no-containers hint when connected with none', () => {
		render(PodmanDetail, { props: { data: { ...connected, containers: [], running_count: 0, total_count: 0 } } });

		expect(screen.getByText('No containers found.')).toBeInTheDocument();
	});

	it('saves connection settings from the editor', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue(connected);

		render(PodmanDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('podman', {
				connection: 'socket',
				socket_path: '/run/podman/podman.sock',
				host: '',
				port: 8080,
			}),
		);
		expect(widgetDetail).toHaveBeenCalledWith('podman');
	});

	it('shows an error if saving settings fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(PodmanDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not save the connection settings.')).toBeInTheDocument();
	});

	it('hides the edit-connection control for a non-admin', () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });

		render(PodmanDetail, { props: { data: connected } });

		expect(screen.queryByText('Edit connection')).not.toBeInTheDocument();
	});
});
