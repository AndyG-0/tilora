import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, updateWidgetSettings, runAiWidget } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
	runAiWidget: vi.fn(),
}));
vi.mock('$lib/api', () => ({
	api: { widgetDetail, updateWidgetSettings, runAiWidget },
}));
vi.mock('$app/state', () => ({ page: { params: { id: 'speedtest' } } }));

import { user } from '$lib/stores/user';
import SpeedtestDetail from './SpeedtestDetail.svelte';

const noResults = {
	title: 'Speedtest',
	ran_at: null,
	download_mbps: null,
	upload_mbps: null,
	ping_ms: null,
	server_name: null,
	history: [],
	interval_minutes: 60,
};

const withResults = {
	...noResults,
	ran_at: '2026-08-06T12:00:00Z',
	download_mbps: 250.4,
	upload_mbps: 25.1,
	ping_ms: 8.2,
	server_name: 'Acme ISP',
	history: [
		{ ran_at: '2026-08-06T12:00:00Z', download_mbps: 250.4, upload_mbps: 25.1, ping_ms: 8.2, server_name: 'Acme ISP' },
		{ ran_at: '2026-08-06T11:00:00Z', download_mbps: 200.0, upload_mbps: 20.0, ping_ms: 10.0, server_name: 'Acme ISP' },
	],
};

describe('SpeedtestDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		user.set({ id: 'admin-user', name: 'Admin', avatar: null, role: 'admin' });
	});

	it('shows a no-results hint', () => {
		render(SpeedtestDetail, { props: { data: noResults } });

		expect(screen.getByText('No results yet — tap "Run now" to measure your connection.')).toBeInTheDocument();
	});

	it('renders stats and history when results exist', () => {
		render(SpeedtestDetail, { props: { data: withResults } });

		// The latest run's numbers appear both in the stat cards and as the
		// history table's first row, so assert presence rather than a single
		// unique match; the second (older) row's numbers are unique.
		expect(screen.getAllByText('250.4 Mbps').length).toBeGreaterThan(0);
		expect(screen.getByText('200.0 Mbps')).toBeInTheDocument();
		expect(screen.getByText('20.0 Mbps')).toBeInTheDocument();
		expect(screen.getByText('10 ms')).toBeInTheDocument();
		expect(screen.getAllByText('Acme ISP').length).toBeGreaterThan(0);
	});

	it('runs a speedtest now and refreshes the data', async () => {
		runAiWidget.mockResolvedValue(withResults);

		render(SpeedtestDetail, { props: { data: noResults } });

		await fireEvent.click(screen.getByText('Run now'));

		await vi.waitFor(() => expect(runAiWidget).toHaveBeenCalledWith('speedtest'));
		expect((await screen.findAllByText('250.4 Mbps')).length).toBeGreaterThan(0);
	});

	it('saves the interval from the editor', async () => {
		updateWidgetSettings.mockResolvedValue({ interval_minutes: 30 });
		widgetDetail.mockResolvedValue({ ...withResults, interval_minutes: 30 });

		render(SpeedtestDetail, { props: { data: withResults } });

		await fireEvent.click(screen.getByText('Edit interval'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(widgetDetail).toHaveBeenCalledWith('speedtest');
	});

	it('hides the edit-interval control for a non-admin', () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });

		render(SpeedtestDetail, { props: { data: withResults } });

		expect(screen.queryByText('Edit interval')).not.toBeInTheDocument();
	});
});
