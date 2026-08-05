import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import WordleDetail from './WordleDetail.svelte';

function rowCells(container: HTMLElement, rowIndex: number): HTMLElement[] {
	const rows = container.querySelectorAll('.board .row');
	return Array.from(rows[rowIndex].querySelectorAll('.cell'));
}

function typeWord(word: string) {
	for (const letter of word) {
		fireEvent.keyDown(window, { key: letter });
	}
}

describe('WordleDetail', () => {
	beforeEach(() => {
		localStorage.clear();
		// Always resolves pickAnswer() to ANSWER_WORDS[0] ('ABOUT').
		vi.spyOn(Math, 'random').mockReturnValue(0);
	});

	afterEach(() => {
		vi.restoreAllMocks();
		cleanup();
	});

	it('renders the title and an empty 6x5 grid initially', () => {
		const { container } = render(WordleDetail, { props: { data: { title: 'Wordle' } } });

		expect(screen.getByRole('heading', { name: 'Wordle' })).toBeInTheDocument();
		const cells = container.querySelectorAll('.board .cell');
		expect(cells).toHaveLength(30);
		cells.forEach((cell) => {
			expect(cell.textContent).toBe('');
			expect(cell.getAttribute('data-status')).toBeNull();
		});
	});

	it('scores a submitted guess against the answer', async () => {
		const { container } = render(WordleDetail, { props: { data: { title: 'Wordle' } } });

		typeWord('ABOVE');
		await fireEvent.keyDown(window, { key: 'Enter' });

		const cells = rowCells(container, 0);
		expect(cells.map((c) => c.textContent)).toEqual(['A', 'B', 'O', 'V', 'E']);
		expect(cells.map((c) => c.getAttribute('data-status'))).toEqual([
			'correct',
			'correct',
			'correct',
			'absent',
			'absent',
		]);
	});

	it('shakes and does not advance when fewer than 5 letters are entered', async () => {
		const { container } = render(WordleDetail, { props: { data: { title: 'Wordle' } } });

		typeWord('AB');
		await fireEvent.keyDown(window, { key: 'Enter' });

		expect(container.querySelector('.board')?.classList.contains('shake')).toBe(true);
		expect(container.querySelectorAll('.board .row')).toHaveLength(6);
		rowCells(container, 0).forEach((cell) => expect(cell.getAttribute('data-status')).toBeNull());
	});

	it('shakes and does not advance when the guess is not a real word', async () => {
		const { container } = render(WordleDetail, { props: { data: { title: 'Wordle' } } });

		typeWord('ZZZZZ');
		await fireEvent.keyDown(window, { key: 'Enter' });

		expect(container.querySelector('.board')?.classList.contains('shake')).toBe(true);
		rowCells(container, 0).forEach((cell) => expect(cell.getAttribute('data-status')).toBeNull());
	});

	it('accepts letters typed via the on-screen keyboard', async () => {
		const { container } = render(WordleDetail, { props: { data: { title: 'Wordle' } } });

		for (const letter of 'ABOVE') {
			await fireEvent.click(screen.getByRole('button', { name: letter }));
		}
		await fireEvent.click(screen.getByRole('button', { name: 'ENTER' }));

		const cells = rowCells(container, 0);
		expect(cells.map((c) => c.textContent)).toEqual(['A', 'B', 'O', 'V', 'E']);
	});

	it('shows a win overlay and persists stats when the guess matches the answer', async () => {
		render(WordleDetail, { props: { data: { title: 'Wordle' } } });

		typeWord('ABOUT');
		await fireEvent.keyDown(window, { key: 'Enter' });

		expect(screen.getByText('You got it!')).toBeInTheDocument();
		const stats = JSON.parse(localStorage.getItem('wordle-stats') ?? '{}');
		expect(stats).toEqual({ played: 1, won: 1, currentStreak: 1, maxStreak: 1 });
	});

	it('shows a loss overlay revealing the answer and resets the streak after 6 wrong guesses', async () => {
		render(WordleDetail, { props: { data: { title: 'Wordle' } } });

		for (const guess of ['ABOVE', 'ABUSE', 'ACTOR', 'ACUTE', 'ADMIT', 'ADOPT']) {
			typeWord(guess);
			await fireEvent.keyDown(window, { key: 'Enter' });
		}

		expect(screen.getByText('The word was ABOUT')).toBeInTheDocument();
		const stats = JSON.parse(localStorage.getItem('wordle-stats') ?? '{}');
		expect(stats).toEqual({ played: 1, won: 0, currentStreak: 0, maxStreak: 0 });
	});

	it('resets the board on New Game', async () => {
		const { container } = render(WordleDetail, { props: { data: { title: 'Wordle' } } });

		typeWord('ABOVE');
		await fireEvent.keyDown(window, { key: 'Enter' });
		expect(rowCells(container, 0)[0].textContent).toBe('A');

		await fireEvent.click(screen.getByText('New Game'));

		expect(container.querySelectorAll('.board .row')).toHaveLength(6);
		rowCells(container, 0).forEach((cell) => {
			expect(cell.textContent).toBe('');
			expect(cell.getAttribute('data-status')).toBeNull();
		});
	});

	it('loads previously saved stats on mount', () => {
		localStorage.setItem('wordle-stats', JSON.stringify({ played: 4, won: 3, currentStreak: 2, maxStreak: 3 }));

		render(WordleDetail, { props: { data: { title: 'Wordle' } } });

		expect(screen.getByText('4')).toBeInTheDocument();
		expect(screen.getByText('2')).toBeInTheDocument();
	});
});
