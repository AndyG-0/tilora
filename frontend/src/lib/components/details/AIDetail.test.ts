import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { updateWidgetSettings, widgetDetail, runAiWidget, assistantTopics } = vi.hoisted(() => ({
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
	runAiWidget: vi.fn(),
	assistantTopics: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { updateWidgetSettings, widgetDetail, runAiWidget, assistantTopics } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'ai-insights' } } }));

import AIDetail from './AIDetail.svelte';

const baseData = {
	title: 'Daily Briefing',
	text: 'Sunny today, bring a jacket.',
	ran_at: '2026-07-24T06:30:00Z',
	history: [],
	prompt: 'Write a short daily briefing.',
	cron: '30 6 * * *',
	topics: [],
	language: 'en',
};

describe('AIDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		assistantTopics.mockResolvedValue([
			{ id: 'calendar', name: 'Calendar' },
			{ id: 'weather', name: 'Weather' },
		]);
	});

	it('renders the latest briefing text', () => {
		render(AIDetail, { props: { data: baseData } });

		expect(screen.getByText('Daily Briefing')).toBeInTheDocument();
		expect(screen.getByText('Sunny today, bring a jacket.')).toBeInTheDocument();
	});

	it('renders markdown in the briefing and history text', () => {
		render(AIDetail, {
			props: {
				data: {
					...baseData,
					text: '**Sunny** today.',
					history: [
						{ ran_at: '2026-07-24T06:30:00Z', text: '**Sunny** today.' },
						{ ran_at: '2026-07-23T06:30:00Z', text: 'Cloudy with *light* rain.' },
					],
				},
			},
		});

		expect(screen.getByText('Sunny', { selector: 'strong' })).toBeInTheDocument();
		expect(screen.getByText('light', { selector: 'em' })).toBeInTheDocument();
	});

	it('lets the user edit and save the prompt', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({ ...baseData, prompt: 'New prompt text' });

		render(AIDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit prompt'));
		const textarea = await screen.findByLabelText('Prompt');
		expect(textarea).toHaveValue('Write a short daily briefing.');

		await fireEvent.input(textarea, { target: { value: 'New prompt text' } });
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('ai-insights', {
			prompt: 'New prompt text',
			topics: [],
			language: 'en',
		});
		expect(widgetDetail).toHaveBeenCalledWith('ai-insights');
	});

	it('lets the user change the response language', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({ ...baseData, language: 'es' });

		render(AIDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit prompt'));
		const languageSelect = await screen.findByLabelText('Response language');
		expect(languageSelect).toHaveValue('en');

		await fireEvent.change(languageSelect, { target: { value: 'es' } });
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('ai-insights', {
			prompt: 'Write a short daily briefing.',
			topics: [],
			language: 'es',
		});
	});

	it('lets the user pick topics to cover in the summary', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({ ...baseData, topics: ['calendar'] });

		render(AIDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit prompt'));
		const calendarCheckbox = await screen.findByLabelText('Calendar');
		expect(calendarCheckbox).not.toBeChecked();

		await fireEvent.click(calendarCheckbox);
		expect(calendarCheckbox).toBeChecked();

		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('ai-insights', {
			prompt: 'Write a short daily briefing.',
			topics: ['calendar'],
			language: 'en',
		});
	});

	it('preselects the widget’s already-configured topics', async () => {
		render(AIDetail, { props: { data: { ...baseData, topics: ['weather'] } } });

		await fireEvent.click(screen.getByText('Edit prompt'));

		expect(await screen.findByLabelText('Weather')).toBeChecked();
		expect(screen.getByLabelText('Calendar')).not.toBeChecked();
	});

	it('renders whatever disambiguated name the backend sends for a topic, verbatim', async () => {
		assistantTopics.mockResolvedValue([{ id: 'weather-b', name: 'Weather (Chicago, IL) (2)' }]);

		render(AIDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit prompt'));

		expect(await screen.findByLabelText('Weather (Chicago, IL) (2)')).toBeInTheDocument();
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
