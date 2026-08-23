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
	bookmarks: [
		{ name: 'GitHub', url: 'https://github.com', icon: 'https://github.com/favicon.ico' },
		{ name: 'Apple', url: 'https://apple.com' },
		{ name: 'Zulip', url: 'https://zulip.org' },
	],
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

	it('filters bookmarks in real time with search query and handles clear search', async () => {
		render(BookmarksDetail, { props: { data: baseData } });

		const searchInput = screen.getByPlaceholderText('Search bookmarks…');
		expect(screen.getByText('GitHub')).toBeInTheDocument();
		expect(screen.getByText('Apple')).toBeInTheDocument();
		expect(screen.getByText('Zulip')).toBeInTheDocument();

		// Search for Apple
		await fireEvent.input(searchInput, { target: { value: 'Apple' } });
		expect(screen.getByText('Apple')).toBeInTheDocument();
		expect(screen.queryByText('GitHub')).not.toBeInTheDocument();
		expect(screen.queryByText('Zulip')).not.toBeInTheDocument();

		// Search for something non-existent
		await fireEvent.input(searchInput, { target: { value: 'NonExistent' } });
		expect(screen.getByText('No bookmarks match "NonExistent"')).toBeInTheDocument();

		// Clear search
		const clearButton = screen.getByRole('button', { name: 'Clear search' });
		await fireEvent.click(clearButton);
		expect(screen.getByText('GitHub')).toBeInTheDocument();
		expect(screen.getByText('Apple')).toBeInTheDocument();
		expect(screen.getByText('Zulip')).toBeInTheDocument();
	});

	it('toggles sort order between A-Z and Z-A in view mode', async () => {
		render(BookmarksDetail, { props: { data: baseData } });

		const sortBtn = screen.getByRole('button', { name: 'Sort A–Z' });
		await fireEvent.click(sortBtn); // sorts A-Z: Apple, GitHub, Zulip

		let items = screen.getAllByRole('link');
		expect(items[0]).toHaveTextContent('Apple');
		expect(items[1]).toHaveTextContent('GitHub');
		expect(items[2]).toHaveTextContent('Zulip');

		await fireEvent.click(screen.getByRole('button', { name: 'Sort Z–A' })); // sorts Z-A: Zulip, GitHub, Apple
		items = screen.getAllByRole('link');
		expect(items[0]).toHaveTextContent('Zulip');
		expect(items[1]).toHaveTextContent('GitHub');
		expect(items[2]).toHaveTextContent('Apple');
	});

	it('opens the editor prefilled with the current bookmarks', async () => {
		render(BookmarksDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit bookmarks'));

		const nameInputs = screen.getAllByPlaceholderText('Name');
		expect(nameInputs[0]).toHaveValue('GitHub');
		expect(nameInputs[1]).toHaveValue('Apple');
		expect(nameInputs[2]).toHaveValue('Zulip');
	});

	it('sorts bookmarks alphabetically in the editor', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue(baseData);

		render(BookmarksDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit bookmarks'));
		await fireEvent.click(screen.getByText('Sort A–Z'));

		const nameInputs = screen.getAllByPlaceholderText('Name');
		expect(nameInputs[0]).toHaveValue('Apple');
		expect(nameInputs[1]).toHaveValue('GitHub');
		expect(nameInputs[2]).toHaveValue('Zulip');

		await fireEvent.click(screen.getByText('Sort Z–A'));
		const reversedInputs = screen.getAllByPlaceholderText('Name');
		expect(reversedInputs[0]).toHaveValue('Zulip');
		expect(reversedInputs[1]).toHaveValue('GitHub');
		expect(reversedInputs[2]).toHaveValue('Apple');
	});

	it('reorders bookmarks using move up and move down buttons', async () => {
		render(BookmarksDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit bookmarks'));

		// Move first item (GitHub) down
		const downButtons = screen.getAllByLabelText('Move down');
		await fireEvent.click(downButtons[0]);

		let nameInputs = screen.getAllByPlaceholderText('Name');
		expect(nameInputs[0]).toHaveValue('Apple');
		expect(nameInputs[1]).toHaveValue('GitHub');
		expect(nameInputs[2]).toHaveValue('Zulip');

		// Move third item (Zulip) up
		const upButtons = screen.getAllByLabelText('Move up');
		await fireEvent.click(upButtons[2]);

		nameInputs = screen.getAllByPlaceholderText('Name');
		expect(nameInputs[0]).toHaveValue('Apple');
		expect(nameInputs[1]).toHaveValue('Zulip');
		expect(nameInputs[2]).toHaveValue('GitHub');
	});

	it('reorders bookmarks using drag and drop handlers', async () => {
		render(BookmarksDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit bookmarks'));

		const rows = document.querySelectorAll('.bookmark-row');
		expect(rows).toHaveLength(3);

		// Drag index 0 (GitHub) and drop onto index 2 (Zulip)
		await fireEvent.dragStart(rows[0], { dataTransfer: { setData: vi.fn(), effectAllowed: 'move' } });
		await fireEvent.dragOver(rows[2], {
			clientY: 300,
			currentTarget: { getBoundingClientRect: () => ({ top: 200, height: 50 }) },
			dataTransfer: { dropEffect: 'move' },
		});
		await fireEvent.drop(rows[2]);

		const nameInputs = screen.getAllByPlaceholderText('Name');
		expect(nameInputs[0]).toHaveValue('Apple');
	});

	it('imports bookmarks from an HTML bookmark file and supports appending/replacing', async () => {
		render(BookmarksDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit bookmarks'));

		const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
		expect(fileInput).toBeInTheDocument();

		const htmlContent = `
<!DOCTYPE NETSCAPE-Bookmark-file-1>
<DL><p>
    <DT><A HREF="https://svelte.dev">Svelte</A>
    <DT><A HREF="https://vite.dev">Vite</A>
</DL><p>
`;
		const file = new File([htmlContent], 'bookmarks.html', { type: 'text/html' });

		await fireEvent.change(fileInput, { target: { files: [file] } });

		// Since bookmarkInputs > 0, import prompt is displayed
		expect(await screen.findByText(/Found 2 bookmarks/i)).toBeInTheDocument();

		// Click "Add to existing"
		await fireEvent.click(screen.getByText('Add to existing'));

		const nameInputs = screen.getAllByPlaceholderText('Name');
		expect(nameInputs).toHaveLength(5);
		expect(nameInputs[3]).toHaveValue('Svelte');
		expect(nameInputs[4]).toHaveValue('Vite');
	});

	it('imports bookmarks in replace mode', async () => {
		render(BookmarksDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit bookmarks'));

		const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
		const jsonContent = JSON.stringify([{ name: 'Solo', url: 'https://solo.com' }]);
		const file = new File([jsonContent], 'bookmarks.json', { type: 'application/json' });

		await fireEvent.change(fileInput, { target: { files: [file] } });
		await fireEvent.click(await screen.findByText('Replace all'));

		const nameInputs = screen.getAllByPlaceholderText('Name');
		expect(nameInputs).toHaveLength(1);
		expect(nameInputs[0]).toHaveValue('Solo');
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
		expect(nameInputs).toHaveLength(4);
		await fireEvent.input(nameInputs[3], { target: { value: 'Example' } });
		await fireEvent.input(urlInputs[3], { target: { value: 'https://example.com' } });

		const titleInput = screen.getByDisplayValue('Bookmarks');
		await fireEvent.input(titleInput, { target: { value: 'Links' } });

		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('bookmarks', {
			title: 'Links',
			bookmarks: [
				{ name: 'GitHub', url: 'https://github.com', icon: 'https://github.com/favicon.ico' },
				{ name: 'Apple', url: 'https://apple.com', icon: undefined },
				{ name: 'Zulip', url: 'https://zulip.org', icon: undefined },
				{ name: 'Example', url: 'https://example.com', icon: undefined },
			],
		});
		expect(widgetDetail).toHaveBeenCalledWith('bookmarks');
	});

	it('drops blank bookmark rows when saving', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue(baseData);

		render(BookmarksDetail, {
			props: { data: { title: 'Bookmarks', bookmarks: [{ name: 'GitHub', url: 'https://github.com' }] } },
		});

		await fireEvent.click(screen.getByText('Edit bookmarks'));
		await fireEvent.click(screen.getByText('+ Add bookmark'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('bookmarks', {
			title: 'Bookmarks',
			bookmarks: [{ name: 'GitHub', url: 'https://github.com', icon: undefined }],
		});
	});

	it('removes a bookmark row when its remove button is clicked', async () => {
		render(BookmarksDetail, {
			props: { data: { title: 'Bookmarks', bookmarks: [{ name: 'GitHub', url: 'https://github.com' }] } },
		});

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
