import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import WordleTile from './WordleTile.svelte';

describe('WordleTile', () => {
	it('renders the static preview', () => {
		render(WordleTile, { props: { widgetId: 'wordle' } });

		expect(screen.getByText('Wordle')).toBeInTheDocument();
		expect(screen.getByText('Tap to play')).toBeInTheDocument();
		expect(screen.getByText('W')).toBeInTheDocument();
		expect(screen.getByText('O')).toBeInTheDocument();
		expect(screen.getByText('R')).toBeInTheDocument();
		expect(screen.getByText('D')).toBeInTheDocument();
		expect(screen.getByText('S')).toBeInTheDocument();
	});
});
