import { afterEach, describe, expect, it, vi } from 'vitest';
import { detectBrowser, getInsecureOriginInfo, isChromeBrowser, isPrivateIpHostname } from './network';

describe('network', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	describe('isPrivateIpHostname', () => {
		it.each(['10.0.0.1', '10.255.255.255', '172.16.0.1', '172.31.255.255', '192.168.1.50', '192.168.0.1'])(
			'is true for private IPv4 address %s',
			(hostname) => {
				expect(isPrivateIpHostname(hostname)).toBe(true);
			},
		);

		it.each(['8.8.8.8', '172.15.0.1', '172.32.0.1', '11.0.0.1', '193.168.1.1', 'localhost', 'example.com', '::1'])(
			'is false for non-private-IPv4 host %s',
			(hostname) => {
				expect(isPrivateIpHostname(hostname)).toBe(false);
			},
		);
	});

	describe('detectBrowser', () => {
		it('detects Chrome on desktop', () => {
			expect(
				detectBrowser(
					'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
				),
			).toBe('chrome');
		});

		it('detects Chrome on iOS (CriOS)', () => {
			expect(
				detectBrowser(
					'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.0.0 Mobile/15E148 Safari/604.1',
				),
			).toBe('chrome');
		});

		it('detects Edge on desktop', () => {
			expect(
				detectBrowser(
					'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
				),
			).toBe('edge');
		});

		it('detects Edge on iOS (EdgiOS)', () => {
			expect(
				detectBrowser(
					'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 EdgiOS/120.0.0.0 Mobile/15E148 Safari/605.1.15',
				),
			).toBe('edge');
		});

		it('detects Brave via Brave user agent pattern', () => {
			expect(
				detectBrowser(
					'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Brave/120.0.0.0',
				),
			).toBe('brave');
		});

		it('detects Safari on macOS', () => {
			expect(
				detectBrowser(
					'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
				),
			).toBe('safari');
		});

		it('detects Safari on iOS', () => {
			expect(
				detectBrowser(
					'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
				),
			).toBe('safari');
		});

		it('detects Firefox on desktop', () => {
			expect(
				detectBrowser('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0'),
			).toBe('firefox');
		});

		it('detects Firefox on iOS (FxiOS)', () => {
			expect(
				detectBrowser(
					'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/120.0 Mobile/15E148 Safari/605.1.15',
				),
			).toBe('firefox');
		});

		it('returns other for unrecognized user agents', () => {
			expect(detectBrowser('CustomBot/1.0')).toBe('other');
		});
	});

	describe('isChromeBrowser', () => {
		it('is true for a Chrome user agent', () => {
			vi.stubGlobal('navigator', {
				userAgent:
					'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
			});
			expect(isChromeBrowser()).toBe(true);
		});

		it('is false for Edge, which also contains "Chrome" in its UA', () => {
			vi.stubGlobal('navigator', {
				userAgent:
					'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
			});
			expect(isChromeBrowser()).toBe(false);
		});

		it('is false for Safari user agent', () => {
			vi.stubGlobal('navigator', {
				userAgent:
					'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15) AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15',
			});
			expect(isChromeBrowser()).toBe(false);
		});
	});

	describe('getInsecureOriginInfo', () => {
		it('flags an http origin at a private IP as needing the flag for Chrome', () => {
			vi.stubGlobal('window', {
				location: { protocol: 'http:', hostname: '192.168.1.50', origin: 'http://192.168.1.50:8080' },
				isSecureContext: false,
			});
			vi.stubGlobal('navigator', { userAgent: 'Chrome/120.0.0.0' });

			expect(getInsecureOriginInfo()).toEqual({
				needsInsecureOriginFlag: true,
				browser: 'chrome',
				isChrome: true,
				isChromium: true,
				origin: 'http://192.168.1.50:8080',
			});
		});

		it('flags an http origin at a private IP for Safari', () => {
			vi.stubGlobal('window', {
				location: { protocol: 'http:', hostname: '192.168.1.50', origin: 'http://192.168.1.50:8080' },
				isSecureContext: false,
			});
			vi.stubGlobal('navigator', {
				userAgent:
					'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
			});

			expect(getInsecureOriginInfo()).toEqual({
				needsInsecureOriginFlag: true,
				browser: 'safari',
				isChrome: false,
				isChromium: false,
				origin: 'http://192.168.1.50:8080',
			});
		});

		it('flags an http origin at a private IP for Edge', () => {
			vi.stubGlobal('window', {
				location: { protocol: 'http:', hostname: '192.168.1.50', origin: 'http://192.168.1.50:8080' },
				isSecureContext: false,
			});
			vi.stubGlobal('navigator', {
				userAgent:
					'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
			});

			expect(getInsecureOriginInfo()).toEqual({
				needsInsecureOriginFlag: true,
				browser: 'edge',
				isChrome: false,
				isChromium: true,
				origin: 'http://192.168.1.50:8080',
			});
		});

		it('does not flag when window.isSecureContext is true', () => {
			vi.stubGlobal('window', {
				location: { protocol: 'http:', hostname: '192.168.1.50', origin: 'http://192.168.1.50:8080' },
				isSecureContext: true,
			});
			vi.stubGlobal('navigator', { userAgent: 'Chrome/120.0.0.0' });

			expect(getInsecureOriginInfo()?.needsInsecureOriginFlag).toBe(false);
		});

		it('does not flag an https origin at a private IP', () => {
			vi.stubGlobal('window', {
				location: { protocol: 'https:', hostname: '192.168.1.50', origin: 'https://192.168.1.50' },
				isSecureContext: true,
			});

			expect(getInsecureOriginInfo()?.needsInsecureOriginFlag).toBe(false);
		});

		it('does not flag an http origin at a public hostname', () => {
			vi.stubGlobal('window', {
				location: { protocol: 'http:', hostname: 'example.com', origin: 'http://example.com' },
			});

			expect(getInsecureOriginInfo()?.needsInsecureOriginFlag).toBe(false);
		});
	});
});
