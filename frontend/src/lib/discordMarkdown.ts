import type { Token, Tokens, TokenizerAndRendererExtension } from 'marked';
import { createMarkdownRenderer, escapeHtml } from './markdown';

// Discord's markdown dialect differs from CommonMark/GFM in two ways that
// matter here: `__x__` means underline (not bold — that's `**x**`), and
// `||x||` is a spoiler with no CommonMark equivalent. Custom inline
// extensions run before marked's built-in tokenizers, so these take
// precedence over the default (wrong, for Discord) interpretation of `__`.
const underlineExtension: TokenizerAndRendererExtension = {
	name: 'underline',
	level: 'inline',
	start(src) {
		return src.match(/__/)?.index;
	},
	tokenizer(src) {
		const match = /^__(?!_)([\s\S]+?)__(?!_)/.exec(src);
		if (!match) return undefined;
		return {
			type: 'underline',
			raw: match[0],
			text: match[1],
			tokens: this.lexer.inlineTokens(match[1]),
		};
	},
	renderer(token) {
		return `<u>${this.parser.parseInline(token.tokens ?? [])}</u>`;
	},
};

const spoilerExtension: TokenizerAndRendererExtension = {
	name: 'spoiler',
	level: 'inline',
	start(src) {
		return src.match(/\|\|/)?.index;
	},
	tokenizer(src) {
		const match = /^\|\|([\s\S]+?)\|\|/.exec(src);
		if (!match) return undefined;
		return {
			type: 'spoiler',
			raw: match[0],
			text: match[1],
			tokens: this.lexer.inlineTokens(match[1]),
		};
	},
	renderer(token) {
		return `<span class="spoiler" role="button" tabindex="0">${this.parser.parseInline(token.tokens ?? [])}</span>`;
	},
};

const { marked, render: renderDiscordMarkdown } = createMarkdownRenderer([underlineExtension, spoilerExtension]);

/**
 * Renders Discord message content (Discord's markdown dialect) to sanitized
 * HTML for use with `{@html}`.
 */
export { renderDiscordMarkdown };

// `{@html}` content sits outside Svelte's reactive tree, so spoiler reveal
// is wired up via event delegation on the containing element instead of a
// per-element handler. The `.spoiler` spans marked renders already carry
// `role="button" tabindex="0"` so they're focusable and keyboard-operable;
// these two handlers just need attaching to their container.

/** Click-delegation handler for spoiler reveal. */
export function toggleSpoiler(event: MouseEvent): void {
	const target = event.target;
	if (!(target instanceof Element)) return;
	target.closest('.spoiler')?.classList.toggle('revealed');
}

/** Keydown-delegation handler for spoiler reveal (Enter/Space, matching native button semantics). */
export function toggleSpoilerKey(event: KeyboardEvent): void {
	if (event.key !== 'Enter' && event.key !== ' ') return;
	const target = event.target;
	if (!(target instanceof Element) || !target.closest('.spoiler')) return;
	event.preventDefault();
	target.closest('.spoiler')?.classList.toggle('revealed');
}

export interface FormattedSegment {
	text: string;
	bold?: boolean;
	italic?: boolean;
	underline?: boolean;
	strike?: boolean;
	code?: boolean;
	link?: boolean;
	spoiler?: boolean;
}

export interface FormattedChar {
	ch: string;
	bold?: boolean;
	italic?: boolean;
	underline?: boolean;
	strike?: boolean;
	code?: boolean;
	link?: boolean;
	spoiler?: boolean;
}

type FormatFlags = Pick<FormattedSegment, 'bold' | 'italic' | 'underline' | 'strike' | 'code' | 'link'>;

const REDACTION_CHAR = '█';

/**
 * Parses Discord-dialect markdown (the same dialect `renderDiscordMarkdown`
 * renders to HTML) into per-line, per-segment formatting for renderers that
 * can't use `{@html}` directly — the screensaver's plain-text sign
 * animations, which need to know which characters are bold/italic/etc.
 * rather than being handed markup. Reuses the same `marked` instance/
 * extensions so the dialect never drifts between the two.
 *
 * `marked.lexer` doesn't touch the DOM (unlike `renderDiscordMarkdown`,
 * which needs DOMPurify), so this works identically during SSR.
 */
export function parseFormattedLines(content: string): FormattedSegment[][] {
	return marked.lexer(content).flatMap(flattenBlock);
}

/**
 * Explodes formatted segments into one entry per character, for renderers
 * that animate character-by-character (Matrix, Flipboard). Uses
 * `Array.from` rather than `.split('')` so multi-code-unit glyphs count and
 * render as a single character.
 */
export function segmentsToChars(segments: FormattedSegment[]): FormattedChar[] {
	return segments.flatMap((segment) =>
		Array.from(segment.text).map((ch) => ({
			ch,
			bold: segment.bold,
			italic: segment.italic,
			underline: segment.underline,
			strike: segment.strike,
			code: segment.code,
			link: segment.link,
			spoiler: segment.spoiler,
		})),
	);
}

/**
 * Renders formatted segments to a small, hardcoded set of inline tags
 * around explicitly-escaped text — safe by construction (no raw markdown
 * source ever passes through unescaped), so unlike `renderDiscordMarkdown`
 * this needs no DOMPurify pass.
 */
export function segmentsToHtml(segments: FormattedSegment[]): string {
	return segments.map(segmentToHtml).join('');
}

function segmentToHtml(segment: FormattedSegment): string {
	let html = escapeHtml(segment.text);
	if (segment.code) html = `<code>${html}</code>`;
	if (segment.bold) html = `<strong>${html}</strong>`;
	if (segment.italic) html = `<em>${html}</em>`;
	if (segment.underline) html = `<u>${html}</u>`;
	if (segment.strike) html = `<s>${html}</s>`;
	if (segment.link) html = `<span class="md-link">${html}</span>`;
	return html;
}

/**
 * Converts Discord's `<@123>`/`<@&123>`/`<#123>`/`<a:name:123>` reference
 * syntax to readable plain text. Kept separate from `parseFormattedLines` —
 * these aren't part of the markdown dialect, and `marked` would otherwise
 * misparse the angle brackets as raw HTML — so callers that know they have
 * Discord content run this first.
 */
export function replaceDiscordReferences(content: string): string {
	return content
		.replace(/<@!?\d+>/g, '@user')
		.replace(/<@&\d+>/g, '@role')
		.replace(/<#\d+>/g, '#channel')
		.replace(/<a?:(\w+):\d+>/g, ':$1:');
}

function tokenChildren(token: Token): Token[] {
	return (token as { tokens?: Token[] }).tokens ?? [];
}

function flattenBlock(token: Token): FormattedSegment[][] {
	switch (token.type) {
		case 'paragraph':
		case 'text':
			return flattenInline(tokenChildren(token), {});
		case 'heading':
			return flattenInline(tokenChildren(token), { bold: true });
		case 'blockquote':
			return (token as Tokens.Blockquote).tokens.flatMap(flattenBlock);
		case 'list': {
			const list = token as Tokens.List;
			return list.items.flatMap((item, i) => {
				const itemLines = item.tokens.flatMap(flattenBlock);
				if (itemLines.length === 0) itemLines.push([]);
				const prefix = list.ordered ? `${i + 1}. ` : '• ';
				itemLines[0] = [{ text: prefix }, ...itemLines[0]];
				return itemLines;
			});
		}
		case 'code':
			return (token as Tokens.Code).text.split('\n').map((line) => [{ text: line, code: true }]);
		case 'space':
		case 'hr':
			return [];
		default:
			return token.raw?.trim() ? [[{ text: token.raw.trim() }]] : [];
	}
}

function flattenInline(tokens: Token[], format: FormatFlags): FormattedSegment[][] {
	const lines: FormattedSegment[][] = [[]];
	const push = (segment: FormattedSegment) => lines[lines.length - 1].push(segment);
	const mergeLines = (sub: FormattedSegment[][]) => {
		if (sub.length === 0) return;
		lines[lines.length - 1].push(...sub[0]);
		lines.push(...sub.slice(1));
	};

	for (const token of tokens) {
		switch (token.type) {
			case 'text':
			case 'escape':
				push({ text: (token as Tokens.Text | Tokens.Escape).text, ...format });
				break;
			case 'strong':
				mergeLines(flattenInline(tokenChildren(token), { ...format, bold: true }));
				break;
			case 'em':
				mergeLines(flattenInline(tokenChildren(token), { ...format, italic: true }));
				break;
			case 'underline':
				mergeLines(flattenInline(tokenChildren(token), { ...format, underline: true }));
				break;
			case 'del':
				mergeLines(flattenInline(tokenChildren(token), { ...format, strike: true }));
				break;
			case 'link':
				mergeLines(flattenInline(tokenChildren(token), { ...format, link: true }));
				break;
			case 'codespan':
				push({ text: (token as Tokens.Codespan).text, ...format, code: true });
				break;
			case 'spoiler':
				push(redactSpoiler(tokenChildren(token), format));
				break;
			case 'br':
				lines.push([]);
				break;
			case 'image':
				push({ text: (token as Tokens.Image).text || (token as Tokens.Image).href, ...format });
				break;
			default:
				if (token.raw) push({ text: token.raw, ...format });
		}
	}
	return lines;
}

function redactSpoiler(innerTokens: Token[], format: FormatFlags): FormattedSegment {
	const innerLines = flattenInline(innerTokens, {});
	const visibleLength = innerLines.reduce(
		(sum, line) => sum + line.reduce((lineSum, segment) => lineSum + segment.text.length, 0),
		0,
	);
	return { text: REDACTION_CHAR.repeat(Math.max(visibleLength, 1)), ...format, spoiler: true };
}
