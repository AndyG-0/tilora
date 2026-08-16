import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({
	widgetSummary: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import PackageTile from './PackageTile.svelte';

const PACKAGE = {
	id: 1,
	widget_id: 'packages',
	tracking_number: '1Z999AA1',
	carrier: 'UPS',
	label: 'Gift',
	status: 'Out for delivery',
	last_event: 'Out for delivery',
	eta_date: '2026-01-01',
	delivered: false,
	added_at: '2026-01-01T00:00:00+00:00',
	updated_at: '2026-01-01T00:00:00+00:00',
};

describe('PackageTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(PackageTile, { props: { widgetId: 'packages', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('renders packages arriving today with a count badge', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Packages',
			arriving_today_count: 1,
			arriving_today: [PACKAGE],
			active_count: 1,
		});

		render(PackageTile, { props: { widgetId: 'packages', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Gift')).toBeInTheDocument();
		expect(screen.getByText('Packages')).toBeInTheDocument();
		expect(screen.getByText('1')).toBeInTheDocument();
		expect(screen.getByText('UPS')).toBeInTheDocument();
	});

	it('falls back to the tracking number when a package has no label', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Packages',
			arriving_today_count: 1,
			arriving_today: [{ ...PACKAGE, label: null }],
			active_count: 1,
		});

		render(PackageTile, { props: { widgetId: 'packages', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('1Z999AA1')).toBeInTheDocument();
	});

	it('shows an in-transit summary when nothing is arriving today', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Packages',
			arriving_today_count: 0,
			arriving_today: [],
			active_count: 2,
		});

		render(PackageTile, { props: { widgetId: 'packages', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('2 on the way')).toBeInTheDocument();
	});

	it('shows an empty state when nothing is tracked', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Packages',
			arriving_today_count: 0,
			arriving_today: [],
			active_count: 0,
		});

		render(PackageTile, { props: { widgetId: 'packages', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Nothing tracked')).toBeInTheDocument();
	});
});
