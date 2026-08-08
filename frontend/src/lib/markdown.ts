import { browser } from '$app/environment';
import { Marked, type Tokens, type TokenizerAndRendererExtension } from 'marked';
import DOMPurify from 'dompurify';

export function escapeAttribute(value: string): string {
	return value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export function escapeHtml(value: string): string {
	return escapeAttribute(value).replace(/'/g, '&#39;');
}

export const ALLOWED_TAGS = [
	'p',
	'strong',
	'em',
	'u',
	's',
	'del',
	'code',
	'pre',
	'blockquote',
	'ul',
	'ol',
	'li',
	'a',
	'span',
	'br',
	'h1',
	'h2',
	'h3',
];
export const ALLOWED_ATTR = ['href', 'title', 'target', 'rel', 'class', 'role', 'tabindex'];

export interface MarkdownRenderer {
	marked: Marked;
	/**
	 * Renders markdown to sanitized HTML for use with `{@html}`. DOMPurify
	 * silently returns its input unsanitized when there's no `window` (e.g.
	 * during SSR), so parsing is skipped there in favor of an escaped
	 * plain-text fallback — the client re-renders with full formatting after
	 * hydration.
	 */
	render(content: string): string;
}

/**
 * Builds a `marked` instance configured with GFM, a link renderer that
 * only allows http(s) targets (opened in a new tab), and this app's HTML
 * allowlist, optionally extended with additional tokenizer extensions
 * (e.g. Discord's underline/spoiler dialect).
 */
export function createMarkdownRenderer(extensions: TokenizerAndRendererExtension[] = []): MarkdownRenderer {
	const marked = new Marked({ gfm: true, breaks: true });
	marked.use({
		extensions,
		renderer: {
			link({ href, title, tokens }: Tokens.Link) {
				const text = this.parser.parseInline(tokens);
				if (!/^https?:\/\//i.test(href)) return text;
				const titleAttr = title ? ` title="${escapeAttribute(title)}"` : '';
				return `<a href="${escapeAttribute(href)}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`;
			},
		},
	});

	return {
		marked,
		render(content: string): string {
			if (!browser) return escapeHtml(content);
			const html = marked.parse(content, { async: false });
			return DOMPurify.sanitize(html, { ALLOWED_TAGS, ALLOWED_ATTR });
		},
	};
}

export const renderMarkdown = createMarkdownRenderer().render;
