import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { synthesizeSpeech, transcribeAudio } = vi.hoisted(() => ({
	synthesizeSpeech: vi.fn(),
	transcribeAudio: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { synthesizeSpeech, transcribeAudio } }));

import {
	computeRms,
	ensureMicrophonePermission,
	INITIAL_VAD_STATE,
	isSpeaking,
	isSpeechRecognitionSupported,
	isSpeechSynthesisSupported,
	listBrowserVoices,
	listenOnce,
	matchWakeWord,
	playChime,
	SpeechError,
	speak,
	startContinuousListening,
	stepVad,
	stopSpeaking,
	type VadConfig,
} from './speech';

const CHROME_UA =
	'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

describe('speech', () => {
	beforeEach(() => {
		stopSpeaking();
	});

	afterEach(() => {
		stopSpeaking();
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
			await expect(listenOnce()).rejects.toThrow(SpeechError);
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

		it('rejects when recognition errors out with not-allowed', async () => {
			class FakeRecognition {
				lang = '';
				interimResults = true;
				maxAlternatives = 1;
				onresult: (() => void) | null = null;
				onerror: ((event: unknown) => void) | null = null;
				onend: (() => void) | null = null;
				start() {
					this.onerror?.({ error: 'not-allowed' });
				}
			}
			// @ts-expect-error -- minimal stub, not a full SpeechRecognition impl
			window.SpeechRecognition = FakeRecognition;

			await expect(listenOnce()).rejects.toMatchObject({ code: 'not-allowed' });
		});

		it('transcribes via Cloud STT when sttAvailable is true and MediaRecorder is present', async () => {
			const fakeTrack = { stop: vi.fn() };
			const fakeStream = { getTracks: () => [fakeTrack] };
			const mockGetUserMedia = vi.fn().mockResolvedValue(fakeStream);
			vi.stubGlobal('navigator', {
				mediaDevices: { getUserMedia: mockGetUserMedia },
			});

			class FakeMediaRecorder {
				state = 'inactive';
				mimeType = 'audio/webm';
				ondataavailable: ((event: { data: Blob }) => void) | null = null;
				onstop: (() => void) | null = null;
				onerror: (() => void) | null = null;
				static isTypeSupported() {
					return true;
				}
				start() {
					this.state = 'recording';
					setTimeout(() => {
						this.ondataavailable?.({ data: new Blob(['audio-data-chunk-here-1234567890'], { type: 'audio/webm' }) });
						this.state = 'inactive';
						this.onstop?.();
					}, 10);
				}
				stop() {
					this.state = 'inactive';
					this.onstop?.();
				}
			}
			vi.stubGlobal('MediaRecorder', FakeMediaRecorder);

			transcribeAudio.mockResolvedValue({ text: 'transcribed from whisper' });

			const onListeningMode = vi.fn();
			const onTranscribing = vi.fn();

			const result = await listenOnce({
				sttAvailable: true,
				onListeningMode,
				onTranscribing,
			});

			expect(result).toBe('transcribed from whisper');
			expect(onListeningMode).toHaveBeenCalledWith('cloud_stt');
			expect(onTranscribing).toHaveBeenCalled();
			expect(transcribeAudio).toHaveBeenCalled();
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

	describe('matchWakeWord', () => {
		it('returns matched: true with empty query when wake word is spoken alone', () => {
			expect(matchWakeWord('Tilora', 'Tilora')).toEqual({ matched: true, query: '' });
			expect(matchWakeWord('tilora', 'Tilora')).toEqual({ matched: true, query: '' });
			expect(matchWakeWord('Hey Tilora', 'Tilora')).toEqual({ matched: true, query: '' });
			expect(matchWakeWord('ok tilora', 'Tilora')).toEqual({ matched: true, query: '' });
			expect(matchWakeWord('Hello Tilora!', 'Tilora')).toEqual({ matched: true, query: '' });
		});

		it('returns matched: true and extracts command query', () => {
			expect(matchWakeWord('Tilora what is the weather', 'Tilora')).toEqual({
				matched: true,
				query: 'what is the weather',
			});
			expect(matchWakeWord('Hey Tilora, turn on the lights!', 'Tilora')).toEqual({
				matched: true,
				query: 'turn on the lights!',
			});
			expect(matchWakeWord('Friday, play some music', 'Friday')).toEqual({
				matched: true,
				query: 'play some music',
			});
		});

		it('matches phonetic variants of Tilora that Web Speech engines generate', () => {
			expect(matchWakeWord('Tell Laura what is the weather', 'Tilora')).toEqual({
				matched: true,
				query: 'what is the weather',
			});
			expect(matchWakeWord('To Laura what time is it', 'Tilora')).toEqual({
				matched: true,
				query: 'what time is it',
			});
			expect(matchWakeWord('Hey Taylor how are you', 'Tilora')).toEqual({
				matched: true,
				query: 'how are you',
			});
			expect(matchWakeWord('OK T-Lora turn off the lights', 'Tilora')).toEqual({
				matched: true,
				query: 'turn off the lights',
			});
			expect(matchWakeWord('Hey Flora what is new', 'Tilora')).toEqual({
				matched: true,
				query: 'what is new',
			});
			expect(matchWakeWord('Um hey Tilora what is on the schedule', 'Tilora')).toEqual({
				matched: true,
				query: 'what is on the schedule',
			});
		});

		it('supports fuzzy matching for custom agent names', () => {
			expect(matchWakeWord('Hey Jarviss turn on the lamp', 'Jarvis')).toEqual({
				matched: true,
				query: 'turn on the lamp',
			});
		});

		it('returns matched: false when wake word is not present', () => {
			expect(matchWakeWord('what is the weather', 'Tilora')).toEqual({ matched: false, query: '' });
			expect(matchWakeWord('good morning everyone', 'Tilora')).toEqual({ matched: false, query: '' });
			expect(matchWakeWord('', 'Tilora')).toEqual({ matched: false, query: '' });
		});
	});

	describe('ensureMicrophonePermission', () => {
		it('calls getUserMedia and releases tracks', async () => {
			const stopTrack = vi.fn();
			const getUserMedia = vi.fn().mockResolvedValue({
				getTracks: () => [{ stop: stopTrack }],
			});
			vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } });

			const granted = await ensureMicrophonePermission();
			expect(granted).toBe(true);
			expect(getUserMedia).toHaveBeenCalledWith({ audio: true });
			expect(stopTrack).toHaveBeenCalled();
		});
	});

	describe('speaking state and stopSpeaking', () => {
		it('tracks speaking state and resets on stopSpeaking', () => {
			expect(isSpeaking()).toBe(false);
			const cancel = vi.fn();
			vi.stubGlobal('speechSynthesis', { cancel, speak: vi.fn(), getVoices: () => [] });
			stopSpeaking();
			expect(cancel).toHaveBeenCalled();
			expect(isSpeaking()).toBe(false);
		});
	});

	describe('startContinuousListening', () => {
		it('calls onError when speech recognition is unsupported', () => {
			const onError = vi.fn();
			const onWakeWordDetected = vi.fn();
			const handle = startContinuousListening({
				getAgentName: () => 'Tilora',
				onWakeWordDetected,
				onError,
			});

			expect(onError).toHaveBeenCalledWith(expect.any(Error));
			expect(typeof handle.stop).toBe('function');
		});

		it('detects wake word in continuous stream and calls onWakeWordDetected', () => {
			const onWakeWordDetected = vi.fn();
			let capturedResultHandler: ((event: unknown) => void) | undefined;
			let started = false;
			let stopped = false;

			class FakeContinuousRecognition {
				continuous = false;
				interimResults = false;
				maxAlternatives = 1;
				lang = '';
				set onresult(fn: ((event: unknown) => void) | null) {
					capturedResultHandler = fn ?? undefined;
				}
				onerror: (() => void) | null = null;
				onend: (() => void) | null = null;
				start() {
					started = true;
				}
				stop() {
					stopped = true;
				}
				abort() {
					stopped = true;
				}
			}
			// @ts-expect-error -- test stub
			window.SpeechRecognition = FakeContinuousRecognition;
			vi.stubGlobal('navigator', { userAgent: CHROME_UA, language: 'en-US' });

			const handle = startContinuousListening({
				getAgentName: () => 'Tilora',
				onWakeWordDetected,
			});

			expect(started).toBe(true);

			// Simulate speech event with wake word
			if (capturedResultHandler) {
				capturedResultHandler({
					resultIndex: 0,
					results: [{ 0: { transcript: 'Hey Tilora what time is it' } }],
				});
			}

			expect(onWakeWordDetected).toHaveBeenCalledWith('what time is it');

			handle.stop();
			expect(stopped).toBe(true);
		});
	});

	describe('computeRms', () => {
		it('is 0 for silence (all bytes at the 128 midpoint)', () => {
			expect(computeRms(new Uint8Array(32).fill(128))).toBe(0);
		});

		it('is ~1 for a full-scale square wave', () => {
			const data = new Uint8Array(32).fill(255);
			expect(computeRms(data)).toBeCloseTo(0.992, 2);
		});

		it('scales with amplitude', () => {
			const quiet = new Uint8Array(32).fill(128 + 13); // ~0.1 amplitude
			const loud = new Uint8Array(32).fill(128 + 64); // ~0.5 amplitude
			expect(computeRms(loud)).toBeGreaterThan(computeRms(quiet));
		});
	});

	describe('stepVad', () => {
		const cfg: VadConfig = {
			tickMs: 100,
			threshold: 0.1,
			minUtteranceMs: 350,
			silenceHangoverMs: 900,
			maxUtteranceMs: 6000,
		};

		it('stays idle while rms is below threshold', () => {
			const { state, action } = stepVad(INITIAL_VAD_STATE, 0.01, cfg);
			expect(action).toBe('none');
			expect(state).toBe(INITIAL_VAD_STATE);
		});

		it('starts recording once rms crosses threshold', () => {
			const { state, action } = stepVad(INITIAL_VAD_STATE, 0.5, cfg);
			expect(action).toBe('start');
			expect(state).toEqual({ phase: 'recording', elapsedRecordingMs: 100, speechMs: 100, silenceMs: 0 });
		});

		it('discards a short blip that never reaches the minimum utterance length', () => {
			let state = stepVad(INITIAL_VAD_STATE, 0.5, cfg).state; // 100ms speech
			const step = stepVad(state, 0.0, cfg); // silence starts immediately
			state = step.state;
			// advance silence to the hangover threshold
			let action = step.action;
			for (let i = 0; i < 8; i++) {
				const r = stepVad(state, 0.0, cfg);
				state = r.state;
				action = r.action;
			}
			expect(action).toBe('stop-discard');
			expect(state).toBe(INITIAL_VAD_STATE);
		});

		it('transcribes an utterance that clears the minimum speech duration before trailing silence', () => {
			let state = INITIAL_VAD_STATE;
			let action = 'none' as ReturnType<typeof stepVad>['action'];
			for (let i = 0; i < 4; i++) {
				({ state, action } = stepVad(state, 0.5, cfg));
			}
			expect(state.speechMs).toBe(400);
			for (let i = 0; i < 9; i++) {
				({ state, action } = stepVad(state, 0.0, cfg));
			}
			expect(action).toBe('stop-transcribe');
			expect(state).toBe(INITIAL_VAD_STATE);
		});

		it('force-stops at the max utterance duration even without trailing silence', () => {
			let state = INITIAL_VAD_STATE;
			let action = 'none' as ReturnType<typeof stepVad>['action'];
			for (let i = 0; i < 60; i++) {
				({ state, action } = stepVad(state, 0.5, cfg));
			}
			expect(action).toBe('stop-transcribe');
		});
	});

	describe('startContinuousListening (cloud VAD path)', () => {
		function makeFakeMediaRecorderClass() {
			class FakeMediaRecorder {
				static instances: FakeMediaRecorder[] = [];
				state = 'inactive';
				mimeType = 'audio/webm';
				ondataavailable: ((e: { data: Blob }) => void) | null = null;
				onstop: (() => void) | null = null;
				onerror: (() => void) | null = null;
				static isTypeSupported() {
					return true;
				}
				constructor() {
					FakeMediaRecorder.instances.push(this);
				}
				start() {
					this.state = 'recording';
					this.ondataavailable?.({ data: new Blob(['chunk'], { type: 'audio/webm' }) });
				}
				stop() {
					this.state = 'inactive';
					this.onstop?.();
				}
			}
			return FakeMediaRecorder;
		}

		function stubCloudVadEnvironment(initialRms = 0) {
			const audioState = { rms: initialRms };

			class FakeAnalyserNode {
				fftSize = 32;
				getByteTimeDomainData(arr: Uint8Array) {
					const val = Math.min(255, Math.max(0, Math.round(128 + audioState.rms * 128)));
					arr.fill(val);
				}
			}
			const analyser = new FakeAnalyserNode();

			class FakeAudioContext {
				state = 'running';
				currentTime = 0;
				destination = {};
				createMediaStreamSource() {
					return { connect: vi.fn() };
				}
				createAnalyser() {
					return analyser;
				}
				resume() {
					this.state = 'running';
					return Promise.resolve();
				}
				close() {
					return Promise.resolve();
				}
			}
			vi.stubGlobal('AudioContext', FakeAudioContext);

			const fakeTrack = { stop: vi.fn() };
			const fakeStream = { getTracks: () => [fakeTrack] };
			const getUserMedia = vi.fn().mockResolvedValue(fakeStream);
			// No userAgent override here: jsdom's default UA is not chrome/edge/safari,
			// so isNativeSpeechReliable() is false and (with no SpeechRecognition ctor
			// stubbed) startContinuousListening dispatches to the cloud VAD path.
			vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } });

			const FakeMediaRecorder = makeFakeMediaRecorderClass();
			vi.stubGlobal('MediaRecorder', FakeMediaRecorder);

			return { audioState, getUserMedia, FakeMediaRecorder };
		}

		beforeEach(() => {
			vi.useFakeTimers();
			transcribeAudio.mockReset();
		});

		afterEach(() => {
			vi.useRealTimers();
		});

		it('records an utterance, transcribes it once, and fires onWakeWordDetected on a match', async () => {
			const { audioState, FakeMediaRecorder } = stubCloudVadEnvironment(0);
			transcribeAudio.mockResolvedValue({ text: 'Hey Tilora what time is it' });
			const onWakeWordDetected = vi.fn();

			const handle = startContinuousListening({
				getAgentName: () => 'Tilora',
				sttAvailable: true,
				onWakeWordDetected,
			});

			// ~600ms silent calibration window
			await vi.advanceTimersByTimeAsync(650);

			// speech crosses the calibrated threshold and clears the 350ms minimum
			audioState.rms = 0.5;
			await vi.advanceTimersByTimeAsync(400);

			// trailing silence past the 900ms hangover triggers stop + transcribe
			audioState.rms = 0;
			await vi.advanceTimersByTimeAsync(1200);

			expect(FakeMediaRecorder.instances).toHaveLength(1);
			expect(transcribeAudio).toHaveBeenCalledTimes(1);
			expect(onWakeWordDetected).toHaveBeenCalledWith('what time is it');

			handle.stop();
		});

		it('never starts recording (and never transcribes) while the assistant is speaking', async () => {
			class FakeUtterance {
				text: string;
				voice: SpeechSynthesisVoice | undefined;
				constructor(text: string) {
					this.text = text;
				}
			}
			vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance);
			vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), speak: vi.fn(), getVoices: () => [] });
			speak('assistant is talking', { provider: 'browser', voiceId: '', voiceName: '' });

			const { audioState, FakeMediaRecorder } = stubCloudVadEnvironment(0);

			const handle = startContinuousListening({
				getAgentName: () => 'Tilora',
				sttAvailable: true,
				onWakeWordDetected: vi.fn(),
			});

			await vi.advanceTimersByTimeAsync(650);
			audioState.rms = 0.5;
			await vi.advanceTimersByTimeAsync(1500);

			expect(FakeMediaRecorder.instances).toHaveLength(0);
			expect(transcribeAudio).not.toHaveBeenCalled();

			handle.stop();
			stopSpeaking();
		});

		it('pause() discards an in-flight recording, and resume() re-arms without recalibrating', async () => {
			const { audioState } = stubCloudVadEnvironment(0);

			const handle = startContinuousListening({
				getAgentName: () => 'Tilora',
				sttAvailable: true,
				onWakeWordDetected: vi.fn(),
			});

			await vi.advanceTimersByTimeAsync(650);
			audioState.rms = 0.5;
			await vi.advanceTimersByTimeAsync(200);

			handle.pause();
			audioState.rms = 0;
			await vi.advanceTimersByTimeAsync(1500);
			expect(transcribeAudio).not.toHaveBeenCalled();

			handle.resume();
			audioState.rms = 0.5;
			await vi.advanceTimersByTimeAsync(400);
			audioState.rms = 0;
			await vi.advanceTimersByTimeAsync(1200);

			expect(transcribeAudio).toHaveBeenCalledTimes(1);

			handle.stop();
		});

		it('routes Firefox/Chromium user agents with sttAvailable to the cloud path instead of onError', async () => {
			stubCloudVadEnvironment(0);
			const onError = vi.fn();

			const handle = startContinuousListening({
				getAgentName: () => 'Tilora',
				sttAvailable: true,
				onWakeWordDetected: vi.fn(),
				onError,
			});

			await vi.advanceTimersByTimeAsync(650);

			expect(onError).not.toHaveBeenCalled();
			handle.stop();
		});
	});
});
