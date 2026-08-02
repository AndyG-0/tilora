import { render, screen } from '@testing-library/svelte';
import { fireEvent } from '@testing-library/dom';
import { createRawSnippet } from 'svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto } = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));

import TileCard from './TileCard.svelte';

function textSnippet(text: string) {
	return createRawSnippet(() => ({
		render: () => `<span>${text}</span>`,
	}));
}

describe('TileCard', () => {
	it('renders its children', () => {
		render(TileCard, { props: { widgetId: 'weather', children: textSnippet('Weather content') } });

		expect(screen.getByText('Weather content')).toBeInTheDocument();
	});

	it('navigates to the widget detail route on click', async () => {
		render(TileCard, { props: { widgetId: 'ai-insights', children: textSnippet('AI content') } });

		await fireEvent.click(screen.getByRole('button'));

		expect(goto).toHaveBeenCalledWith('/widget/ai-insights');
	});
});
