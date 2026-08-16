import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({ widgetSummary: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import AITile from './AITile.svelte';

describe('AITile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(AITile, { props: { widgetId: 'ai-insights', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Loading briefing…')).toBeInTheDocument();
	});

	it('renders the fetched title and text', async () => {
		widgetSummary.mockResolvedValue({
			title: "Today's briefing",
			text: 'Traffic is light and the weather looks clear all day.',
			ran_at: '2024-03-15T06:30:00Z',
		});

		render(AITile, { props: { widgetId: 'ai-insights', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText("Today's briefing")).toBeInTheDocument();
		expect(screen.getByText('Traffic is light and the weather looks clear all day.')).toBeInTheDocument();
	});

	it('renders markdown in the briefing text', async () => {
		widgetSummary.mockResolvedValue({
			title: "Today's briefing",
			text: '**Rain** expected after `noon`.',
			ran_at: '2024-03-15T06:30:00Z',
		});

		render(AITile, { props: { widgetId: 'ai-insights', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Rain', { selector: 'strong' })).toBeInTheDocument();
		expect(screen.getByText('noon', { selector: 'code' })).toBeInTheDocument();
	});

	it('renders scrollable container for multi-paragraph content', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Detailed Insights',
			text: '### Overview\n\nFirst paragraph of detailed insight.\n\n> Note this quote\n\nSecond paragraph.',
			ran_at: '2024-03-15T06:30:00Z',
		});

		const { container } = render(AITile, { props: { widgetId: 'ai-insights', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Detailed Insights')).toBeInTheDocument();
		expect(screen.getByText('Overview', { selector: 'h3' })).toBeInTheDocument();
		expect(screen.getByText('First paragraph of detailed insight.')).toBeInTheDocument();
		expect(container.querySelector('.scroll-wrap')).toBeInTheDocument();
		expect(container.querySelector('.text')).toBeInTheDocument();
	});
});
