import { describe, expect, it } from 'vitest';
import { isValidGuess, isWin, keyboardStatuses, pickAnswer, scoreGuess, type GuessResult } from './wordle';
import { ANSWER_WORDS } from './wordleWords';

describe('pickAnswer', () => {
	it('is deterministic for a fixed random function', () => {
		expect(pickAnswer(() => 0)).toBe(ANSWER_WORDS[0]);
	});

	it('always returns a member of ANSWER_WORDS', () => {
		expect(ANSWER_WORDS).toContain(pickAnswer(() => 0.5));
	});
});

describe('scoreGuess', () => {
	it('marks every letter correct when the guess matches the answer', () => {
		const result = scoreGuess('APPLE', 'APPLE');

		expect(result.map((r) => r.status)).toEqual(['correct', 'correct', 'correct', 'correct', 'correct']);
	});

	it('marks every letter absent when no letters are shared', () => {
		const result = scoreGuess('ABCDE', 'FGHIJ');

		expect(result.map((r) => r.status)).toEqual(['absent', 'absent', 'absent', 'absent', 'absent']);
	});

	it('scores a mixed guess with correct, present, and absent letters', () => {
		// answer TRACE: T,R,A,C,E — guess CRANE shares every letter but only
		// R, A, E land in their answer position.
		const result = scoreGuess('CRANE', 'TRACE');

		expect(result).toEqual<GuessResult>([
			{ letter: 'C', status: 'present' },
			{ letter: 'R', status: 'correct' },
			{ letter: 'A', status: 'correct' },
			{ letter: 'N', status: 'absent' },
			{ letter: 'E', status: 'correct' },
		]);
	});

	it('is case-insensitive', () => {
		expect(scoreGuess('crane', 'trace')).toEqual(scoreGuess('CRANE', 'TRACE'));
	});

	it('does not over-count a guessed letter that appears fewer times in the answer', () => {
		// answer ABIDE has a single E; guess SPEED has two — only the first
		// (by position) can be claimed, the second must stay absent.
		const result = scoreGuess('SPEED', 'ABIDE');

		expect(result).toEqual<GuessResult>([
			{ letter: 'S', status: 'absent' },
			{ letter: 'P', status: 'absent' },
			{ letter: 'E', status: 'present' },
			{ letter: 'E', status: 'absent' },
			{ letter: 'D', status: 'present' },
		]);
	});

	it('lets an exact-position match claim a duplicate letter before present matches do', () => {
		// answer ALARM has two A's and one L; guess LLAMA has two L's and two
		// A's — the correctly-placed L (index 1) and A (index 2) claim their
		// letters first, leaving the extra L absent and the extra A present.
		const result = scoreGuess('LLAMA', 'ALARM');

		expect(result).toEqual<GuessResult>([
			{ letter: 'L', status: 'absent' },
			{ letter: 'L', status: 'correct' },
			{ letter: 'A', status: 'correct' },
			{ letter: 'M', status: 'present' },
			{ letter: 'A', status: 'present' },
		]);
	});
});

describe('isValidGuess', () => {
	it('is true for a word in the guess list', () => {
		expect(isValidGuess('APPLE')).toBe(true);
	});

	it('is case-insensitive', () => {
		expect(isValidGuess('apple')).toBe(true);
	});

	it('is false for gibberish', () => {
		expect(isValidGuess('ZZZZZ')).toBe(false);
	});

	it('is false for the wrong length', () => {
		expect(isValidGuess('CAT')).toBe(false);
		expect(isValidGuess('APPLES')).toBe(false);
	});
});

describe('isWin', () => {
	it('is true when every letter is correct', () => {
		expect(isWin(scoreGuess('APPLE', 'APPLE'))).toBe(true);
	});

	it('is false otherwise', () => {
		expect(isWin(scoreGuess('CRANE', 'TRACE'))).toBe(false);
	});
});

describe('keyboardStatuses', () => {
	it('reflects a single guess directly', () => {
		const guesses = [scoreGuess('CRANE', 'TRACE')];

		expect(keyboardStatuses(guesses)).toEqual({
			C: 'present',
			R: 'correct',
			A: 'correct',
			N: 'absent',
			E: 'correct',
		});
	});

	it('lets a later correct status override an earlier absent one for the same letter', () => {
		const guesses: GuessResult[] = [[{ letter: 'A', status: 'absent' }], [{ letter: 'A', status: 'correct' }]];

		expect(keyboardStatuses(guesses)).toEqual({ A: 'correct' });
	});

	it('keeps the best status seen when a later guess reports a lower one', () => {
		const guesses: GuessResult[] = [[{ letter: 'B', status: 'present' }], [{ letter: 'B', status: 'absent' }]];

		expect(keyboardStatuses(guesses)).toEqual({ B: 'present' });
	});
});
