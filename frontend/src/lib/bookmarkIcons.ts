import type { BookmarkItem } from '$lib/api';

// Bookmarks don't have their icon fetched/proxied server-side (self-hosted
// app — no reason to route users' link domains through a third party), so
// this derives the icon straight from the browser: prefer a manually-set
// override, otherwise fall back to the domain's own root favicon.
export function faviconSrc(bookmark: BookmarkItem): string | undefined {
	const override = bookmark.icon?.trim();
	if (override) return override;

	try {
		return `${new URL(bookmark.url).origin}/favicon.ico`;
	} catch {
		return undefined;
	}
}

// Many sites don't serve a favicon at their root, or block hotlinking —
// hide the broken image instead of showing a broken-image icon.
export function hideBrokenIcon(event: Event) {
	(event.currentTarget as HTMLImageElement).style.display = 'none';
}
