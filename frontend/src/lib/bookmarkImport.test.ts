import { describe, expect, it } from 'vitest';
import {
	parseNetscapeHtml,
	parseChromiumJson,
	parseGenericJson,
	parseCsv,
	parseBookmarkText,
	importBookmarksFromFile,
} from './bookmarkImport';

describe('bookmarkImport', () => {
	describe('parseNetscapeHtml', () => {
		it('parses standard Netscape bookmark HTML format', () => {
			const html = `
<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><H3 ADD_DATE="1600000000">Dev</H3>
    <DL><p>
        <DT><A HREF="https://github.com" ADD_DATE="1600000000" ICON="https://github.com/favicon.ico">GitHub</A>
        <DT><A HREF="https://svelte.dev" ICON="https://svelte.dev/favicon.png">Svelte</A>
    </DL><p>
    <DT><A HREF="https://news.ycombinator.com">Hacker News</A>
</DL><p>
`;
			const result = parseNetscapeHtml(html);
			expect(result).toEqual([
				{ name: 'GitHub', url: 'https://github.com', icon: 'https://github.com/favicon.ico' },
				{ name: 'Svelte', url: 'https://svelte.dev', icon: 'https://svelte.dev/favicon.png' },
				{ name: 'Hacker News', url: 'https://news.ycombinator.com' },
			]);
		});

		it('ignores unsafe or javascript links in HTML', () => {
			const html = `
<DL>
    <DT><A HREF="javascript:alert(1)">Exploit</A>
    <DT><A HREF="data:text/html,bad">Data</A>
    <DT><A HREF="https://safe.com">Safe Link</A>
</DL>
`;
			const result = parseNetscapeHtml(html);
			expect(result).toEqual([{ name: 'Safe Link', url: 'https://safe.com' }]);
		});
	});

	describe('parseChromiumJson', () => {
		it('parses Chrome/Chromium bookmarks json structure', () => {
			const data = {
				checksum: 'abc123',
				roots: {
					bookmark_bar: {
						children: [
							{
								name: 'GitHub',
								type: 'url',
								url: 'https://github.com',
							},
							{
								name: 'Folder',
								type: 'folder',
								children: [
									{
										name: 'Google',
										type: 'url',
										url: 'https://google.com',
										icon: 'https://google.com/favicon.ico',
									},
								],
							},
						],
					},
					other: {
						children: [
							{
								name: 'Mozilla',
								type: 'url',
								url: 'https://mozilla.org',
							},
						],
					},
				},
				version: 1,
			};

			const result = parseChromiumJson(data);
			expect(result).toEqual([
				{ name: 'GitHub', url: 'https://github.com' },
				{ name: 'Google', url: 'https://google.com', icon: 'https://google.com/favicon.ico' },
				{ name: 'Mozilla', url: 'https://mozilla.org' },
			]);
		});

		it('does not blow the call stack on pathologically deep folder nesting', () => {
			// A corrupted or maliciously crafted export could nest folders far
			// deeper than any real browser profile would -- this must degrade
			// (skip anything past the depth cap) rather than throwing.
			let innermost: Record<string, unknown> = {
				name: 'Deep',
				type: 'url',
				url: 'https://deep.example',
			};
			for (let i = 0; i < 5000; i++) {
				innermost = { name: `Folder ${i}`, type: 'folder', children: [innermost] };
			}
			const data = { roots: { bookmark_bar: innermost } };

			expect(() => parseChromiumJson(data)).not.toThrow();
			expect(parseChromiumJson(data)).toEqual([]);
		});

		it('still finds bookmarks nested within the depth cap', () => {
			let innermost: Record<string, unknown> = {
				name: 'Reachable',
				type: 'url',
				url: 'https://reachable.example',
			};
			for (let i = 0; i < 5; i++) {
				innermost = { name: `Folder ${i}`, type: 'folder', children: [innermost] };
			}
			const data = { roots: { bookmark_bar: innermost } };

			expect(parseChromiumJson(data)).toEqual([{ name: 'Reachable', url: 'https://reachable.example' }]);
		});
	});

	describe('parseGenericJson', () => {
		it('parses arrays of bookmark objects', () => {
			const data = [
				{ name: 'Tilora', url: 'https://tilora.home', icon: 'https://tilora.home/icon.png' },
				{ title: 'YouTube', href: 'https://youtube.com' },
				{ label: 'Reddit', link: 'https://reddit.com' },
			];
			const result = parseGenericJson(data);
			expect(result).toEqual([
				{ name: 'Tilora', url: 'https://tilora.home', icon: 'https://tilora.home/icon.png' },
				{ name: 'YouTube', url: 'https://youtube.com' },
				{ name: 'Reddit', url: 'https://reddit.com' },
			]);
		});

		it('parses objects wrapped with bookmarks or items key', () => {
			const data = {
				bookmarks: [{ name: 'Wikipedia', url: 'https://wikipedia.org' }],
			};
			const result = parseGenericJson(data);
			expect(result).toEqual([{ name: 'Wikipedia', url: 'https://wikipedia.org' }]);
		});
	});

	describe('parseCsv', () => {
		it('parses CSV with header row', () => {
			const csv = `Title,URL,Icon
GitHub,https://github.com,https://github.com/favicon.ico
Hacker News,https://news.ycombinator.com,
`;
			const result = parseCsv(csv);
			expect(result).toEqual([
				{ name: 'GitHub', url: 'https://github.com', icon: 'https://github.com/favicon.ico' },
				{ name: 'Hacker News', url: 'https://news.ycombinator.com' },
			]);
		});

		it('parses CSV without header row', () => {
			const csv = `DuckDuckGo,https://duckduckgo.com
Wikipedia,https://wikipedia.org
`;
			const result = parseCsv(csv);
			expect(result).toEqual([
				{ name: 'DuckDuckGo', url: 'https://duckduckgo.com' },
				{ name: 'Wikipedia', url: 'https://wikipedia.org' },
			]);
		});

		it('parses reversed URL,Name column ordering', () => {
			const csv = `https://duckduckgo.com,DuckDuckGo
https://wikipedia.org,Wikipedia
`;
			const result = parseCsv(csv);
			expect(result).toEqual([
				{ name: 'DuckDuckGo', url: 'https://duckduckgo.com' },
				{ name: 'Wikipedia', url: 'https://wikipedia.org' },
			]);
		});
	});

	describe('parseBookmarkText', () => {
		it('auto-detects JSON format from filename or content', () => {
			const jsonText = JSON.stringify([{ name: 'OpenAI', url: 'https://openai.com' }]);
			expect(parseBookmarkText(jsonText, 'bookmarks.json')).toEqual([{ name: 'OpenAI', url: 'https://openai.com' }]);
		});

		it('auto-detects HTML Netscape format', () => {
			const htmlText = '<DT><A HREF="https://matrix.org">Matrix</A>';
			expect(parseBookmarkText(htmlText, 'bookmarks.html')).toEqual([{ name: 'Matrix', url: 'https://matrix.org' }]);
		});

		it('returns empty array for empty or unparseable input', () => {
			expect(parseBookmarkText('', 'unknown.txt')).toEqual([]);
			expect(parseBookmarkText('plain text without urls', 'notes.txt')).toEqual([]);
		});
	});

	describe('importBookmarksFromFile', () => {
		it('reads a File and returns items', async () => {
			const file = new File(['<DT><A HREF="https://archlinux.org">Arch Linux</A>'], 'bookmarks.html', {
				type: 'text/html',
			});
			const items = await importBookmarksFromFile(file);
			expect(items).toEqual([{ name: 'Arch Linux', url: 'https://archlinux.org' }]);
		});

		it('throws an error if no bookmarks were found in file', async () => {
			const file = new File(['just some random text'], 'test.txt', { type: 'text/plain' });
			await expect(importBookmarksFromFile(file)).rejects.toThrow('No valid bookmarks found in the selected file.');
		});
	});
});
