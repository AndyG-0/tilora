import { browser } from '$app/environment';

const ROTATION_KEY = 'screensaver:rotationIndex';
const cursorKey = (widgetId: string) => `screensaver:cursor:${widgetId}`;

function readInt(key: string): number {
	if (!browser) return 0;
	try {
		const raw = localStorage.getItem(key);
		const parsed = raw === null ? 0 : parseInt(raw, 10);
		return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
	} catch {
		return 0;
	}
}

function writeInt(key: string, value: number): void {
	if (!browser) return;
	try {
		localStorage.setItem(key, String(value));
	} catch {
		// private browsing / storage disabled — best effort only
	}
}

export function getRotationIndex(): number {
	return readInt(ROTATION_KEY);
}

export function setRotationIndex(index: number): void {
	writeInt(ROTATION_KEY, index);
}

export function getCursor(widgetId: string): number {
	return readInt(cursorKey(widgetId));
}

export function setCursor(widgetId: string, index: number): void {
	writeInt(cursorKey(widgetId), index);
}
