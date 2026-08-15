<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import {
		addRandomTile,
		hasMoves,
		hasWon,
		move as applyMove,
		newGame,
		type Board,
		type Direction,
	} from '$lib/game2048';
	import { _ } from 'svelte-i18n';

	interface Game2048DetailData {
		title: string;
		best_score: number;
	}

	let { data }: { data: Game2048DetailData } = $props();

	// Legacy client-side-only storage, kept only as a one-time migration
	// source (see onMount) — the backend is now the source of truth, since a
	// best score should follow the user to any device, not stay stuck on the
	// one it was set on.
	const BEST_SCORE_KEY = 'game2048-best-score';
	const SWIPE_THRESHOLD_PX = 24;
	const KEY_TO_DIRECTION: Record<string, Direction> = {
		ArrowUp: 'up',
		ArrowDown: 'down',
		ArrowLeft: 'left',
		ArrowRight: 'right',
	};

	let board = $state<Board>(newGame());
	let score = $state(0);
	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates go through saveBestIfNeeded.
	let best = $state(data.best_score);
	let gameOver = $state(false);
	let won = $state(false);

	async function saveBestIfNeeded() {
		if (score <= best) return;
		best = score;
		try {
			await api.updateWidgetSettings(page.params.id!, { best_score: best });
		} catch {
			// best score just won't persist across reloads (e.g. network hiccup)
		}
	}

	function reset() {
		board = newGame();
		score = 0;
		gameOver = false;
		won = false;
	}

	function play(direction: Direction) {
		if (gameOver) return;
		const result = applyMove(board, direction);
		if (!result.moved) return;

		const next = addRandomTile(result.board);
		board = next;
		score += result.scoreGained;
		saveBestIfNeeded();
		if (!won && hasWon(next)) won = true;
		if (!hasMoves(next)) gameOver = true;
	}

	function onKeydown(event: KeyboardEvent) {
		const direction = KEY_TO_DIRECTION[event.key];
		if (!direction) return;
		event.preventDefault();
		play(direction);
	}

	let touchStartX = 0;
	let touchStartY = 0;

	function onTouchStart(event: TouchEvent) {
		touchStartX = event.touches[0].clientX;
		touchStartY = event.touches[0].clientY;
	}

	function onTouchEnd(event: TouchEvent) {
		const deltaX = event.changedTouches[0].clientX - touchStartX;
		const deltaY = event.changedTouches[0].clientY - touchStartY;
		if (Math.max(Math.abs(deltaX), Math.abs(deltaY)) < SWIPE_THRESHOLD_PX) return;

		if (Math.abs(deltaX) > Math.abs(deltaY)) {
			play(deltaX > 0 ? 'right' : 'left');
		} else {
			play(deltaY > 0 ? 'down' : 'up');
		}
	}

	onMount(() => {
		// One-time migration: if the backend has no stored best yet but this
		// browser has a pre-existing localStorage one, push it up once so an
		// existing best score isn't lost, then stop touching localStorage.
		if (best > 0) return;
		try {
			const local = Number(localStorage.getItem(BEST_SCORE_KEY) ?? 0);
			if (local > 0) {
				best = local;
				api.updateWidgetSettings(page.params.id!, { best_score: best }).catch(() => {});
			}
		} catch {
			// no localStorage to migrate from (e.g. private browsing)
		}
	});
</script>

<svelte:window onkeydown={onKeydown} />

<h1>{data.title}</h1>

<div class="scoreboard">
	<div class="score-box">
		<div class="label">{$_('game2048.detail.score')}</div>
		<div class="value">{score}</div>
	</div>
	<div class="score-box">
		<div class="label">{$_('game2048.detail.best')}</div>
		<div class="value">{best}</div>
	</div>
	<button class="new-game" onclick={reset}>{$_('game2048.detail.new_game')}</button>
</div>

<div class="board" ontouchstart={onTouchStart} ontouchend={onTouchEnd} role="presentation">
	{#each board as row, r (r)}
		{#each row as cell, c (c)}
			<div class="cell" data-value={cell || undefined}>
				{#if cell !== 0}{cell}{/if}
			</div>
		{/each}
	{/each}

	{#if gameOver}
		<div class="overlay">
			<p>{$_('game2048.detail.game_over')}</p>
			<button onclick={reset}>{$_('game2048.detail.try_again')}</button>
		</div>
	{:else if won}
		<div class="overlay">
			<p>{$_('game2048.detail.won')}</p>
			<div class="overlay-actions">
				<button onclick={() => (won = false)}>{$_('game2048.detail.keep_playing')}</button>
				<button onclick={reset}>{$_('game2048.detail.new_game')}</button>
			</div>
		</div>
	{/if}
</div>

<p class="hint">{$_('game2048.detail.hint')}</p>

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
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.6rem;
		max-width: 28rem;
		aspect-ratio: 1;
		padding: 0.6rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		touch-action: none;
	}

	.cell {
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.5rem;
		background: var(--color-surface-hover, var(--color-border));
		font-size: 1.4rem;
		font-weight: 700;
		color: var(--color-text);
	}

	/* Progressively deeper accent shades keyed on tile magnitude — theme-aware
	   instead of the classic 2048 palette, since this needs to work across
	   light/dark/sepia/high-contrast. */
	.cell[data-value] {
		color: var(--color-surface);
		background: var(--color-accent, var(--color-text));
	}

	.cell[data-value='2'],
	.cell[data-value='4'] {
		opacity: 0.55;
		color: var(--color-text);
		background: var(--color-surface-hover, var(--color-border));
	}

	.cell[data-value='8'] {
		opacity: 0.7;
	}

	.cell[data-value='16'] {
		opacity: 0.8;
	}

	.cell[data-value='32'] {
		opacity: 0.9;
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

	.overlay-actions {
		display: flex;
		gap: 0.5rem;
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

	.hint {
		margin-top: 1rem;
		color: var(--color-text-muted);
	}
</style>
