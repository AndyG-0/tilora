import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { updateWidgetSettings, widgetDetail } = vi.hoisted(() => ({
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { updateWidgetSettings, widgetDetail } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'bookmarks' } } }));

import BookmarksDetail from './BookmarksDetail.svelte';

const baseData = {
	title: 'Bookmarks',
	bookmarks: [{ name: 'GitHub', url: 'https://github.com', icon: 'https://github.com/favicon.ico' }],
};

describe('BookmarksDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders the title and each bookmark as a link', () => {
		render(BookmarksDetail, { props: { data: baseData } });

		expect(screen.getByText('Bookmarks')).toBeInTheDocument();
		const link = screen.getByText('GitHub').closest('a');
		expect(link).toHaveAttribute('href', 'https://github.com');
		expect(link).toHaveAttribute('target', '_blank');
		expect(link).toHaveAttribute('rel', 'noreferrer');
	});

	it('shows a hint when no bookmarks are configured', () => {
		render(BookmarksDetail, { props: { data: { ...baseData, bookmarks: [] } } });

		expect(screen.getByText('No bookmarks configured yet — tap "Edit bookmarks" to add one.')).toBeInTheDocument();
	});

	it('opens the editor prefilled with the current bookmarks', async () => {
		render(BookmarksDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit bookmarks'));

		expect(screen.getByPlaceholderText('Name')).toHaveValue('GitHub');
		expect(screen.getByPlaceholderText('URL')).toHaveValue('https://github.com');
		expect(screen.getByPlaceholderText('Icon URL (optional)')).toHaveValue('https://github.com/favicon.ico');
	});

	it('lets the user add a bookmark row, edit settings, and save', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({
			...baseData,
			title: 'Links',
			bookmarks: [
				{ name: 'GitHub', url: 'https://github.com', icon: 'https://github.com/favicon.ico' },
				{ name: 'Example', url: 'https://example.com' },
			],
		});

		render(BookmarksDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit bookmarks'));
		await fireEvent.click(screen.getByText('+ Add bookmark'));

		const nameInputs = screen.getAllByPlaceholderText('Name');
		const urlInputs = screen.getAllByPlaceholderText('URL');
		expect(nameInputs).toHaveLength(2);
		await fireEvent.input(nameInputs[1], { target: { value: 'Example' } });
		await fireEvent.input(urlInputs[1], { target: { value: 'https://example.com' } });

		const titleInput = screen.getByDisplayValue('Bookmarks');
		await fireEvent.input(titleInput, { target: { value: 'Links' } });

		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('bookmarks', {
			title: 'Links',
			bookmarks: [
				{ name: 'GitHub', url: 'https://github.com', icon: 'https://github.com/favicon.ico' },
				{ name: 'Example', url: 'https://example.com', icon: undefined },
			],
		});
		expect(widgetDetail).toHaveBeenCalledWith('bookmarks');
	});

	it('drops blank bookmark rows when saving', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue(baseData);

		render(BookmarksDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit bookmarks'));
		await fireEvent.click(screen.getByText('+ Add bookmark'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('bookmarks', {
			title: 'Bookmarks',
			bookmarks: [{ name: 'GitHub', url: 'https://github.com', icon: 'https://github.com/favicon.ico' }],
		});
	});

	it('removes a bookmark row when its remove button is clicked', async () => {
		render(BookmarksDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit bookmarks'));
		expect(screen.getAllByPlaceholderText('Name')).toHaveLength(1);

		await fireEvent.click(screen.getByLabelText('Remove bookmark'));

		expect(screen.queryByPlaceholderText('Name')).not.toBeInTheDocument();
		expect(screen.getByText('No bookmarks yet — add one below.')).toBeInTheDocument();
	});

	it('shows an error if saving fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(BookmarksDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit bookmarks'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not update the bookmarks.')).toBeInTheDocument();
	});
});
