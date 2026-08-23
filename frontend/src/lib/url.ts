// Same allowlist as markdown.ts's link renderer — only http(s) targets are
// safe to bind directly to an href; anything else (javascript:, data:, ...)
// renders as inert text instead of a clickable link.
export function isSafeUrl(url: string | null | undefined): boolean {
	return !!url && /^https?:\/\//i.test(url);
}
