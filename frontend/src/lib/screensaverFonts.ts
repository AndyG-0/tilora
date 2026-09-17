// Curated font-family choices for the screensaver's text-animation styles
// (Marquee, Matrix, Flipboard, LED Dots, Plain). A fixed list rather than
// freeform text input keeps rendering predictable on kiosk displays. 'default'
// means "no override" -- each component keeps its own thematic font (e.g. LED
// Dots keeps its Doto look) by falling through to its own CSS fallback.

export const SCREENSAVER_FONT_FAMILIES = ['default', 'sans', 'mono', 'serif'] as const;

export type ScreensaverFontFamily = (typeof SCREENSAVER_FONT_FAMILIES)[number];

const FONT_FAMILY_CSS: Record<Exclude<ScreensaverFontFamily, 'default'>, string> = {
	sans: 'system-ui, sans-serif',
	mono: "ui-monospace, 'Courier New', monospace",
	serif: 'ui-serif, Georgia, serif',
};

// Resolves a font-family key to a CSS `font-family` value, or `undefined`
// for 'default' so callers can skip setting the custom property entirely
// and let each component's own stylesheet fallback apply.
export function resolveScreensaverFontFamily(family: ScreensaverFontFamily | undefined): string | undefined {
	if (!family || family === 'default') return undefined;
	return FONT_FAMILY_CSS[family];
}
