import { render, screen, fireEvent, within } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { TileReportResponse } from '$lib/api';
import { user } from '$lib/stores/user';

const { tilesReport, renameWidget, removeWidget, widgetTypes, tabs, listHouseholdUsers, addWidget, goto } = vi.hoisted(
	() => ({
		tilesReport: vi.fn(),
		renameWidget: vi.fn(),
		removeWidget: vi.fn(),
		widgetTypes: vi.fn(),
		tabs: vi.fn(),
		listHouseholdUsers: vi.fn(),
		addWidget: vi.fn(),
		goto: vi.fn(),
	}),
);

vi.mock('$lib/api', () => ({
	api: {
		tilesReport,
		renameWidget,
		removeWidget,
		widgetTypes,
		tabs,
		listHouseholdUsers,
		addWidget,
	},
}));

vi.mock('$app/navigation', () => ({ goto }));

import Page from './+page.svelte';

const mockHouseholdUsers = [
	{ id: 'admin1', name: 'Admin', avatar: null, has_pin: true, role: 'admin' as const, created_at: '2026-01-01' },
	{ id: 'user-1', name: 'Alice', avatar: null, has_pin: false, role: 'member' as const, created_at: '2026-01-01' },
];

const mockReportData: TileReportResponse = {
	summary: {
		total_tiles: 3,
		custom_tiles: 1,
		builtin_tiles: 2,
		custom_named_tiles: 1,
		hidden_tiles: 0,
		tabs_count: 2,
	},
	tiles: [
		{
			id: 'weather',
			type: 'weather',
			type_name: 'Weather',
			name: 'Home Weather',
			custom_name: 'Home Weather',
			default_name: 'Weather',
			has_custom_name: true,
			source: 'builtin',
			tab_id: 'home',
			tab_name: 'Home',
			layout: { col: 1, row: 1, colSpan: 2, rowSpan: 2 },
			size_description: 'Standard (2 × 2)',
			owner_user_id: null,
			owner_user_name: 'System / Shared',
			owner_device_id: null,
			owner_device_name: 'All Devices',
			settings_scope: 'network',
			device_overridable: false,
			refresh_interval_seconds: 300,
			network_integration: null,
			is_hidden: false,
			stats: {
				chores_active: 0,
				chores_total: 0,
				shopping_active: 0,
				shopping_total: 0,
				alerts_active: 0,
				photos_count: 0,
				packages_count: 0,
				has_custom_settings: true,
				has_user_settings: false,
				has_device_settings: false,
				has_layout_overrides: false,
			},
		},
		{
			id: 'date',
			type: 'date',
			type_name: 'Date',
			name: 'Date',
			custom_name: null,
			default_name: 'Date',
			has_custom_name: false,
			source: 'builtin',
			tab_id: 'home',
			tab_name: 'Home',
			layout: { col: 3, row: 1, colSpan: 1, rowSpan: 1 },
			size_description: 'Compact (1 × 1)',
			owner_user_id: null,
			owner_user_name: 'System / Shared',
			owner_device_id: null,
			owner_device_name: 'All Devices',
			settings_scope: 'network',
			device_overridable: false,
			refresh_interval_seconds: 300,
			network_integration: null,
			is_hidden: false,
			stats: {
				chores_active: 0,
				chores_total: 0,
				shopping_active: 0,
				shopping_total: 0,
				alerts_active: 0,
				photos_count: 0,
				packages_count: 0,
				has_custom_settings: false,
				has_user_settings: false,
				has_device_settings: false,
				has_layout_overrides: false,
			},
		},
		{
			id: 'chores-custom-1',
			type: 'chores',
			type_name: 'Chores',
			name: 'Chores',
			custom_name: null,
			default_name: 'Chores',
			has_custom_name: false,
			source: 'custom',
			tab_id: 'media',
			tab_name: 'Media',
			layout: { col: 1, row: 1, colSpan: 4, rowSpan: 1 },
			size_description: 'Banner (4 × 1)',
			owner_user_id: 'user-1',
			owner_user_name: 'Alice',
			owner_device_id: 'dev-1',
			owner_device_name: 'Kitchen Tablet',
			settings_scope: 'personal',
			device_overridable: false,
			refresh_interval_seconds: 300,
			network_integration: null,
			is_hidden: false,
			stats: {
				chores_active: 3,
				chores_total: 5,
				shopping_active: 0,
				shopping_total: 0,
				alerts_active: 0,
				photos_count: 0,
				packages_count: 0,
				has_custom_settings: false,
				has_user_settings: true,
				has_device_settings: false,
				has_layout_overrides: false,
			},
		},
	],
};

describe('Tile Reporting Page', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		user.set({ id: 'admin1', name: 'Admin', avatar: null, role: 'admin' });
		tilesReport.mockResolvedValue(mockReportData);
		widgetTypes.mockResolvedValue([{ type: 'clock', name: 'Clock', default_layout: { colSpan: 1, rowSpan: 1 } }]);
		tabs.mockResolvedValue([
			{ id: 'home', name: 'Home' },
			{ id: 'media', name: 'Media' },
		]);
		listHouseholdUsers.mockResolvedValue(mockHouseholdUsers);
		addWidget.mockResolvedValue({ id: 'clock-1' });
	});

	it('renders summary statistics and tile inventory', async () => {
		render(Page);

		expect(await screen.findByRole('heading', { name: 'Home Weather' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Date' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Chores' })).toBeInTheDocument();

		// Sizes
		expect(screen.getByText(/Standard \(2 × 2\)/)).toBeInTheDocument();
		expect(screen.getByText(/Compact \(1 × 1\)/)).toBeInTheDocument();
		expect(screen.getByText(/Banner \(4 × 1\)/)).toBeInTheDocument();

		// Custom badges
		expect(screen.getAllByText('Custom Named').length).toBeGreaterThanOrEqual(1);

		// Mouseover tooltips on summary cards
		expect(screen.getByTitle('Total count of all dashboard tiles configured in the system.')).toBeInTheDocument();
		expect(screen.getByTitle('Default tiles defined in the system dashboard configuration file.')).toBeInTheDocument();
		expect(screen.getByTitle('Tiles created dynamically by household members via the UI.')).toBeInTheDocument();
		expect(screen.getByTitle('Tiles that have a custom user-assigned display name override.')).toBeInTheDocument();
		expect(screen.getByTitle('Shared tiles hidden from view on your current device.')).toBeInTheDocument();
		expect(screen.getByTitle('Total dashboard tabs configured for organizing tiles.')).toBeInTheDocument();
	});

	it('filters tiles by search query', async () => {
		render(Page);

		await screen.findByRole('heading', { name: 'Home Weather' });
		const searchInput = screen.getByPlaceholderText(/Search tiles by name/);

		await fireEvent.input(searchInput, { target: { value: 'Alice' } });
		expect(screen.getByRole('heading', { name: 'Chores' })).toBeInTheDocument();
		expect(screen.queryByRole('heading', { name: 'Home Weather' })).not.toBeInTheDocument();
		expect(screen.queryByRole('heading', { name: 'Date' })).not.toBeInTheDocument();
	});

	it('filters tiles by source dropdown', async () => {
		render(Page);

		await screen.findByRole('heading', { name: 'Home Weather' });
		const sourceSelect = screen.getByLabelText('Filter by source');

		await fireEvent.change(sourceSelect, { target: { value: 'custom' } });
		expect(screen.getByRole('heading', { name: 'Chores' })).toBeInTheDocument();
		expect(screen.queryByRole('heading', { name: 'Home Weather' })).not.toBeInTheDocument();
	});

	it('renames a tile and updates the list', async () => {
		renameWidget.mockResolvedValue({ id: 'chores-custom-1', name: 'Kids Chores' });
		render(Page);

		await screen.findByRole('heading', { name: 'Home Weather' });
		const renameButtons = screen.getAllByText('Rename');
		await fireEvent.click(renameButtons[2]); // Chores tile rename

		const input = await screen.findByLabelText('Tile Name');
		await fireEvent.input(input, { target: { value: 'Kids Chores' } });

		const saveButton = screen.getByText('Save Name');
		await fireEvent.click(saveButton);

		await vi.waitFor(() => {
			expect(renameWidget).toHaveBeenCalledWith('chores-custom-1', 'Kids Chores');
		});
		expect(await screen.findByRole('heading', { name: 'Kids Chores' })).toBeInTheDocument();
	});

	it('deletes a custom tile and removes it from the list', async () => {
		removeWidget.mockResolvedValue({ status: 'ok' });
		render(Page);

		await screen.findByRole('heading', { name: 'Home Weather' });
		const deleteButtons = screen.getAllByText('Delete');
		await fireEvent.click(deleteButtons[0]); // Chores custom tile delete

		const confirmButton = await screen.findByRole('button', { name: 'Delete Tile' });
		await fireEvent.click(confirmButton);

		await vi.waitFor(() => {
			expect(removeWidget).toHaveBeenCalledWith('chores-custom-1');
		});
		expect(screen.queryByRole('heading', { name: 'Chores' })).not.toBeInTheDocument();
	});

	it('navigates back to dashboard when back button is clicked', async () => {
		render(Page);

		await screen.findByRole('heading', { name: 'Home Weather' });
		const backBtn = screen.getByLabelText('Back to Dashboard');
		await fireEvent.click(backBtn);

		expect(goto).toHaveBeenCalledWith('/');
	});

	it('shows the add-tile button and owner filter for admins', async () => {
		render(Page);

		await screen.findByRole('heading', { name: 'Home Weather' });
		expect(screen.getByLabelText('Add Tile')).toBeInTheDocument();
		expect(screen.getByLabelText('Filter by user')).toBeInTheDocument();
	});

	it('hides the add-tile button and owner filter for non-admins', async () => {
		user.set({ id: 'user-1', name: 'Alice', avatar: null, role: 'member' });
		render(Page);

		await screen.findByRole('heading', { name: 'Home Weather' });
		expect(screen.queryByLabelText('Add Tile')).not.toBeInTheDocument();
		expect(screen.queryByLabelText('Filter by user')).not.toBeInTheDocument();
		expect(listHouseholdUsers).not.toHaveBeenCalled();
	});

	it('filters tiles by owner dropdown', async () => {
		render(Page);

		await screen.findByRole('heading', { name: 'Home Weather' });
		const ownerSelect = await screen.findByLabelText('Filter by user');

		await fireEvent.change(ownerSelect, { target: { value: 'user-1' } });
		expect(screen.getByRole('heading', { name: 'Chores' })).toBeInTheDocument();
		expect(screen.queryByRole('heading', { name: 'Home Weather' })).not.toBeInTheDocument();
		expect(screen.queryByRole('heading', { name: 'Date' })).not.toBeInTheDocument();

		await fireEvent.change(ownerSelect, { target: { value: 'unowned' } });
		expect(screen.getByRole('heading', { name: 'Home Weather' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Date' })).toBeInTheDocument();
		expect(screen.queryByRole('heading', { name: 'Chores' })).not.toBeInTheDocument();
	});

	it('adds a tile assigned to another user and refetches the report', async () => {
		render(Page);

		await screen.findByRole('heading', { name: 'Home Weather' });
		await fireEvent.click(screen.getByLabelText('Add Tile'));

		const dialog = await screen.findByRole('dialog');
		const typeSelect = within(dialog).getByLabelText('Tile Type');
		await fireEvent.change(typeSelect, { target: { value: 'clock' } });
		const tabSelect = within(dialog).getByLabelText('Tab');
		await fireEvent.change(tabSelect, { target: { value: 'media' } });
		const ownerSelect = within(dialog).getByLabelText('Assign To');
		await fireEvent.change(ownerSelect, { target: { value: 'user-1' } });

		tilesReport.mockClear();
		await fireEvent.click(within(dialog).getByRole('button', { name: 'Add Tile' }));

		await vi.waitFor(() => {
			expect(addWidget).toHaveBeenCalledWith(
				'clock',
				expect.objectContaining({ col: 1, colSpan: 1, rowSpan: 1 }),
				'media',
				'user-1',
			);
		});
		await vi.waitFor(() => {
			expect(tilesReport).toHaveBeenCalled();
		});
	});
});
