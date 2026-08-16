import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import PiholeTile from './PiholeTile.svelte';

describe('PiholeTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(PiholeTile, { props: { widgetId: 'pihole', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Loading Pi-hole…')).toBeInTheDocument();
	});

	it('shows a not-connected state', async () => {
		widgetSummary.mockResolvedValue({ connected: false, host: '', port: 80, use_https: false, has_password: false });

		render(PiholeTile, { props: { widgetId: 'pihole', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Not connected')).toBeInTheDocument();
	});

	it('renders the fetched summary', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			host: 'pi.local',
			port: 80,
			use_https: false,
			has_password: true,
			blocking_enabled: true,
			queries_today: 12345,
			blocked_today: 2345,
			percent_blocked: 19.0,
		});

		render(PiholeTile, { props: { widgetId: 'pihole', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('19%')).toBeInTheDocument();
		expect(screen.getByText('2,345 / 12,345 blocked')).toBeInTheDocument();
		expect(screen.getByText('● Enabled')).toBeInTheDocument();
	});

	it('shows a paused badge when blocking is disabled', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			host: 'pi.local',
			port: 80,
			use_https: false,
			has_password: true,
			blocking_enabled: false,
			queries_today: 100,
			blocked_today: 10,
			percent_blocked: 10,
		});

		render(PiholeTile, { props: { widgetId: 'pihole', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('⏸ Paused')).toBeInTheDocument();
	});
});
