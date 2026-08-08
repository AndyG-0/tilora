import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, updateWidgetSettings } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetDetail, updateWidgetSettings } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'discord' } } }));
vi.mock('$app/environment', () => ({ browser: true }));

import DiscordDetail from './DiscordDetail.svelte';

const baseData = {
	channel_name: 'general',
	display_mode: 'static' as const,
	message_limit: 20,
	time_window_minutes: null,
	marquee_speed_seconds: 40,
	fade_interval_seconds: 6,
	messages: [] as { id: string; author: string; avatar_url: string | null; content: string; timestamp: string }[],
};

describe('DiscordDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders the channel name header and a fallback when there are no messages', () => {
		render(DiscordDetail, { props: { data: baseData } });

		expect(screen.getByText('#general')).toBeInTheDocument();
		expect(screen.getByText('No recent messages.')).toBeInTheDocument();
	});

	it('renders messages with author, content, and timestamp', () => {
		render(DiscordDetail, {
			props: {
				data: {
					...baseData,
					messages: [
						{
							id: '1',
							author: 'Alice',
							avatar_url: null,
							content: 'Hello there',
							timestamp: '2024-01-01T00:00:00Z',
						},
					],
				},
			},
		});

		expect(screen.getByText('Alice')).toBeInTheDocument();
		expect(screen.getByText('Hello there')).toBeInTheDocument();
		expect(screen.queryByText('No recent messages.')).not.toBeInTheDocument();
	});

	it('renders Discord markdown in message content', () => {
		const { container } = render(DiscordDetail, {
			props: {
				data: {
					...baseData,
					messages: [
						{
							id: '1',
							author: 'Alice',
							avatar_url: null,
							content: 'This is **bold** text',
							timestamp: '2024-01-01T00:00:00Z',
						},
					],
				},
			},
		});

		expect(container.querySelector('.content strong')).toHaveTextContent('bold');
	});

	it('shows the marquee-specific field only in marquee mode', async () => {
		render(DiscordDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));

		expect(screen.queryByText('Scroll speed (higher = slower, 40 = normal)')).not.toBeInTheDocument();

		await fireEvent.change(screen.getByLabelText('Display mode'), { target: { value: 'marquee' } });

		expect(screen.getByText('Scroll speed (higher = slower, 40 = normal)')).toBeInTheDocument();
		expect(screen.queryByText('Seconds per message')).not.toBeInTheDocument();
	});

	it('shows the fade-specific field only in fade mode', async () => {
		render(DiscordDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.change(screen.getByLabelText('Display mode'), { target: { value: 'fade' } });

		expect(screen.getByText('Seconds per message')).toBeInTheDocument();
	});

	it('saves settings and refetches', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({ ...baseData, channel_name: 'renamed' });

		render(DiscordDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('discord', {
				display_mode: 'static',
				marquee_speed_seconds: 40,
				fade_interval_seconds: 6,
				message_limit: 20,
				time_window_minutes: null,
			}),
		);
		expect(widgetDetail).toHaveBeenCalledWith('discord');
		expect(await screen.findByText('#renamed')).toBeInTheDocument();
	});

	it('shows an error if saving settings fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(DiscordDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not update the settings.')).toBeInTheDocument();
	});
});
