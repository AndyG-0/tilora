import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail } = vi.hoisted(() => ({ widgetDetail: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetDetail } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'system-monitor' } } }));

import SystemMonitorDetail from './SystemMonitorDetail.svelte';

const initialData = {
	hostname: 'dashboard-host',
	cpu_percent: 12.5,
	cpu_count: 4,
	cpu_per_core: [10.0, 15.0, 12.0, 13.0],
	memory_percent: 42.3,
	memory_used_gb: 6.7,
	memory_total_gb: 16.0,
	disk_percent: 55.0,
	disk_used_gb: 100.0,
	disk_total_gb: 200.0,
	network_sent_gb: 1.2,
	network_recv_gb: 3.4,
	uptime_seconds: 90_061,
	load_average: [0.5, 0.7, 0.9] as [number, number, number],
};

describe('SystemMonitorDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders the seeded stats', () => {
		const { container } = render(SystemMonitorDetail, { props: { data: initialData } });

		expect(screen.getByRole('heading', { name: 'dashboard-host' })).toBeInTheDocument();
		const statValues = Array.from(container.querySelectorAll('.stats .value')).map((el) => el.textContent);
		expect(statValues).toEqual(['13%', '42%', '55%', '1d 1h']);
		expect(screen.getByText('↑ 1.2 GB sent · ↓ 3.4 GB received')).toBeInTheDocument();
		expect(screen.getByText('Load average: 0.50 / 0.70 / 0.90 (1m / 5m / 15m)')).toBeInTheDocument();
	});

	it('polls for updated stats', async () => {
		vi.useFakeTimers();
		widgetDetail.mockResolvedValue({ ...initialData, cpu_percent: 99 });

		render(SystemMonitorDetail, { props: { data: initialData } });

		await vi.advanceTimersByTimeAsync(10_000);

		expect(await screen.findByText('99%')).toBeInTheDocument();
		vi.useRealTimers();
	});
});
