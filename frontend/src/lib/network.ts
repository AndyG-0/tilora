// Detects when the current page is served over an insecure origin (plain
// HTTP to a private/internal IP) where browsers block microphone access
// unless the origin is manually treated as secure (e.g. via flags in Chromium)
// or accessed over HTTPS with trusted certificates (e.g. Safari / Firefox).

const PRIVATE_IPV4_PATTERN =
	/^(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})$/;

export function isPrivateIpHostname(hostname: string): boolean {
	return PRIVATE_IPV4_PATTERN.test(hostname);
}

export type BrowserType = 'chrome' | 'chromium' | 'edge' | 'brave' | 'safari' | 'firefox' | 'other';

export function detectBrowser(customUserAgent?: string): BrowserType {
	const ua = customUserAgent ?? (typeof navigator !== 'undefined' ? navigator.userAgent : '');
	if (!ua) return 'other';

	if (/Edg\//i.test(ua) || /EdgiOS\//i.test(ua) || /EdgA\//i.test(ua) || /Edge\//i.test(ua)) {
		return 'edge';
	}
	if (
		/Brave\//i.test(ua) ||
		(typeof navigator !== 'undefined' &&
			(navigator as unknown as { brave?: { isBrave?: () => Promise<boolean> } }).brave !== undefined)
	) {
		return 'brave';
	}
	if (/Firefox\//i.test(ua) || /FxiOS\//i.test(ua)) {
		return 'firefox';
	}
	if (/OPR\//i.test(ua) || /Opera\//i.test(ua)) {
		return 'other';
	}
	if (/Chromium\//i.test(ua)) {
		return 'chromium';
	}
	if (/Chrome\//i.test(ua) || /CriOS\//i.test(ua)) {
		return 'chrome';
	}
	if (/Safari\//i.test(ua) && !/Android/i.test(ua)) {
		return 'safari';
	}
	return 'other';
}

export function isChromeBrowser(): boolean {
	return detectBrowser() === 'chrome';
}

export function isNativeSpeechReliable(customUserAgent?: string): boolean {
	const b = detectBrowser(customUserAgent);
	return b === 'chrome' || b === 'edge' || b === 'safari';
}

export interface InsecureOriginInfo {
	needsInsecureOriginFlag: boolean;
	browser: BrowserType;
	isChrome: boolean;
	isChromium: boolean;
	origin: string;
}

export function getInsecureOriginInfo(): InsecureOriginInfo | null {
	if (typeof window === 'undefined') return null;
	const { protocol, hostname, origin } = window.location;
	const isSecure = typeof window.isSecureContext === 'boolean' ? window.isSecureContext : protocol === 'https:';
	const browser = detectBrowser();
	const isChromium = browser === 'chrome' || browser === 'chromium' || browser === 'edge' || browser === 'brave';

	return {
		needsInsecureOriginFlag: !isSecure && protocol === 'http:' && isPrivateIpHostname(hostname),
		browser,
		isChrome: browser === 'chrome',
		isChromium,
		origin,
	};
}
