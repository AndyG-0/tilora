import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import Game2048Tile from './Game2048Tile.svelte';

describe('Game2048Tile', () => {
	it('renders the static preview', () => {
		render(Game2048Tile, { props: { widgetId: 'game2048' } });

		expect(screen.getByText('2048')).toBeInTheDocument();
		expect(screen.getByText('Tap to play')).toBeInTheDocument();
		expect(screen.getByText('2')).toBeInTheDocument();
		expect(screen.getByText('4')).toBeInTheDocument();
		expect(screen.getByText('8')).toBeInTheDocument();
	});
});
