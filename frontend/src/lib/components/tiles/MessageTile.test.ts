import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({ widgetSummary: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import MessageTile from './MessageTile.svelte';

describe('MessageTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(MessageTile, { props: { widgetId: 'message', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('renders the title and text when both are set', async () => {
		widgetSummary.mockResolvedValue({ title: 'Reminder', text: 'Take out the trash tonight.' });

		render(MessageTile, { props: { widgetId: 'message', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Reminder')).toBeInTheDocument();
		expect(screen.getByText('Take out the trash tonight.')).toBeInTheDocument();
	});

	it('omits the title element when the title is empty', async () => {
		widgetSummary.mockResolvedValue({ title: '', text: 'Just the message body.' });

		render(MessageTile, { props: { widgetId: 'message', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Just the message body.')).toBeInTheDocument();
		expect(screen.queryByText('Reminder')).not.toBeInTheDocument();
	});

	it('renders markdown in the message text', async () => {
		widgetSummary.mockResolvedValue({ title: 'Reminder', text: '**Trash night** — put bins on the `curb`.' });

		render(MessageTile, { props: { widgetId: 'message', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Trash night', { selector: 'strong' })).toBeInTheDocument();
		expect(screen.getByText('curb', { selector: 'code' })).toBeInTheDocument();
	});
});
