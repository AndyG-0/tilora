import { describe, it, expect } from 'vitest';
import { isSafeUrl } from './url';

describe('isSafeUrl', () => {
	it('allows http and https URLs', () => {
		expect(isSafeUrl('http://example.com')).toBe(true);
		expect(isSafeUrl('https://example.com')).toBe(true);
	});

	it('rejects javascript: and data: URIs', () => {
		expect(isSafeUrl('javascript:alert(1)')).toBe(false);
		expect(isSafeUrl('data:text/html,<script>alert(1)</script>')).toBe(false);
	});

	it('rejects empty, null, or undefined values', () => {
		expect(isSafeUrl('')).toBe(false);
		expect(isSafeUrl(null)).toBe(false);
		expect(isSafeUrl(undefined)).toBe(false);
	});
});
