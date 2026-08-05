import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

const { widgetDetail, updateWidgetSettings } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetDetail, updateWidgetSettings } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'clock' } } }));

import ClockDetail from './ClockDetail.svelte';

describe('ClockDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2024-03-15T10:30:15Z'));
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('renders the digital time in the given timezone and a hint with the timezone name', () => {
		render(ClockDetail, { props: { data: { timezone: 'UTC', style: 'digital' } } });

		expect(screen.getByText('10:30:15 AM')).toBeInTheDocument();
		expect(screen.getByText('UTC · change this in Settings')).toBeInTheDocument();
	});

	it('formats the digital time using the provided timezone, not just UTC', () => {
		render(ClockDetail, { props: { data: { timezone: 'America/Chicago', style: 'digital' } } });

		expect(screen.getByText('5:30:15 AM')).toBeInTheDocument();
	});

	it('ticks every second', async () => {
		render(ClockDetail, { props: { data: { timezone: 'UTC', style: 'digital' } } });

		expect(screen.getByText('10:30:15 AM')).toBeInTheDocument();

		await vi.advanceTimersByTimeAsync(1000);

		expect(screen.getByText('10:30:16 AM')).toBeInTheDocument();
	});

	it('renders an analog face as an svg', () => {
		render(ClockDetail, { props: { data: { timezone: 'UTC', style: 'analog' } } });

		expect(screen.getByRole('img', { name: 'Analog clock face' })).toBeInTheDocument();
	});

	it('renders a binary face as a grid of dots', () => {
		render(ClockDetail, { props: { data: { timezone: 'UTC', style: 'binary' } } });

		expect(screen.getByRole('img', { name: 'Binary clock face' })).toBeInTheDocument();
	});

	it('renders a word-clock phrase', () => {
		render(ClockDetail, { props: { data: { timezone: 'UTC', style: 'word' } } });

		expect(screen.getByText('half past ten')).toBeInTheDocument();
	});

	it('renders a matrix face with the digital time overlaid', () => {
		render(ClockDetail, { props: { data: { timezone: 'UTC', style: 'matrix' } } });

		expect(screen.getByText('10:30:15')).toBeInTheDocument();
	});

	it('saves the chosen style and refetches', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({ timezone: 'UTC', style: 'analog' });

		render(ClockDetail, { props: { data: { timezone: 'UTC', style: 'digital' } } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.change(screen.getByLabelText('Style'), { target: { value: 'analog' } });
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalledWith('clock', { style: 'analog' }));
		expect(widgetDetail).toHaveBeenCalledWith('clock');
		expect(await screen.findByRole('img', { name: 'Analog clock face' })).toBeInTheDocument();
	});

	it('shows an error if saving settings fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(ClockDetail, { props: { data: { timezone: 'UTC', style: 'digital' } } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not update the settings.')).toBeInTheDocument();
	});
});
