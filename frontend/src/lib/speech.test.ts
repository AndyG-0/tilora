import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { synthesizeSpeech } = vi.hoisted(() => ({ synthesizeSpeech: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { synthesizeSpeech } }));

import {
	isSpeechRecognitionSupported,
	isSpeechSynthesisSupported,
	listBrowserVoices,
	listenOnce,
	playChime,
	speak,
} from './speech';

describe('speech', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		synthesizeSpeech.mockReset();
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

	describe('listBrowserVoices', () => {
		it('resolves immediately when voices are already populated', async () => {
			const voices = [{ name: 'Voice 1' } as SpeechSynthesisVoice];
			vi.stubGlobal('speechSynthesis', { getVoices: () => voices });

			await expect(listBrowserVoices()).resolves.toBe(voices);
		});

		it('waits for the voiceschanged event when nothing is populated yet', async () => {
			const voices = [{ name: 'Voice 1' } as SpeechSynthesisVoice];
			let callCount = 0;
			const synth = {
				getVoices: () => (callCount++ === 0 ? [] : voices),
				onvoiceschanged: null as (() => void) | null,
			};
			vi.stubGlobal('speechSynthesis', synth);

			const promise = listBrowserVoices();
			synth.onvoiceschanged?.();

			await expect(promise).resolves.toBe(voices);
		});

		it('falls back to an empty list after a timeout if voiceschanged never fires', async () => {
			vi.useFakeTimers();
			vi.stubGlobal('speechSynthesis', { getVoices: () => [], onvoiceschanged: null });

			const promise = listBrowserVoices();
			await vi.advanceTimersByTimeAsync(1000);

			await expect(promise).resolves.toEqual([]);
			vi.useRealTimers();
		});

		it('resolves with an empty list when speech synthesis is unsupported', async () => {
			await expect(listBrowserVoices()).resolves.toEqual([]);
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

		it('matches a voice selection by voiceURI', () => {
			const cancel = vi.fn();
			const speakFn = vi.fn();
			const matchingVoice = { voiceURI: 'v1', name: 'Voice 1' } as SpeechSynthesisVoice;
			const otherVoice = { voiceURI: 'v2', name: 'Voice 2' } as SpeechSynthesisVoice;
			vi.stubGlobal('speechSynthesis', {
				cancel,
				speak: speakFn,
				getVoices: () => [otherVoice, matchingVoice],
			});

			speak('hello', { provider: 'browser', voiceId: 'v1', voiceName: 'Voice 1' });

			expect(speakFn.mock.calls[0][0].voice).toBe(matchingVoice);
		});

		it('falls back to matching a voice selection by name when the voiceURI is stale', () => {
			const cancel = vi.fn();
			const speakFn = vi.fn();
			const matchingVoice = { voiceURI: 'new-uri', name: 'Voice 1' } as SpeechSynthesisVoice;
			vi.stubGlobal('speechSynthesis', {
				cancel,
				speak: speakFn,
				getVoices: () => [matchingVoice],
			});

			speak('hello', { provider: 'browser', voiceId: 'stale-uri', voiceName: 'Voice 1' });

			expect(speakFn.mock.calls[0][0].voice).toBe(matchingVoice);
		});

		it('plays audio from the remote provider for a non-browser selection', async () => {
			const blob = new Blob(['audio-bytes']);
			synthesizeSpeech.mockResolvedValue(blob);
			const play = vi.fn().mockResolvedValue(undefined);
			class FakeAudio {
				play = play;
				addEventListener = vi.fn();
			}
			vi.stubGlobal('Audio', FakeAudio);
			vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:fake'), revokeObjectURL: vi.fn() });

			await speak('hello', { provider: 'openai', voiceId: 'nova', voiceName: '' });

			expect(synthesizeSpeech).toHaveBeenCalledWith('openai', 'nova', 'hello');
			expect(play).toHaveBeenCalled();
		});

		it('falls back to the browser voice when the remote provider fails', async () => {
			synthesizeSpeech.mockRejectedValue(new Error('server unreachable'));
			const cancel = vi.fn();
			const speakFn = vi.fn();
			vi.stubGlobal('speechSynthesis', { cancel, speak: speakFn, getVoices: () => [] });

			await speak('hello', { provider: 'piper', voiceId: 'en_US-amy-medium', voiceName: '' });

			expect(speakFn).toHaveBeenCalledTimes(1);
			expect(speakFn.mock.calls[0][0].text).toBe('hello');
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
