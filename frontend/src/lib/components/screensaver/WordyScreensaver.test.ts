import { render } from '@testing-library/svelte';
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';

import WordyScreensaver from './WordyScreensaver.svelte';

describe('WordyScreensaver — discord', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("splits a multi-line message into separate lines, prefixing only the first with the message's author", async () => {
		const data = { messages: [{ author: 'Andy', content: 'Line one\nLine two\nLine three' }] };
		const { container } = render(WordyScreensaver, { props: { type: 'discord', data, animationStyle: 'led_dots' } });

		expect(container.querySelector('.dots')?.textContent).toBe('Andy: Line one');

		await vi.advanceTimersByTimeAsync(8000);
		expect(container.querySelector('.dots')?.textContent).toBe('Line two');

		await vi.advanceTimersByTimeAsync(8000);
		expect(container.querySelector('.dots')?.textContent).toBe('Line three');
	});

	it('renders markdown formatting instead of stripping it', () => {
		const data = {
			messages: [{ author: 'Andy', content: '**bold** and _italic_ and `code` and ~~strike~~ and ||spoiler||' }],
		};
		const { container } = render(WordyScreensaver, { props: { type: 'discord', data, animationStyle: 'led_dots' } });

		const dots = container.querySelector('.dots');
		expect(dots?.querySelector('strong')?.textContent).toBe('bold');
		expect(dots?.querySelector('em')?.textContent).toBe('italic');
		expect(dots?.querySelector('code')?.textContent).toBe('code');
		expect(dots?.querySelector('s')?.textContent).toBe('strike');
		expect(dots?.textContent).not.toContain('spoiler');
		expect(dots?.textContent).toContain('█'.repeat('spoiler'.length));
	});

	it('converts mentions, channel refs, and custom emoji to readable text', () => {
		const data = {
			messages: [{ author: 'Andy', content: 'Hello <@123456789> see <#987654321> :tada: <a:wave:555>' }],
		};
		const { container } = render(WordyScreensaver, { props: { type: 'discord', data, animationStyle: 'led_dots' } });

		expect(container.querySelector('.dots')?.textContent).toBe('Andy: Hello @user see #channel :tada: :wave:');
	});

	it('drops blank lines produced by consecutive newlines', async () => {
		const data = { messages: [{ author: 'Andy', content: 'First\n\n\nSecond' }] };
		const { container } = render(WordyScreensaver, { props: { type: 'discord', data, animationStyle: 'led_dots' } });

		expect(container.querySelector('.dots')?.textContent).toBe('Andy: First');
		await vi.advanceTimersByTimeAsync(8000);
		expect(container.querySelector('.dots')?.textContent).toBe('Second');
	});
});

describe('WordyScreensaver — rss', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('flattens every feed group into a single line list', () => {
		const data = {
			feed_groups: [
				{ feed_id: 1, name: 'Feed One', items: [{ title: 'Headline A', source: 'Feed One' }] },
				{ feed_id: 2, name: 'Feed Two', items: [{ title: 'Headline B', source: 'Feed Two' }] },
			],
		};
		const { container } = render(WordyScreensaver, { props: { type: 'rss', data, animationStyle: 'led_dots' } });

		expect(container.querySelector('.dots')?.textContent).toBe('Headline A — Feed One');
	});

	it('shows a placeholder when there are no headlines yet', () => {
		const data = { feed_groups: [] };
		const { container } = render(WordyScreensaver, { props: { type: 'rss', data, animationStyle: 'led_dots' } });

		expect(container.querySelector('.dots')?.textContent).toBe('No headlines yet.');
	});
});
