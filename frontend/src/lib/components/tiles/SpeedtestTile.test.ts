import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import SpeedtestTile from './SpeedtestTile.svelte';

describe('SpeedtestTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(SpeedtestTile, { props: { widgetId: 'speedtest', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Loading speedtest…')).toBeInTheDocument();
	});

	it('shows a no-results state before the first run', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Speedtest',
			ran_at: null,
			download_mbps: null,
			upload_mbps: null,
			ping_ms: null,
			server_name: null,
		});

		render(SpeedtestTile, { props: { widgetId: 'speedtest', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('No results yet')).toBeInTheDocument();
	});

	it('renders the fetched summary', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Speedtest',
			ran_at: '2026-08-06T12:00:00Z',
			download_mbps: 250.4,
			upload_mbps: 25.1,
			ping_ms: 8.2,
			server_name: 'Acme ISP',
		});

		render(SpeedtestTile, { props: { widgetId: 'speedtest', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('↓ 250.4 Mbps')).toBeInTheDocument();
		expect(screen.getByText('↑ 25.1 Mbps')).toBeInTheDocument();
		expect(screen.getByText('8 ms · Acme ISP')).toBeInTheDocument();
	});
});
