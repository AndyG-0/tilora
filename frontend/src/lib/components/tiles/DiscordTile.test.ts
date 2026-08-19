import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi, afterEach } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({ widgetSummary: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));
vi.mock('$app/environment', () => ({ browser: true }));

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

		render(DiscordTile, { props: { widgetId: 'discord', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Loading messages…')).toBeInTheDocument();
	});

	it('shows an empty state when there are no recent messages', async () => {
		widgetSummary.mockResolvedValue(baseSummary());

		render(DiscordTile, { props: { widgetId: 'discord', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('#general')).toBeInTheDocument();
		expect(screen.getByText('No recent messages.')).toBeInTheDocument();
	});

	it('shows not configured state when configured is false or channel_name is empty', async () => {
		widgetSummary.mockResolvedValue(baseSummary({ configured: false, channel_name: '' }));

		render(DiscordTile, { props: { widgetId: 'discord', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Not configured')).toBeInTheDocument();
		expect(screen.queryByText('#')).not.toBeInTheDocument();
	});

	it('renders messages in static mode', async () => {
		widgetSummary.mockResolvedValue(
			baseSummary({
				messages: [
					{ id: '1', author: 'Alice', avatar_url: null, content: 'Hello there', timestamp: '2024-03-15T10:00:00Z' },
				],
			}),
		);

		render(DiscordTile, { props: { widgetId: 'discord', refreshIntervalSeconds: 60 } });

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

		render(DiscordTile, { props: { widgetId: 'discord', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('First message')).toBeInTheDocument();
	});

	it('renders Discord markdown in message content', async () => {
		widgetSummary.mockResolvedValue(
			baseSummary({
				messages: [
					{
						id: '1',
						author: 'Alice',
						avatar_url: null,
						content: 'This is **bold** text',
						timestamp: '2024-03-15T10:00:00Z',
					},
				],
			}),
		);

		const { container } = render(DiscordTile, { props: { widgetId: 'discord', refreshIntervalSeconds: 60 } });

		await screen.findByText('Alice');
		expect(container.querySelector('.content strong')).toHaveTextContent('bold');
	});

	describe('marquee mode', () => {
		afterEach(() => {
			vi.restoreAllMocks();
		});

		function mockClientHeight(height: number) {
			return vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(height);
		}

		const messages = [
			{ id: '1', author: 'Alice', avatar_url: null, content: 'First message', timestamp: '2024-03-15T10:00:00Z' },
			{ id: '2', author: 'Bob', avatar_url: null, content: 'Second message', timestamp: '2024-03-15T10:01:00Z' },
		];

		it('derives animation-duration from measured height scaled by the speed multiplier', async () => {
			mockClientHeight(400);
			widgetSummary.mockResolvedValue(baseSummary({ display_mode: 'marquee', marquee_speed_seconds: 40, messages }));

			const { container } = render(DiscordTile, { props: { widgetId: 'discord', refreshIntervalSeconds: 60 } });

			await screen.findAllByText('Alice');
			const track = container.querySelector('.marquee-track') as HTMLElement;
			// BASE_PX_PER_SECOND=40, DEFAULT_MARQUEE_SPEED_SECONDS=40 -> multiplier of 1 at the default setting.
			expect(track.style.animationDuration).toBe(`${400 / 40}s`);
		});

		it('scales the duration proportionally when marquee_speed_seconds is doubled', async () => {
			mockClientHeight(400);
			widgetSummary.mockResolvedValue(baseSummary({ display_mode: 'marquee', marquee_speed_seconds: 80, messages }));

			const { container } = render(DiscordTile, { props: { widgetId: 'discord', refreshIntervalSeconds: 60 } });

			await screen.findAllByText('Alice');
			const track = container.querySelector('.marquee-track') as HTMLElement;
			expect(track.style.animationDuration).toBe(`${(400 / 40) * 2}s`);
		});

		it('renders two copies of the message list for a seamless loop', async () => {
			mockClientHeight(400);
			widgetSummary.mockResolvedValue(baseSummary({ display_mode: 'marquee', messages }));

			render(DiscordTile, { props: { widgetId: 'discord', refreshIntervalSeconds: 60 } });

			expect(await screen.findAllByText('Alice')).toHaveLength(2);
			expect(await screen.findAllByText('Bob')).toHaveLength(2);
		});
	});
});
