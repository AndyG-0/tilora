import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { updateWidgetSettings, widgetDetail } = vi.hoisted(() => ({
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { updateWidgetSettings, widgetDetail } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'message' } } }));

import MessageDetail from './MessageDetail.svelte';

const baseData = { title: 'Note', text: 'Tap to edit this message.' };

describe('MessageDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders the current title and text', () => {
		render(MessageDetail, { props: { data: baseData } });

		expect(screen.getByText('Note')).toBeInTheDocument();
		expect(screen.getByText('Tap to edit this message.')).toBeInTheDocument();
	});

	it('lets the user edit and save the message', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({ title: 'Reminder', text: 'Take out the trash' });

		render(MessageDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit message'));
		const titleInput = screen.getByLabelText('Title');
		const textInput = screen.getByLabelText('Text');
		expect(titleInput).toHaveValue('Note');
		expect(textInput).toHaveValue('Tap to edit this message.');

		await fireEvent.input(titleInput, { target: { value: 'Reminder' } });
		await fireEvent.input(textInput, { target: { value: 'Take out the trash' } });
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('message', {
			title: 'Reminder',
			text: 'Take out the trash',
		});
		expect(widgetDetail).toHaveBeenCalledWith('message');
	});

	it('shows an error if saving fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(MessageDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit message'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not update the message.')).toBeInTheDocument();
	});

	it('renders markdown in the message text', () => {
		render(MessageDetail, {
			props: { data: { title: 'Note', text: '**Trash night** — put bins on the `curb`.' } },
		});

		expect(screen.getByText('Trash night', { selector: 'strong' })).toBeInTheDocument();
		expect(screen.getByText('curb', { selector: 'code' })).toBeInTheDocument();
	});

	it('shows a markdown hint under the text field while editing', async () => {
		render(MessageDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit message'));

		expect(screen.getByText('Supports basic markdown.')).toBeInTheDocument();
	});
});
