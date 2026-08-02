// Pure 2048 game engine — no DOM/Svelte dependencies, so it's directly
// unit-testable and reusable between the tile preview and the full board.

export type Board = number[][];
export type Direction = 'up' | 'down' | 'left' | 'right';

export const BOARD_SIZE = 4;
export const WIN_VALUE = 2048;

export function createEmptyBoard(size: number = BOARD_SIZE): Board {
	return Array.from({ length: size }, () => Array(size).fill(0));
}

function emptyCells(board: Board): [number, number][] {
	const cells: [number, number][] = [];
	board.forEach((row, r) =>
		row.forEach((cell, c) => {
			if (cell === 0) cells.push([r, c]);
		}),
	);
	return cells;
}

// `random` is injectable so tests can make tile placement/value deterministic.
export function addRandomTile(board: Board, random: () => number = Math.random): Board {
	const cells = emptyCells(board);
	if (cells.length === 0) return board;
	const [r, c] = cells[Math.floor(random() * cells.length)];
	const value = random() < 0.9 ? 2 : 4;
	const next = board.map((row) => [...row]);
	next[r][c] = value;
	return next;
}

export function newGame(random: () => number = Math.random): Board {
	return addRandomTile(addRandomTile(createEmptyBoard(), random), random);
}

function slideRowLeft(row: number[]): { row: number[]; scoreGained: number } {
	const values = row.filter((v) => v !== 0);
	const merged: number[] = [];
	let scoreGained = 0;
	for (let i = 0; i < values.length; i++) {
		if (values[i] === values[i + 1]) {
			const mergedValue = values[i] * 2;
			merged.push(mergedValue);
			scoreGained += mergedValue;
			i++;
		} else {
			merged.push(values[i]);
		}
	}
	while (merged.length < row.length) merged.push(0);
	return { row: merged, scoreGained };
}

function transpose(board: Board): Board {
	const size = board.length;
	return Array.from({ length: size }, (_, r) => Array.from({ length: size }, (_, c) => board[c][r]));
}

function reverseRows(board: Board): Board {
	return board.map((row) => [...row].reverse());
}

export function move(board: Board, direction: Direction): { board: Board; moved: boolean; scoreGained: number } {
	let working = board;
	if (direction === 'up' || direction === 'down') working = transpose(working);
	if (direction === 'right' || direction === 'down') working = reverseRows(working);

	let scoreGained = 0;
	working = working.map((row) => {
		const result = slideRowLeft(row);
		scoreGained += result.scoreGained;
		return result.row;
	});

	if (direction === 'right' || direction === 'down') working = reverseRows(working);
	if (direction === 'up' || direction === 'down') working = transpose(working);

	const moved = JSON.stringify(working) !== JSON.stringify(board);
	return { board: working, moved, scoreGained };
}

export function hasMoves(board: Board): boolean {
	if (emptyCells(board).length > 0) return true;
	const size = board.length;
	for (let r = 0; r < size; r++) {
		for (let c = 0; c < size; c++) {
			const value = board[r][c];
			if (c + 1 < size && board[r][c + 1] === value) return true;
			if (r + 1 < size && board[r + 1][c] === value) return true;
		}
	}
	return false;
}

export function hasWon(board: Board, target: number = WIN_VALUE): boolean {
	return board.some((row) => row.some((cell) => cell >= target));
}
