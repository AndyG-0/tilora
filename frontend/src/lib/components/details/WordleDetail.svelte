<script lang="ts">
	import { onMount } from 'svelte';
	import {
		MAX_ATTEMPTS,
		WORD_LENGTH,
		isValidGuess,
		isWin,
		keyboardStatuses,
		pickAnswer,
		scoreGuess,
		type GuessResult,
	} from '$lib/wordle';
	import { _ } from 'svelte-i18n';

	interface WordleDetailData {
		title: string;
	}

	let { data }: { data: WordleDetailData } = $props();

	const STATS_KEY = 'wordle-stats';
	const SHAKE_DURATION_MS = 400;
	const KEYBOARD_ROWS: string[][] = [
		['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
		['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
		['ENTER', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '⌫'],
	];

	let answer = $state(pickAnswer());
	let guesses = $state<GuessResult[]>([]);
	let currentGuess = $state('');
	let gameOver = $state(false);
	let won = $state(false);
	let invalidShake = $state(false);
	let stats = $state({ played: 0, won: 0, currentStreak: 0, maxStreak: 0 });

	let keyboardState = $derived(keyboardStatuses(guesses));

	function saveStats() {
		try {
			localStorage.setItem(STATS_KEY, JSON.stringify(stats));
		} catch {
			// stats just won't persist across reloads (e.g. private browsing)
		}
	}

	function recordGameEnd(didWin: boolean) {
		stats.played += 1;
		if (didWin) {
			stats.won += 1;
			stats.currentStreak += 1;
			stats.maxStreak = Math.max(stats.maxStreak, stats.currentStreak);
		} else {
			stats.currentStreak = 0;
		}
		saveStats();
	}

	function triggerShake() {
		invalidShake = true;
		setTimeout(() => (invalidShake = false), SHAKE_DURATION_MS);
	}

	function reset() {
		answer = pickAnswer();
		guesses = [];
		currentGuess = '';
		gameOver = false;
		won = false;
	}

	function submitGuess() {
		if (gameOver) return;
		if (currentGuess.length !== WORD_LENGTH || !isValidGuess(currentGuess)) {
			triggerShake();
			return;
		}

		const result = scoreGuess(currentGuess, answer);
		guesses = [...guesses, result];
		currentGuess = '';

		if (isWin(result)) {
			won = true;
			gameOver = true;
			recordGameEnd(true);
		} else if (guesses.length >= MAX_ATTEMPTS) {
			gameOver = true;
			recordGameEnd(false);
		}
	}

	function pressLetter(letter: string) {
		if (gameOver || currentGuess.length >= WORD_LENGTH) return;
		currentGuess += letter;
	}

	function pressBackspace() {
		if (gameOver) return;
		currentGuess = currentGuess.slice(0, -1);
	}

	function pressEnter() {
		submitGuess();
	}

	function onKeydown(event: KeyboardEvent) {
		if (event.metaKey || event.ctrlKey || event.altKey) return;

		if (event.key === 'Enter') {
			event.preventDefault();
			pressEnter();
		} else if (event.key === 'Backspace') {
			event.preventDefault();
			pressBackspace();
		} else if (/^[a-zA-Z]$/.test(event.key)) {
			event.preventDefault();
			pressLetter(event.key.toUpperCase());
		}
	}

	function cellLetter(row: number, col: number): string {
		if (row < guesses.length) return guesses[row][col].letter;
		if (row === guesses.length) return currentGuess[col] ?? '';
		return '';
	}

	function cellStatus(row: number, col: number) {
		return row < guesses.length ? guesses[row][col].status : undefined;
	}

	onMount(() => {
		try {
			const raw = localStorage.getItem(STATS_KEY);
			if (raw) stats = JSON.parse(raw);
		} catch {
			// keep defaults (e.g. private browsing blocks localStorage)
		}
	});
</script>

<svelte:window onkeydown={onKeydown} />

<h1>{data.title}</h1>

<div class="scoreboard">
	<div class="score-box">
		<div class="label">{$_('wordle.detail.played')}</div>
		<div class="value">{stats.played}</div>
	</div>
	<div class="score-box">
		<div class="label">{$_('wordle.detail.streak')}</div>
		<div class="value">{stats.currentStreak}</div>
	</div>
	<button class="new-game" onclick={reset}>{$_('wordle.detail.new_game')}</button>
</div>

<div class="board" class:shake={invalidShake}>
	<!-- eslint-disable-next-line @typescript-eslint/no-unused-vars -- each-block item binding is required syntax; only the index is used -->
	{#each Array(MAX_ATTEMPTS) as _, row (row)}
		<div class="row">
			<!-- eslint-disable-next-line @typescript-eslint/no-unused-vars -- each-block item binding is required syntax; only the index is used -->
			{#each Array(WORD_LENGTH) as _, col (col)}
				<div class="cell" data-status={cellStatus(row, col)}>{cellLetter(row, col)}</div>
			{/each}
		</div>
	{/each}

	{#if gameOver}
		<div class="overlay">
			<p>{won ? $_('wordle.detail.won') : $_('wordle.detail.lost', { values: { word: answer } })}</p>
			<button onclick={reset}>{$_('wordle.detail.new_game')}</button>
		</div>
	{/if}
</div>

<div class="keyboard">
	{#each KEYBOARD_ROWS as row (row.join(''))}
		<div class="key-row">
			{#each row as key (key)}
				<button
					class="key"
					data-wide={key.length > 1 || undefined}
					data-status={keyboardState[key]}
					aria-label={key === '⌫' ? $_('wordle.detail.backspace') : key}
					onclick={() => (key === 'ENTER' ? pressEnter() : key === '⌫' ? pressBackspace() : pressLetter(key))}
				>
					{key}
				</button>
			{/each}
		</div>
	{/each}
</div>

<p class="hint">{$_('wordle.detail.hint')}</p>

<style>
	h1 {
		margin: 0 0 1rem;
	}

	.scoreboard {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.score-box {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.6rem;
		padding: 0.4rem 0.9rem;
		text-align: center;
	}

	.score-box .label {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.score-box .value {
		font-size: 1.2rem;
		font-weight: 600;
	}

	.new-game {
		margin-left: auto;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		border-radius: 0.6rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.board {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		width: fit-content;
		padding: 0.6rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
	}

	.board.shake {
		animation: shake 0.4s;
	}

	@keyframes shake {
		10%,
		90% {
			transform: translateX(-4px);
		}
		20%,
		80% {
			transform: translateX(4px);
		}
		30%,
		50%,
		70% {
			transform: translateX(-6px);
		}
		40%,
		60% {
			transform: translateX(6px);
		}
	}

	.row {
		display: grid;
		grid-template-columns: repeat(5, 1fr);
		gap: 0.4rem;
	}

	.cell {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 3rem;
		height: 3rem;
		border: 2px solid var(--color-border);
		border-radius: 0.4rem;
		font-size: 1.4rem;
		font-weight: 700;
		color: var(--color-text);
		text-transform: uppercase;
	}

	.cell[data-status='correct'] {
		background: var(--color-success);
		border-color: var(--color-success);
		color: var(--color-on-accent);
	}

	.cell[data-status='present'] {
		background: var(--color-warning);
		border-color: var(--color-warning);
		color: var(--color-on-accent);
	}

	.cell[data-status='absent'] {
		background: var(--color-surface-hover, var(--color-border));
		border-color: var(--color-surface-hover, var(--color-border));
		color: var(--color-text-muted);
	}

	.overlay {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		background: color-mix(in srgb, var(--color-surface) 85%, transparent);
		border-radius: 1rem;
		font-size: 1.2rem;
		font-weight: 600;
		text-align: center;
		padding: 1rem;
	}

	.overlay button {
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		border-radius: 0.6rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
		font-size: 1rem;
		font-weight: 500;
	}

	.keyboard {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-top: 1rem;
		max-width: 28rem;
	}

	.key-row {
		display: flex;
		gap: 0.35rem;
		justify-content: center;
	}

	.key {
		flex: 1;
		min-width: 2rem;
		height: 3rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
		border-radius: 0.4rem;
		font-weight: 600;
		font-size: 0.85rem;
		cursor: pointer;
		text-transform: uppercase;
	}

	.key[data-wide] {
		flex: 1.5;
		font-size: 0.7rem;
	}

	.key:active {
		background: var(--color-surface-hover);
	}

	.key[data-status='correct'] {
		background: var(--color-success);
		border-color: var(--color-success);
		color: var(--color-on-accent);
	}

	.key[data-status='present'] {
		background: var(--color-warning);
		border-color: var(--color-warning);
		color: var(--color-on-accent);
	}

	.key[data-status='absent'] {
		opacity: 0.4;
	}

	.hint {
		margin-top: 1rem;
		color: var(--color-text-muted);
	}
</style>
