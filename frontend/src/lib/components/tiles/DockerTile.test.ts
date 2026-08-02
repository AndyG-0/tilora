import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import DockerTile from './DockerTile.svelte';

describe('DockerTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(DockerTile, { props: { widgetId: 'docker' } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('shows a not-connected state', async () => {
		widgetSummary.mockResolvedValue({
			connected: false,
			connection: 'tcp',
			socket_path: '/var/run/docker.sock',
			host: '',
			port: 2375,
			containers: [],
			running_count: 0,
			stopped_count: 0,
			total_count: 0,
		});

		render(DockerTile, { props: { widgetId: 'docker' } });

		expect(await screen.findByText('Not connected')).toBeInTheDocument();
	});

	it('renders the fetched summary with counts and containers', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			connection: 'socket',
			socket_path: '/var/run/docker.sock',
			host: '',
			port: 2375,
			containers: [
				{ name: 'web', state: 'running', status: 'Up 2 hours' },
				{ name: 'worker', state: 'exited', status: 'Exited (0) 3 days ago' },
			],
			running_count: 1,
			stopped_count: 1,
			total_count: 2,
		});

		render(DockerTile, { props: { widgetId: 'docker' } });

		expect(await screen.findByText('1 running')).toBeInTheDocument();
		expect(screen.getByText('1 stopped')).toBeInTheDocument();
		expect(screen.getByText('web')).toBeInTheDocument();
		expect(screen.getByText('worker')).toBeInTheDocument();
	});

	it('shows an error message when the plugin surfaces a fetch error', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			connection: 'tcp',
			socket_path: '/var/run/docker.sock',
			host: 'docker.local',
			port: 2375,
			containers: [],
			running_count: 0,
			stopped_count: 0,
			total_count: 0,
			error: 'Could not reach the Docker API: connection refused',
		});

		render(DockerTile, { props: { widgetId: 'docker' } });

		expect(await screen.findByText('Could not reach the Docker API: connection refused')).toBeInTheDocument();
	});
});
