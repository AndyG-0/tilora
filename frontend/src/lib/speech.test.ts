import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { isSpeechRecognitionSupported, isSpeechSynthesisSupported, listenOnce, playChime, speak } from './speech';

describe('speech', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		// @ts-expect-error -- test-only cleanup of a property speech.ts adds
		delete window.SpeechRecognition;
		// @ts-expect-error -- test-only cleanup of a property speech.ts adds
		delete window.webkitSpeechRecognition;
	});

	describe('isSpeechRecognitionSupported', () => {
		it('is false when neither constructor exists', () => {
			expect(isSpeechRecognitionSupported()).toBe(false);
		});

		it('is true when SpeechRecognition exists', () => {
			// @ts-expect-error -- minimal stub, not a full SpeechRecognition impl
			window.SpeechRecognition = class {};
			expect(isSpeechRecognitionSupported()).toBe(true);
		});

		it('is true when only the webkit-prefixed constructor exists', () => {
			// @ts-expect-error -- minimal stub, not a full SpeechRecognition impl
			window.webkitSpeechRecognition = class {};
			expect(isSpeechRecognitionSupported()).toBe(true);
		});
	});

	describe('isSpeechSynthesisSupported', () => {
		it('reflects whether window.speechSynthesis is present', () => {
			expect(isSpeechSynthesisSupported()).toBe('speechSynthesis' in window);
		});
	});

	describe('speak', () => {
		class FakeUtterance {
			text: string;
			constructor(text: string) {
				this.text = text;
			}
		}

		beforeEach(() => {
			vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance);
		});

		it('cancels any in-progress utterance and speaks the new text', () => {
			const cancel = vi.fn();
			const speakFn = vi.fn();
			vi.stubGlobal('speechSynthesis', { cancel, speak: speakFn });

			speak('hello there');

			expect(cancel).toHaveBeenCalled();
			expect(speakFn).toHaveBeenCalledTimes(1);
			expect(speakFn.mock.calls[0][0]).toBeInstanceOf(FakeUtterance);
			expect(speakFn.mock.calls[0][0].text).toBe('hello there');
		});

		it('does nothing for empty text', () => {
			const cancel = vi.fn();
			const speakFn = vi.fn();
			vi.stubGlobal('speechSynthesis', { cancel, speak: speakFn });

			speak('');

			expect(cancel).not.toHaveBeenCalled();
			expect(speakFn).not.toHaveBeenCalled();
		});
	});

	describe('listenOnce', () => {
		it('rejects when speech recognition is unsupported', async () => {
			await expect(listenOnce()).rejects.toThrow('not supported');
		});

		it('resolves with the first final transcript', async () => {
			class FakeRecognition {
				lang = '';
				interimResults = true;
				maxAlternatives = 1;
				onresult: ((event: unknown) => void) | null = null;
				onerror: (() => void) | null = null;
				onend: (() => void) | null = null;
				start() {
					this.onresult?.({ results: { 0: { 0: { transcript: 'what is the weather' } } } });
				}
			}
			// @ts-expect-error -- minimal stub, not a full SpeechRecognition impl
			window.SpeechRecognition = FakeRecognition;

			await expect(listenOnce()).resolves.toBe('what is the weather');
		});

		it('rejects when recognition errors out', async () => {
			class FakeRecognition {
				lang = '';
				interimResults = true;
				maxAlternatives = 1;
				onresult: (() => void) | null = null;
				onerror: ((event: unknown) => void) | null = null;
				onend: (() => void) | null = null;
				start() {
					this.onerror?.(new Event('error'));
				}
			}
			// @ts-expect-error -- minimal stub, not a full SpeechRecognition impl
			window.SpeechRecognition = FakeRecognition;

			await expect(listenOnce()).rejects.toThrow('failed');
		});
	});

	describe('playChime', () => {
		let start: ReturnType<typeof vi.fn>;
		let stop: ReturnType<typeof vi.fn>;
		let close: ReturnType<typeof vi.fn>;

		beforeEach(() => {
			start = vi.fn();
			stop = vi.fn();
			close = vi.fn();
			const oscillator = {
				type: '',
				frequency: { value: 0 },
				connect: vi.fn(),
				start,
				stop,
				onended: null as (() => void) | null,
			};
			const gain = {
				gain: { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() },
				connect: vi.fn(),
			};
			class FakeAudioContext {
				currentTime = 0;
				destination = {};
				createOscillator() {
					return oscillator;
				}
				createGain() {
					return gain;
				}
				close = close;
			}
			vi.stubGlobal('AudioContext', FakeAudioContext);
		});

		it('starts and stops an oscillator', () => {
			playChime();

			expect(start).toHaveBeenCalled();
			expect(stop).toHaveBeenCalled();
		});

		it('does nothing when AudioContext is unsupported', () => {
			vi.unstubAllGlobals();
			expect(() => playChime()).not.toThrow();
		});
	});
});
