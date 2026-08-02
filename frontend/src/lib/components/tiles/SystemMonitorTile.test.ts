import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import SystemMonitorTile from './SystemMonitorTile.svelte';

describe('SystemMonitorTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(SystemMonitorTile, { props: { widgetId: 'system-monitor' } });

		expect(screen.getByText('Loading system stats…')).toBeInTheDocument();
	});

	it('renders the fetched summary', async () => {
		widgetSummary.mockResolvedValue({
			hostname: 'dashboard-host',
			cpu_percent: 12.5,
			memory_percent: 42.3,
			disk_percent: 55.0,
		});

		render(SystemMonitorTile, { props: { widgetId: 'system-monitor' } });

		expect(await screen.findByText('dashboard-host')).toBeInTheDocument();
		expect(screen.getByText('13%')).toBeInTheDocument();
		expect(screen.getByText('42%')).toBeInTheDocument();
		expect(screen.getByText('55%')).toBeInTheDocument();
	});
});
