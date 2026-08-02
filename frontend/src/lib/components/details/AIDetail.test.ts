import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { updateWidgetSettings, widgetDetail, runAiWidget } = vi.hoisted(() => ({
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
	runAiWidget: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { updateWidgetSettings, widgetDetail, runAiWidget } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'ai-insights' } } }));

import AIDetail from './AIDetail.svelte';

const baseData = {
	title: 'Daily Briefing',
	text: 'Sunny today, bring a jacket.',
	ran_at: '2026-07-24T06:30:00Z',
	history: [],
	prompt: 'Write a short daily briefing.',
	cron: '30 6 * * *',
};

describe('AIDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders the latest briefing text', () => {
		render(AIDetail, { props: { data: baseData } });

		expect(screen.getByText('Daily Briefing')).toBeInTheDocument();
		expect(screen.getByText('Sunny today, bring a jacket.')).toBeInTheDocument();
	});

	it('lets the user edit and save the prompt', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({ ...baseData, prompt: 'New prompt text' });

		render(AIDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit prompt'));
		const textarea = screen.getByLabelText('Prompt');
		expect(textarea).toHaveValue('Write a short daily briefing.');

		await fireEvent.input(textarea, { target: { value: 'New prompt text' } });
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('ai-insights', { prompt: 'New prompt text' });
		expect(widgetDetail).toHaveBeenCalledWith('ai-insights');
	});

	it('regenerates the briefing on demand', async () => {
		runAiWidget.mockResolvedValue({ ...baseData, text: 'Fresh briefing text' });

		render(AIDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Regenerate now'));

		await vi.waitFor(() => expect(runAiWidget).toHaveBeenCalledWith('ai-insights'));
		expect(await screen.findByText('Fresh briefing text')).toBeInTheDocument();
	});

	it('shows an error if regeneration fails', async () => {
		runAiWidget.mockRejectedValue(new Error('boom'));

		render(AIDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Regenerate now'));

		expect(await screen.findByText('Could not regenerate the briefing.')).toBeInTheDocument();
	});
});
