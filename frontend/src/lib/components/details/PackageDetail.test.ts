import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, createPackage, removePackage } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	createPackage: vi.fn(),
	removePackage: vi.fn(),
}));
vi.mock('$lib/api', () => ({
	api: { widgetDetail, createPackage, removePackage },
}));
vi.mock('$app/state', () => ({ page: { params: { id: 'packages' } } }));

import PackageDetail from './PackageDetail.svelte';

const pkg1 = {
	id: 1,
	widget_id: 'packages',
	tracking_number: '1Z999AA1',
	carrier: 'UPS',
	label: 'Gift',
	status: 'Out for delivery',
	last_event: 'Left facility',
	eta_date: '2026-01-01',
	delivered: false,
	added_at: '2026-01-01T00:00:00+00:00',
	updated_at: '2026-01-01T00:00:00+00:00',
};

describe('PackageDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders each package, its status, and the widget title', () => {
		render(PackageDetail, {
			props: {
				data: { title: 'Packages', packages: [pkg1], arriving_today_count: 0, arriving_today: [], active_count: 1 },
			},
		});

		expect(screen.getByText('Packages')).toBeInTheDocument();
		expect(screen.getByText('Gift')).toBeInTheDocument();
		expect(screen.getByText(/UPS/)).toBeInTheDocument();
		expect(screen.getByText('Left facility')).toBeInTheDocument();
	});

	it('shows a hint when there are no packages', () => {
		render(PackageDetail, {
			props: {
				data: { title: 'Packages', packages: [], arriving_today_count: 0, arriving_today: [], active_count: 0 },
			},
		});

		expect(screen.getByText('No packages tracked yet — add a tracking number above.')).toBeInTheDocument();
	});

	it('adds a new package from the form and refetches', async () => {
		createPackage.mockResolvedValue({ ...pkg1, id: 2, tracking_number: '1Z999AA2' });
		widgetDetail.mockResolvedValue({
			title: 'Packages',
			packages: [{ ...pkg1, id: 2, tracking_number: '1Z999AA2' }],
			arriving_today_count: 0,
			arriving_today: [],
			active_count: 1,
		});

		render(PackageDetail, {
			props: {
				data: { title: 'Packages', packages: [], arriving_today_count: 0, arriving_today: [], active_count: 0 },
			},
		});

		await fireEvent.input(screen.getByPlaceholderText('Tracking number…'), { target: { value: '1Z999AA2' } });
		await fireEvent.click(screen.getByText('Add'));

		await vi.waitFor(() => expect(createPackage).toHaveBeenCalledWith('packages', '1Z999AA2', undefined));
		expect(await screen.findByText(/1Z999AA2/)).toBeInTheDocument();
	});

	it('passes the optional label to createPackage', async () => {
		createPackage.mockResolvedValue({ ...pkg1 });
		widgetDetail.mockResolvedValue({
			title: 'Packages',
			packages: [pkg1],
			arriving_today_count: 0,
			arriving_today: [],
			active_count: 1,
		});

		render(PackageDetail, {
			props: {
				data: { title: 'Packages', packages: [], arriving_today_count: 0, arriving_today: [], active_count: 0 },
			},
		});

		await fireEvent.input(screen.getByPlaceholderText('Tracking number…'), { target: { value: '1Z999AA1' } });
		await fireEvent.input(screen.getByPlaceholderText('Label (optional)…'), { target: { value: 'Gift' } });
		await fireEvent.click(screen.getByText('Add'));

		await vi.waitFor(() => expect(createPackage).toHaveBeenCalledWith('packages', '1Z999AA1', 'Gift'));
	});

	it('shows an error if adding a package fails', async () => {
		createPackage.mockRejectedValue(new Error('boom'));

		render(PackageDetail, {
			props: {
				data: { title: 'Packages', packages: [], arriving_today_count: 0, arriving_today: [], active_count: 0 },
			},
		});

		await fireEvent.input(screen.getByPlaceholderText('Tracking number…'), { target: { value: '1Z999AA1' } });
		await fireEvent.click(screen.getByText('Add'));

		expect(await screen.findByText('Could not add that tracking number.')).toBeInTheDocument();
	});

	it('removes a package and refetches', async () => {
		removePackage.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({
			title: 'Packages',
			packages: [],
			arriving_today_count: 0,
			arriving_today: [],
			active_count: 0,
		});

		render(PackageDetail, {
			props: {
				data: { title: 'Packages', packages: [pkg1], arriving_today_count: 0, arriving_today: [], active_count: 1 },
			},
		});

		await fireEvent.click(screen.getByLabelText('Remove package'));

		await vi.waitFor(() => expect(removePackage).toHaveBeenCalledWith(1));
		expect(screen.queryByText('Gift')).not.toBeInTheDocument();
	});

	it('shows an error if removing a package fails', async () => {
		removePackage.mockRejectedValue(new Error('boom'));

		render(PackageDetail, {
			props: {
				data: { title: 'Packages', packages: [pkg1], arriving_today_count: 0, arriving_today: [], active_count: 1 },
			},
		});

		await fireEvent.click(screen.getByLabelText('Remove package'));

		expect(await screen.findByText('Could not remove the package.')).toBeInTheDocument();
	});
});
