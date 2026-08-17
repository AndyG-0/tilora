import { browser } from '$app/environment';

const STORAGE_KEY = 'tilora:jellyfin:force-transcode';
const TTL_MS = 7 * 24 * 60 * 60 * 1000;

interface CacheEntry {
	value: true;
	expiresAt: number;
}

export function shouldForceTranscode(): boolean {
	if (!browser) return false;
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) return false;
		const entry = JSON.parse(raw) as CacheEntry;
		if (!entry?.value || typeof entry.expiresAt !== 'number' || entry.expiresAt < Date.now()) {
			localStorage.removeItem(STORAGE_KEY);
			return false;
		}
		return true;
	} catch {
		return false;
	}
}

export function markDirectPlayFailed(): void {
	if (!browser) return;
	try {
		const entry: CacheEntry = { value: true, expiresAt: Date.now() + TTL_MS };
		localStorage.setItem(STORAGE_KEY, JSON.stringify(entry));
	} catch {
		// private browsing / storage disabled — best effort only
	}
}
