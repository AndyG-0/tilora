// Pure Wordle game engine — no DOM/Svelte dependencies, so it's directly
// unit-testable and reusable between the tile preview and the full board.

import { ANSWER_WORDS, VALID_GUESSES } from '$lib/wordleWords';

export type LetterStatus = 'correct' | 'present' | 'absent';
export type GuessResult = { letter: string; status: LetterStatus }[];

export const WORD_LENGTH = 5;
export const MAX_ATTEMPTS = 6;

const VALID_GUESS_SET = new Set(VALID_GUESSES);

// `random` is injectable so tests can make the chosen answer deterministic.
export function pickAnswer(random: () => number = Math.random): string {
	return ANSWER_WORDS[Math.floor(random() * ANSWER_WORDS.length)];
}

export function isValidGuess(word: string): boolean {
	return VALID_GUESS_SET.has(word.toUpperCase());
}

// Duplicate-letter-safe two-pass scoring: exact matches claim a letter from
// the answer's frequency pool first, then remaining guessed letters claim
// from what's left — so a guess with more copies of a letter than the
// answer has never marks more than the true count as correct/present.
export function scoreGuess(guess: string, answer: string): GuessResult {
	const guessLetters = guess.toUpperCase().split('');
	const answerLetters = answer.toUpperCase().split('');
	const statuses: LetterStatus[] = new Array(guessLetters.length).fill('absent');

	const remaining = new Map<string, number>();
	answerLetters.forEach((letter) => remaining.set(letter, (remaining.get(letter) ?? 0) + 1));

	guessLetters.forEach((letter, i) => {
		if (letter === answerLetters[i]) {
			statuses[i] = 'correct';
			remaining.set(letter, (remaining.get(letter) ?? 0) - 1);
		}
	});

	guessLetters.forEach((letter, i) => {
		if (statuses[i] === 'correct') return;
		const left = remaining.get(letter) ?? 0;
		if (left > 0) {
			statuses[i] = 'present';
			remaining.set(letter, left - 1);
		}
	});

	return guessLetters.map((letter, i) => ({ letter, status: statuses[i] }));
}

export function isWin(result: GuessResult): boolean {
	return result.every((entry) => entry.status === 'correct');
}

const STATUS_RANK: Record<LetterStatus, number> = { absent: 0, present: 1, correct: 2 };

export type KeyboardStatus = Record<string, LetterStatus>;

// Folds every scored guess into each letter's best-known status so far
// (correct > present > absent), for coloring the on-screen keyboard.
export function keyboardStatuses(guesses: GuessResult[]): KeyboardStatus {
	const statuses: KeyboardStatus = {};
	guesses.forEach((result) => {
		result.forEach(({ letter, status }) => {
			const current = statuses[letter];
			if (!current || STATUS_RANK[status] > STATUS_RANK[current]) {
				statuses[letter] = status;
			}
		});
	});
	return statuses;
}
