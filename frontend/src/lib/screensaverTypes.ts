// Widget types that make sense as a full-screen screensaver slide. Kept
// separate from `widgetComponents.ts`'s full type registry so the Settings
// picker filter and `Screensaver.svelte`'s render/skip logic share one
// source of truth instead of drifting apart.

export const SCREENSAVER_VISUAL_TYPES = [
	'clock',
	'date',
	'calendar',
	'calendar_caldav',
	'calendar_microsoft',
	'photos',
	'weather',
	'flights',
] as const;

export const SCREENSAVER_WORDY_TYPES = ['rss', 'sports', 'ai', 'discord', 'message'] as const;

export const SCREENSAVER_ALLOWED_TYPES: string[] = [...SCREENSAVER_VISUAL_TYPES, ...SCREENSAVER_WORDY_TYPES];

export function isScreensaverVisualType(type: string): boolean {
	return (SCREENSAVER_VISUAL_TYPES as readonly string[]).includes(type);
}

export function isScreensaverWordyType(type: string): boolean {
	return (SCREENSAVER_WORDY_TYPES as readonly string[]).includes(type);
}

export function isScreensaverAllowedType(type: string): boolean {
	return SCREENSAVER_ALLOWED_TYPES.includes(type);
}

export const TEXT_ANIMATION_STYLES = ['marquee', 'matrix', 'flipboard', 'led_dots'] as const;

export type TextAnimationStyle = (typeof TEXT_ANIMATION_STYLES)[number];

export const FLIPBOARD_PATTERNS = ['top_to_bottom', 'random'] as const;

export type FlipboardPattern = (typeof FLIPBOARD_PATTERNS)[number];
