import type { BookmarkItem } from '$lib/api';
import { isSafeUrl } from '$lib/url';

/**
 * Parses HTML bookmarks in Netscape Bookmark format.
 * This is the standard export format for Chrome, Firefox, Safari, Edge,
 * Raindrop, Pinboard, Shaarli, Pocket, Linkwarden, etc.
 */
export function parseNetscapeHtml(html: string): BookmarkItem[] {
	const items: BookmarkItem[] = [];

	// Parse using DOMParser if available in browser / test environment
	if (typeof DOMParser !== 'undefined') {
		const doc = new DOMParser().parseFromString(html, 'text/html');
		const links = doc.querySelectorAll('a');
		for (const link of links) {
			const href = link.getAttribute('href')?.trim() || '';
			const name = (link.textContent || '').trim();
			const icon = link.getAttribute('icon') || link.getAttribute('icon_uri') || undefined;

			if (href && name && isSafeUrl(href)) {
				items.push({
					name,
					url: href,
					...(icon && isSafeUrl(icon) ? { icon } : {}),
				});
			}
		}
		if (items.length > 0) {
			return items;
		}
	}

	// Fallback regex parser for non-DOM environments or partial chunks
	const linkRegex = /<a\b[^>]*\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))[^>]*>([\s\S]*?)<\/a>/gi;
	const iconRegex = /\bicon(?:_uri)?\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i;

	let match: RegExpExecArray | null;
	while ((match = linkRegex.exec(html)) !== null) {
		const url = (match[1] || match[2] || match[3] || '').trim();
		const rawName = (match[4] || '').replace(/<[^>]+>/g, '').trim();
		if (!url || !rawName || !isSafeUrl(url)) continue;

		const fullTag = match[0];
		const iconMatch = iconRegex.exec(fullTag);
		const icon = (iconMatch ? iconMatch[1] || iconMatch[2] || iconMatch[3] : undefined)?.trim();

		items.push({
			name: rawName,
			url,
			...(icon && isSafeUrl(icon) ? { icon } : {}),
		});
	}

	return items;
}

/**
 * Parses Chromium profile Bookmarks JSON format (e.g. Chrome/Brave/Edge bookmarks file).
 */
// Caps folder-nesting recursion so a pathological or corrupted export (e.g.
// thousands of nested folders) can't blow the call stack -- deeper branches
// are just skipped rather than importing partial/garbage data.
const MAX_TRAVERSAL_DEPTH = 50;

export function parseChromiumJson(data: unknown): BookmarkItem[] {
	const items: BookmarkItem[] = [];

	function traverse(node: unknown, depth: number) {
		if (depth > MAX_TRAVERSAL_DEPTH) return;
		if (!node || typeof node !== 'object') return;
		const record = node as Record<string, unknown>;

		if (record.type === 'url' || (record.url && (record.name || record.title))) {
			const url = String(record.url || '').trim();
			const name = String(record.name || record.title || '').trim();
			if (url && name && isSafeUrl(url)) {
				items.push({
					name,
					url,
					...(record.icon && isSafeUrl(String(record.icon)) ? { icon: String(record.icon) } : {}),
				});
			}
		}

		if (Array.isArray(record.children)) {
			for (const child of record.children) {
				traverse(child, depth + 1);
			}
		} else if (record.roots && typeof record.roots === 'object') {
			const roots = record.roots as Record<string, unknown>;
			for (const rootKey of Object.keys(roots)) {
				traverse(roots[rootKey], depth + 1);
			}
		}
	}

	traverse(data, 0);
	return items;
}

/**
 * Parses generic JSON bookmarks export (arrays of objects or { bookmarks: [...] }).
 */
export function parseGenericJson(data: unknown): BookmarkItem[] {
	const items: BookmarkItem[] = [];
	const record = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
	const rawList = Array.isArray(data)
		? data
		: Array.isArray(record.bookmarks)
			? record.bookmarks
			: Array.isArray(record.items)
				? record.items
				: Array.isArray(record.links)
					? record.links
					: [];

	for (const item of rawList) {
		if (!item || typeof item !== 'object') continue;
		const row = item as Record<string, unknown>;
		const name = String(row.name || row.title || row.label || row.description || '').trim();
		const url = String(row.url || row.href || row.link || '').trim();
		const icon = row.icon ? String(row.icon).trim() : undefined;

		if (name && url && isSafeUrl(url)) {
			items.push({
				name,
				url,
				...(icon && isSafeUrl(icon) ? { icon } : {}),
			});
		}
	}

	return items;
}

/**
 * Parses simple CSV bookmarks format (with or without headers: name,url,icon).
 */
export function parseCsv(text: string): BookmarkItem[] {
	const items: BookmarkItem[] = [];
	const lines = text
		.split(/\r?\n/)
		.map((line) => line.trim())
		.filter((line) => line.length > 0);

	if (lines.length === 0) return items;

	// Check if first line is a header
	let startIndex = 0;
	let nameIdx = 0;
	let urlIdx = 1;
	let iconIdx = -1;

	const firstLineCols = splitCsvLine(lines[0]);
	const headerLower = firstLineCols.map((c) => c.toLowerCase().trim());
	const hasNameHeader = headerLower.includes('name') || headerLower.includes('title') || headerLower.includes('label');
	const hasUrlHeader = headerLower.includes('url') || headerLower.includes('href') || headerLower.includes('link');

	if (hasNameHeader && hasUrlHeader) {
		startIndex = 1;
		nameIdx = headerLower.findIndex((c) => ['name', 'title', 'label'].includes(c));
		urlIdx = headerLower.findIndex((c) => ['url', 'href', 'link'].includes(c));
		iconIdx = headerLower.findIndex((c) => ['icon', 'favicon', 'icon_url'].includes(c));
	} else if (firstLineCols.length >= 2) {
		// Detect if first column is url or name
		if (isSafeUrl(firstLineCols[0]) && !isSafeUrl(firstLineCols[1])) {
			urlIdx = 0;
			nameIdx = 1;
		}
	}

	for (let i = startIndex; i < lines.length; i++) {
		const cols = splitCsvLine(lines[i]);
		if (cols.length < 2) continue;

		const name = (cols[nameIdx] || '').trim();
		const url = (cols[urlIdx] || '').trim();
		const icon = iconIdx >= 0 && cols[iconIdx] ? cols[iconIdx].trim() : undefined;

		if (name && url && isSafeUrl(url)) {
			items.push({
				name,
				url,
				...(icon && isSafeUrl(icon) ? { icon } : {}),
			});
		}
	}

	return items;
}

function splitCsvLine(line: string): string[] {
	const result: string[] = [];
	let current = '';
	let inQuotes = false;
	const delimiter = line.includes('\t') ? '\t' : line.includes(';') && !line.includes(',') ? ';' : ',';

	for (let i = 0; i < line.length; i++) {
		const char = line[i];
		if (char === '"') {
			if (inQuotes && line[i + 1] === '"') {
				current += '"';
				i++;
			} else {
				inQuotes = !inQuotes;
			}
		} else if (char === delimiter && !inQuotes) {
			result.push(current.trim());
			current = '';
		} else {
			current += char;
		}
	}
	result.push(current.trim());
	return result;
}

/**
 * Parses raw text content of an imported bookmark file according to detected format.
 */
export function parseBookmarkText(content: string, fileName?: string): BookmarkItem[] {
	const trimmed = content.trim();
	if (!trimmed) return [];

	const lowerName = (fileName || '').toLowerCase();

	// 1. JSON detection
	if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
		try {
			const parsed: unknown = JSON.parse(trimmed);
			if (
				parsed &&
				typeof parsed === 'object' &&
				('roots' in parsed || ('checksum' in parsed && 'version' in parsed))
			) {
				const chromiumItems = parseChromiumJson(parsed);
				if (chromiumItems.length > 0) return chromiumItems;
			}
			const genericItems = parseGenericJson(parsed);
			if (genericItems.length > 0) return genericItems;
		} catch {
			// not valid JSON, fall through
		}
	}

	// 2. HTML detection (Netscape bookmark format)
	if (
		lowerName.endsWith('.html') ||
		lowerName.endsWith('.htm') ||
		trimmed.includes('<!DOCTYPE NETSCAPE-Bookmark-file-1>') ||
		trimmed.toLowerCase().includes('<h3') ||
		trimmed.toLowerCase().includes('<a href=')
	) {
		const htmlItems = parseNetscapeHtml(trimmed);
		if (htmlItems.length > 0) return htmlItems;
	}

	// 3. CSV / TSV detection
	if (lowerName.endsWith('.csv') || lowerName.endsWith('.tsv') || trimmed.includes(',') || trimmed.includes(';')) {
		const csvItems = parseCsv(trimmed);
		if (csvItems.length > 0) return csvItems;
	}

	// 4. Try HTML parser fallback
	const fallbackHtml = parseNetscapeHtml(trimmed);
	if (fallbackHtml.length > 0) return fallbackHtml;

	return [];
}

/**
 * Reads a File object and extracts bookmark items.
 */
export async function importBookmarksFromFile(file: File): Promise<BookmarkItem[]> {
	const text = await file.text();
	const items = parseBookmarkText(text, file.name);
	if (items.length === 0) {
		throw new Error('No valid bookmarks found in the selected file.');
	}
	return items;
}
