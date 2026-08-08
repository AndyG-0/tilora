import { beforeEach, describe, expect, it, vi } from 'vitest';

beforeEach(() => {
	vi.resetModules();
});

describe('renderMarkdown (browser)', () => {
	beforeEach(() => {
		vi.doMock('$app/environment', () => ({ browser: true }));
	});

	async function render(content: string) {
		const { renderMarkdown } = await import('./markdown');
		return renderMarkdown(content);
	}

	it('renders bold and italic text', async () => {
		expect(await render('**bold**')).toContain('<strong>bold</strong>');
		expect(await render('*italic*')).toContain('<em>italic</em>');
	});

	it('renders underline as literal double-underscore (no Discord dialect)', async () => {
		const html = await render('__text__');
		expect(html).toContain('<strong>text</strong>');
		expect(html).not.toContain('<u>');
	});

	it('renders GFM lists, headings, and blockquotes', async () => {
		expect(await render('- one\n- two')).toContain('<li>one</li>');
		expect(await render('# Heading')).toContain('<h1>Heading</h1>');
		expect(await render('> quoted')).toContain('<blockquote>');
	});

	it('renders inline code and fenced code blocks', async () => {
		expect(await render('`code`')).toContain('<code>code</code>');
		const html = await render('```\ncode block\n```');
		expect(html).toContain('<pre>');
		expect(html).toContain('code block');
	});

	it('adds target/rel to http(s) links but drops other protocols', async () => {
		const html = await render('[example](https://example.com)');
		expect(html).toContain('<a href="https://example.com"');
		expect(html).toContain('target="_blank"');
		expect(html).toContain('rel="noopener noreferrer"');

		const dropped = await render('[click me](javascript:alert(1))');
		expect(dropped).not.toContain('<a ');
		expect(dropped).toContain('click me');
	});

	it('sanitizes raw HTML and disallowed attributes', async () => {
		const html = await render('<script>alert(1)</script>');
		expect(html).not.toContain('<script');
		expect(html).not.toContain('alert(1)');

		const imgHtml = await render('<img src=x onerror="alert(1)">');
		expect(imgHtml).not.toContain('<img');
		expect(imgHtml).not.toContain('onerror');
	});
});

describe('renderMarkdown (server)', () => {
	beforeEach(() => {
		vi.doMock('$app/environment', () => ({ browser: false }));
	});

	it('falls back to escaped plain text instead of parsing markdown', async () => {
		const { renderMarkdown } = await import('./markdown');
		const html = renderMarkdown('**bold** <script>alert(1)</script>');
		expect(html).not.toContain('<strong>');
		expect(html).not.toContain('<script');
		expect(html).toContain('&lt;script&gt;');
	});
});
