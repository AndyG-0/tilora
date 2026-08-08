import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
	parseFormattedLines,
	replaceDiscordReferences,
	segmentsToChars,
	segmentsToHtml,
	type FormattedSegment,
} from './discordMarkdown';

beforeEach(() => {
	vi.resetModules();
});

describe('renderDiscordMarkdown (browser)', () => {
	beforeEach(() => {
		vi.doMock('$app/environment', () => ({ browser: true }));
	});

	async function render(content: string) {
		const { renderDiscordMarkdown } = await import('./discordMarkdown');
		return renderDiscordMarkdown(content);
	}

	it('renders bold text', async () => {
		expect(await render('**bold**')).toContain('<strong>bold</strong>');
	});

	it('renders italic text with either delimiter', async () => {
		expect(await render('*italic*')).toContain('<em>italic</em>');
		expect(await render('_italic_')).toContain('<em>italic</em>');
	});

	it('renders underline as <u>, distinct from CommonMark bold', async () => {
		const html = await render('__underline__');
		expect(html).toContain('<u>underline</u>');
		expect(html).not.toContain('<strong>');
	});

	it('renders strikethrough', async () => {
		expect(await render('~~strike~~')).toContain('<del>strike</del>');
	});

	it('renders a spoiler as a focusable, hidden-until-revealed span', async () => {
		const html = await render('||secret||');
		expect(html).toContain('class="spoiler"');
		expect(html).toContain('role="button"');
		expect(html).toContain('tabindex="0"');
		expect(html).toContain('secret');
	});

	it('reveals a spoiler on click and keydown', async () => {
		const { toggleSpoiler, toggleSpoilerKey } = await import('./discordMarkdown');
		const container = document.createElement('div');
		container.innerHTML = await render('||secret||');
		const span = container.querySelector('.spoiler')!;

		toggleSpoiler({ target: span } as unknown as MouseEvent);
		expect(span.classList.contains('revealed')).toBe(true);

		toggleSpoilerKey({ key: 'Enter', target: span, preventDefault: () => {} } as unknown as KeyboardEvent);
		expect(span.classList.contains('revealed')).toBe(false);

		toggleSpoilerKey({ key: 'a', target: span, preventDefault: () => {} } as unknown as KeyboardEvent);
		expect(span.classList.contains('revealed')).toBe(false);
	});

	it('renders inline code and fenced code blocks', async () => {
		expect(await render('`code`')).toContain('<code>code</code>');
		const html = await render('```\ncode block\n```');
		expect(html).toContain('<pre>');
		expect(html).toContain('code block');
	});

	it('renders blockquotes', async () => {
		expect(await render('> quoted')).toContain('<blockquote>');
	});

	it('renders bulleted and numbered lists', async () => {
		const bulleted = await render('- one\n- two');
		expect(bulleted).toContain('<ul>');
		expect(bulleted).toContain('<li>one</li>');
		expect(bulleted).toContain('<li>two</li>');

		const numbered = await render('1. one\n2. two');
		expect(numbered).toContain('<ol>');
	});

	it('renders headers', async () => {
		expect(await render('# Heading')).toContain('<h1>Heading</h1>');
	});

	it('autolinks bare URLs and adds target/rel for safe navigation', async () => {
		const html = await render('https://example.com');
		expect(html).toContain('href="https://example.com"');
		expect(html).toContain('target="_blank"');
		expect(html).toContain('rel="noopener noreferrer"');
	});

	it('renders markdown link syntax', async () => {
		const html = await render('[example](https://example.com)');
		expect(html).toContain('<a href="https://example.com"');
		expect(html).toContain('>example</a>');
	});

	it('drops links with a non-http(s) protocol, keeping the text', async () => {
		const html = await render('[click me](javascript:alert(1))');
		expect(html).not.toContain('<a ');
		expect(html).toContain('click me');
	});

	it('strips script tags from raw HTML in message content', async () => {
		const html = await render('<script>alert(1)</script>');
		expect(html).not.toContain('<script');
		expect(html).not.toContain('alert(1)');
	});

	it('strips disallowed tags and event-handler attributes', async () => {
		const html = await render('<img src=x onerror="alert(1)">');
		expect(html).not.toContain('<img');
		expect(html).not.toContain('onerror');
	});
});

describe('renderDiscordMarkdown (server)', () => {
	beforeEach(() => {
		vi.doMock('$app/environment', () => ({ browser: false }));
	});

	it('falls back to escaped plain text instead of parsing markdown', async () => {
		const { renderDiscordMarkdown } = await import('./discordMarkdown');
		const html = renderDiscordMarkdown('**bold** <script>alert(1)</script>');
		expect(html).not.toContain('<strong>');
		expect(html).not.toContain('<script');
		expect(html).toContain('&lt;script&gt;');
	});
});

describe('parseFormattedLines', () => {
	function flatText(lines: FormattedSegment[][]): string {
		return lines.map((line) => line.map((s) => s.text).join('')).join('\n');
	}

	it('marks up bold, italic, underline, strike, and code segments', () => {
		const lines = parseFormattedLines('**bold** *italic* __underline__ ~~strike~~ `code`');
		const segments = lines[0];
		expect(segments.find((s) => s.text === 'bold')?.bold).toBe(true);
		expect(segments.find((s) => s.text === 'italic')?.italic).toBe(true);
		expect(segments.find((s) => s.text === 'underline')?.underline).toBe(true);
		expect(segments.find((s) => s.text === 'strike')?.strike).toBe(true);
		expect(segments.find((s) => s.text === 'code')?.code).toBe(true);
	});

	it('combines nested formatting flags on a single segment', () => {
		const lines = parseFormattedLines('**_bold italic_**');
		const segment = lines[0].find((s) => s.text === 'bold italic');
		expect(segment?.bold).toBe(true);
		expect(segment?.italic).toBe(true);
	});

	it('marks link text with the link flag', () => {
		const lines = parseFormattedLines('[example](https://example.com)');
		const segment = lines[0].find((s) => s.text === 'example');
		expect(segment?.link).toBe(true);
	});

	it('redacts spoiler text, sizing the redaction to the hidden text length', () => {
		const lines = parseFormattedLines('||secret||');
		const segment = lines[0].find((s) => s.spoiler);
		expect(segment?.text).toBe('█'.repeat('secret'.length));
	});

	it('drops formatting inside a spoiler but keeps formatting wrapping it', () => {
		const lines = parseFormattedLines('**||bold secret||**');
		const segment = lines[0].find((s) => s.spoiler);
		expect(segment?.text).toBe('█'.repeat('bold secret'.length));
		expect(segment?.bold).toBe(true);
	});

	it('renders headings as a single bold line', () => {
		const lines = parseFormattedLines('# Heading');
		expect(flatText(lines)).toBe('Heading');
		expect(lines[0][0].bold).toBe(true);
	});

	it('drops the blockquote marker but keeps the content', () => {
		const lines = parseFormattedLines('> quoted text');
		expect(flatText(lines)).toBe('quoted text');
	});

	it('prefixes list items with a bullet or number', () => {
		const bulleted = parseFormattedLines('- one\n- two');
		expect(flatText(bulleted)).toBe('• one\n• two');

		const numbered = parseFormattedLines('1. one\n2. two');
		expect(flatText(numbered)).toBe('1. one\n2. two');
	});

	it('renders fenced code blocks as one code-flagged line per source line', () => {
		const lines = parseFormattedLines('```\nline one\nline two\n```');
		expect(lines).toHaveLength(2);
		expect(lines[0]).toEqual([{ text: 'line one', code: true }]);
		expect(lines[1]).toEqual([{ text: 'line two', code: true }]);
	});

	it('drops blank lines produced by consecutive newlines', () => {
		const lines = parseFormattedLines('First\n\n\nSecond');
		expect(flatText(lines)).toBe('First\nSecond');
	});
});

describe('segmentsToChars', () => {
	it('explodes segments into one entry per character, carrying formatting flags', () => {
		const chars = segmentsToChars([{ text: 'ab', bold: true }]);
		expect(chars).toEqual([
			{
				ch: 'a',
				bold: true,
				italic: undefined,
				underline: undefined,
				strike: undefined,
				code: undefined,
				link: undefined,
				spoiler: undefined,
			},
			{
				ch: 'b',
				bold: true,
				italic: undefined,
				underline: undefined,
				strike: undefined,
				code: undefined,
				link: undefined,
				spoiler: undefined,
			},
		]);
	});

	it('counts multi-code-unit glyphs as a single character', () => {
		const chars = segmentsToChars([{ text: '🎉x' }]);
		expect(chars.map((c) => c.ch)).toEqual(['🎉', 'x']);
	});
});

describe('segmentsToHtml', () => {
	it('wraps formatted segments in the corresponding inline tags', () => {
		const html = segmentsToHtml([
			{ text: 'bold', bold: true },
			{ text: 'italic', italic: true },
			{ text: 'u', underline: true },
			{ text: 'strike', strike: true },
			{ text: 'code', code: true },
			{ text: 'link', link: true },
		]);
		expect(html).toBe(
			'<strong>bold</strong><em>italic</em><u>u</u><s>strike</s><code>code</code><span class="md-link">link</span>',
		);
	});

	it('escapes HTML-significant characters in segment text', () => {
		const html = segmentsToHtml([{ text: '<script>&"\'' }]);
		expect(html).not.toContain('<script>');
		expect(html).toContain('&lt;script&gt;');
		expect(html).toContain('&amp;');
		expect(html).toContain('&quot;');
		expect(html).toContain('&#39;');
	});
});

describe('replaceDiscordReferences', () => {
	it('converts mentions, roles, channels, and custom emoji to readable text', () => {
		const result = replaceDiscordReferences('Hi <@123> <@!456> <@&789> <#111> :) <a:wave:222> <:tada:333>');
		expect(result).toBe('Hi @user @user @role #channel :) :wave: :tada:');
	});
});
