import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({ widgetSummary: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import DiscordTile from './DiscordTile.svelte';

function baseSummary(overrides: Partial<Record<string, unknown>> = {}) {
	return {
		channel_name: 'general',
		display_mode: 'static',
		marquee_speed_seconds: 20,
		fade_interval_seconds: 5,
		messages: [],
		...overrides,
	};
}

describe('DiscordTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(DiscordTile, { props: { widgetId: 'discord' } });

		expect(screen.getByText('Loading messages…')).toBeInTheDocument();
	});

	it('shows an empty state when there are no recent messages', async () => {
		widgetSummary.mockResolvedValue(baseSummary());

		render(DiscordTile, { props: { widgetId: 'discord' } });

		expect(await screen.findByText('#general')).toBeInTheDocument();
		expect(screen.getByText('No recent messages.')).toBeInTheDocument();
	});

	it('renders messages in static mode', async () => {
		widgetSummary.mockResolvedValue(
			baseSummary({
				messages: [
					{ id: '1', author: 'Alice', avatar_url: null, content: 'Hello there', timestamp: '2024-03-15T10:00:00Z' },
				],
			}),
		);

		render(DiscordTile, { props: { widgetId: 'discord' } });

		expect(await screen.findByText('Alice')).toBeInTheDocument();
		expect(screen.getByText('Hello there')).toBeInTheDocument();
	});

	it('renders the current message in fade mode', async () => {
		widgetSummary.mockResolvedValue(
			baseSummary({
				display_mode: 'fade',
				messages: [
					{ id: '1', author: 'Alice', avatar_url: null, content: 'First message', timestamp: '2024-03-15T10:00:00Z' },
					{ id: '2', author: 'Bob', avatar_url: null, content: 'Second message', timestamp: '2024-03-15T10:01:00Z' },
				],
			}),
		);

		render(DiscordTile, { props: { widgetId: 'discord' } });

		expect(await screen.findByText('First message')).toBeInTheDocument();
	});
});
