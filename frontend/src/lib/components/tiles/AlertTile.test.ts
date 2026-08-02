import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary, playChime } = vi.hoisted(() => ({
	goto: vi.fn(),
	widgetSummary: vi.fn(),
	playChime: vi.fn(),
}));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));
vi.mock('$lib/speech', () => ({ playChime }));

import AlertTile from './AlertTile.svelte';

const CRITICAL_ALERT = {
	id: 1,
	widget_id: 'alert',
	severity: 'critical' as const,
	message: 'Freeze warning',
	created_at: '2026-01-01T00:00:00+00:00',
	expires_at: null,
	dismissed: false,
};

describe('AlertTile', () => {
	beforeEach(() => {
		widgetSummary.mockReset();
		playChime.mockReset();
	});

	it('shows a no-alerts message when there are none', async () => {
		widgetSummary.mockResolvedValue({ count: 0, most_urgent: null });

		render(AlertTile, { props: { widgetId: 'alert' } });

		expect(await screen.findByText('No active alerts')).toBeInTheDocument();
	});

	it('renders the most urgent alert and a count badge', async () => {
		widgetSummary.mockResolvedValue({ count: 2, most_urgent: CRITICAL_ALERT });

		render(AlertTile, { props: { widgetId: 'alert' } });

		expect(await screen.findByText('Freeze warning')).toBeInTheDocument();
		expect(screen.getByText('2')).toBeInTheDocument();
	});

	it('does not chime on the initial load, even if an alert is already active', async () => {
		widgetSummary.mockResolvedValue({ count: 1, most_urgent: CRITICAL_ALERT });

		render(AlertTile, { props: { widgetId: 'alert' } });

		await screen.findByText('Freeze warning');
		expect(playChime).not.toHaveBeenCalled();
	});

	it('chimes when a poll sees a new alert id after the initial load', async () => {
		vi.useFakeTimers();
		try {
			widgetSummary.mockResolvedValueOnce({ count: 1, most_urgent: CRITICAL_ALERT });
			render(AlertTile, { props: { widgetId: 'alert' } });
			await vi.advanceTimersByTimeAsync(0);
			expect(widgetSummary).toHaveBeenCalledTimes(1);
			expect(playChime).not.toHaveBeenCalled();

			widgetSummary.mockResolvedValueOnce({
				count: 1,
				most_urgent: { ...CRITICAL_ALERT, id: 2, message: 'New alert' },
			});
			await vi.advanceTimersByTimeAsync(30_000);

			expect(playChime).toHaveBeenCalledTimes(1);
		} finally {
			vi.useRealTimers();
		}
	});

	it('does not chime again when the same alert id is polled repeatedly', async () => {
		vi.useFakeTimers();
		try {
			widgetSummary.mockResolvedValue({ count: 1, most_urgent: CRITICAL_ALERT });
			render(AlertTile, { props: { widgetId: 'alert' } });
			await vi.advanceTimersByTimeAsync(0);
			expect(widgetSummary).toHaveBeenCalledTimes(1);

			await vi.advanceTimersByTimeAsync(30_000);
			await vi.advanceTimersByTimeAsync(30_000);

			expect(playChime).not.toHaveBeenCalled();
		} finally {
			vi.useRealTimers();
		}
	});
});
