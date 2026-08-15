import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

const { updateWidgetSettings } = vi.hoisted(() => ({ updateWidgetSettings: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { updateWidgetSettings } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'game2048' } } }));

import Game2048Detail from './Game2048Detail.svelte';

function scoreValues(container: HTMLElement): string[] {
	return Array.from(container.querySelectorAll('.score-box .value')).map((el) => el.textContent ?? '');
}

describe('Game2048Detail', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.clearAllMocks();
		updateWidgetSettings.mockResolvedValue({});
		// Fixed at 0: every "which empty cell" pick resolves to the first
		// empty cell in row-major order, and every "2 vs 4" roll picks 2 —
		// makes new-tile placement fully deterministic for these tests.
		vi.spyOn(Math, 'random').mockReturnValue(0);
	});

	afterEach(() => {
		vi.restoreAllMocks();
		cleanup();
	});

	it('renders the title and starts a fresh game with score 0', () => {
		const { container } = render(Game2048Detail, { props: { data: { title: '2048', best_score: 0 } } });

		expect(screen.getByRole('heading', { name: '2048' })).toBeInTheDocument();
		expect(scoreValues(container)).toEqual(['0', '0']);
		expect(screen.getAllByText('2')).toHaveLength(2);
	});

	it('merges tiles on arrow key input and updates the score', async () => {
		const { container } = render(Game2048Detail, { props: { data: { title: '2048', best_score: 0 } } });

		await fireEvent.keyDown(window, { key: 'ArrowLeft' });

		const boardCells = Array.from(container.querySelectorAll('.board .cell')).map((el) => el.textContent);
		expect(boardCells).toEqual(['4', '2', '', '', '', '', '', '', '', '', '', '', '', '', '', '']);
		expect(scoreValues(container)).toEqual(['4', '4']);
	});

	it('resets score and board on New Game', async () => {
		const { container } = render(Game2048Detail, { props: { data: { title: '2048', best_score: 0 } } });
		await fireEvent.keyDown(window, { key: 'ArrowLeft' });
		expect(scoreValues(container)[0]).toBe('4');

		await fireEvent.click(screen.getByText('New Game'));

		expect(scoreValues(container)[0]).toBe('0');
	});

	it('shows the best score handed down from the backend', () => {
		const { container } = render(Game2048Detail, { props: { data: { title: '2048', best_score: 512 } } });

		expect(scoreValues(container)[1]).toBe('512');
	});

	it('persists a new best score to the backend once the current score surpasses it', async () => {
		render(Game2048Detail, { props: { data: { title: '2048', best_score: 0 } } });

		await fireEvent.keyDown(window, { key: 'ArrowLeft' });

		expect(updateWidgetSettings).toHaveBeenCalledWith('game2048', { best_score: 4 });
	});

	it('migrates a pre-existing localStorage best score to the backend once, on mount', () => {
		localStorage.setItem('game2048-best-score', '512');

		const { container } = render(Game2048Detail, { props: { data: { title: '2048', best_score: 0 } } });

		expect(scoreValues(container)[1]).toBe('512');
		expect(updateWidgetSettings).toHaveBeenCalledWith('game2048', { best_score: 512 });
	});

	it('does not migrate localStorage once the backend already has a best score', () => {
		localStorage.setItem('game2048-best-score', '999');

		render(Game2048Detail, { props: { data: { title: '2048', best_score: 512 } } });

		expect(updateWidgetSettings).not.toHaveBeenCalled();
	});
});
