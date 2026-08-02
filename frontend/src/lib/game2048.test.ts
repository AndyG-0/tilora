import { describe, expect, it } from 'vitest';
import { addRandomTile, createEmptyBoard, hasMoves, hasWon, move, newGame, type Board } from './game2048';

describe('createEmptyBoard', () => {
	it('creates a 4x4 grid of zeros by default', () => {
		expect(createEmptyBoard()).toEqual([
			[0, 0, 0, 0],
			[0, 0, 0, 0],
			[0, 0, 0, 0],
			[0, 0, 0, 0],
		]);
	});
});

describe('addRandomTile', () => {
	it('places a 2 in the chosen empty cell when random is low', () => {
		const board = createEmptyBoard();

		// First call picks the cell index (0 -> [0,0]); second decides the
		// value (< 0.9 -> 2).
		const next = addRandomTile(board, () => 0);

		expect(next[0][0]).toBe(2);
	});

	it('places a 4 when the value roll is >= 0.9', () => {
		const board = createEmptyBoard();
		const rolls = [0, 0.95];
		let i = 0;
		const next = addRandomTile(board, () => rolls[i++]);

		expect(next[0][0]).toBe(4);
	});

	it('does not mutate the input board', () => {
		const board = createEmptyBoard();

		addRandomTile(board, () => 0);

		expect(board[0][0]).toBe(0);
	});

	it('is a no-op on a full board', () => {
		const board: Board = [
			[2, 2, 2, 2],
			[2, 2, 2, 2],
			[2, 2, 2, 2],
			[2, 2, 2, 2],
		];

		expect(addRandomTile(board, () => 0)).toEqual(board);
	});
});

describe('newGame', () => {
	it('starts with exactly two tiles on the board', () => {
		const board = newGame(() => 0.05);

		const nonZero = board.flat().filter((v) => v !== 0);
		expect(nonZero).toHaveLength(2);
	});
});

describe('move', () => {
	it('slides tiles left without merging when values differ', () => {
		const board: Board = [
			[0, 2, 0, 4],
			[0, 0, 0, 0],
			[0, 0, 0, 0],
			[0, 0, 0, 0],
		];

		const result = move(board, 'left');

		expect(result.board[0]).toEqual([2, 4, 0, 0]);
		expect(result.moved).toBe(true);
		expect(result.scoreGained).toBe(0);
	});

	it('merges equal adjacent tiles once per move, left to right', () => {
		const board: Board = [[2, 2, 2, 2]];

		const result = move(board, 'left');

		expect(result.board[0]).toEqual([4, 4, 0, 0]);
		expect(result.scoreGained).toBe(8);
	});

	it('slides and merges right', () => {
		const board: Board = [[2, 2, 0, 4]];

		const result = move(board, 'right');

		expect(result.board[0]).toEqual([0, 0, 4, 4]);
		expect(result.scoreGained).toBe(4);
	});

	it('slides and merges up a column', () => {
		const board: Board = [
			[2, 0, 0, 0],
			[0, 0, 0, 0],
			[2, 0, 0, 0],
			[4, 0, 0, 0],
		];

		const result = move(board, 'up');

		expect(result.board.map((row) => row[0])).toEqual([4, 4, 0, 0]);
	});

	it('slides and merges down a column', () => {
		const board: Board = [
			[2, 0, 0, 0],
			[0, 0, 0, 0],
			[2, 0, 0, 0],
			[4, 0, 0, 0],
		];

		const result = move(board, 'down');

		expect(result.board.map((row) => row[0])).toEqual([0, 0, 4, 4]);
	});

	it('reports moved: false when nothing changes', () => {
		const board: Board = [
			[2, 4, 8, 16],
			[0, 0, 0, 0],
			[0, 0, 0, 0],
			[0, 0, 0, 0],
		];

		const result = move(board, 'left');

		expect(result.moved).toBe(false);
		expect(result.board).toEqual(board);
	});

	it('does not double-merge a tile that already resulted from a merge', () => {
		const board: Board = [[4, 2, 2, 0]];

		const result = move(board, 'left');

		// The pre-existing 4 must not merge again with the newly-merged 4.
		expect(result.board[0]).toEqual([4, 4, 0, 0]);
		expect(result.scoreGained).toBe(4);
	});
});

describe('hasMoves', () => {
	it('is true when there is an empty cell', () => {
		const board = createEmptyBoard();

		expect(hasMoves(board)).toBe(true);
	});

	it('is true when two adjacent cells share a value, even if full', () => {
		const board: Board = [
			[2, 4, 2, 4],
			[4, 2, 4, 2],
			[2, 4, 2, 4],
			[4, 2, 4, 4],
		];

		expect(hasMoves(board)).toBe(true);
	});

	it('is false when the board is full with no adjacent equal values', () => {
		const board: Board = [
			[2, 4, 2, 4],
			[4, 2, 4, 2],
			[2, 4, 2, 4],
			[4, 2, 4, 2],
		];

		expect(hasMoves(board)).toBe(false);
	});
});

describe('hasWon', () => {
	it('is true once a tile reaches the target value', () => {
		const board = createEmptyBoard();
		board[0][0] = 2048;

		expect(hasWon(board)).toBe(true);
	});

	it('is false otherwise', () => {
		const board = createEmptyBoard();
		board[0][0] = 1024;

		expect(hasWon(board)).toBe(false);
	});
});
