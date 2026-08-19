// Feature-detected wrappers around the browser's native Speech APIs, plus an
// opt-in path to server-synthesized cloud/self-hosted (Piper) voices. The
// kiosk runs Chromium full-screen on a Pi touchscreen, and the built-in
// SpeechSynthesis voices there are backed by espeak-ng and sound robotic —
// so speak() also supports a specific admin-enabled cloud/Piper voice,
// fetched as audio bytes from the backend (see app/api/tts.py) and played
// back via the Audio element. Speech *recognition* (listenOnce and
// continuous wake-word detection) prefers the browser's native
// SpeechRecognition where it's reliable (isNativeSpeechReliable()), and
// falls back to cloud STT (OpenAI Whisper, see app/api/assistant.py) where
// it isn't — Chromium, Firefox, Brave.

import { api } from '$lib/api';

interface SpeechRecognitionResultLike {
	transcript: string;
}

interface SpeechRecognitionEventLike extends Event {
	resultIndex: number;
	results: {
		[index: number]: { [index: number]: SpeechRecognitionResultLike; isFinal?: boolean; length?: number };
		length: number;
	};
}

interface SpeechRecognitionErrorEventLike extends Event {
	error?: string;
	message?: string;
}

interface SpeechRecognitionLike extends EventTarget {
	lang: string;
	continuous: boolean;
	interimResults: boolean;
	maxAlternatives: number;
	start(): void;
	stop(): void;
	abort(): void;
	onresult: ((event: SpeechRecognitionEventLike) => void) | null;
	onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
	onend: (() => void) | null;
}

function getSpeechRecognitionCtor(): (new () => SpeechRecognitionLike) | undefined {
	const w = window as unknown as {
		SpeechRecognition?: new () => SpeechRecognitionLike;
		webkitSpeechRecognition?: new () => SpeechRecognitionLike;
	};
	return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

export function isSpeechRecognitionSupported(sttAvailable = false): boolean {
	if (typeof window === 'undefined') return false;
	if (getSpeechRecognitionCtor() !== undefined) return true;
	if (sttAvailable && typeof navigator !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia)) return true;
	return false;
}

export function isSpeechSynthesisSupported(): boolean {
	return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

export interface VoiceSelection {
	provider: 'browser' | 'openai' | 'piper';
	voiceId: string;
	voiceName: string;
}

import { logger } from '$lib/logger';

export interface WakeWordMatch {
	matched: boolean;
	query: string;
}

function escapeRegex(str: string): string {
	return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const TILORA_VARIANTS_PATTERN =
	'(?:tilora|tilorah|talora|talorah|tylora|tylorah|tealora|tealorah|tellora|tellorah|t-lora|tlora|tell\\s+laura|tell\\s+aura|tell\\s+ora|tell\\s+lora|to\\s+laura|to\\s+lora|the\\s+laura|t\\s+lora|tee\\s+lora|tea\\s+lora|t-flora|t\\s+flora|tflora|taylor|tyler|delora)';

function levenshteinDistance(a: string, b: string): number {
	if (a === b) return 0;
	if (!a.length) return b.length;
	if (!b.length) return a.length;

	const matrix: number[][] = [];
	for (let i = 0; i <= b.length; i++) matrix[i] = [i];
	for (let j = 0; j <= a.length; j++) matrix[0][j] = j;

	for (let i = 1; i <= b.length; i++) {
		for (let j = 1; j <= a.length; j++) {
			if (b.charAt(i - 1) === a.charAt(j - 1)) {
				matrix[i][j] = matrix[i - 1][j - 1];
			} else {
				matrix[i][j] = Math.min(matrix[i - 1][j - 1] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j] + 1);
			}
		}
	}
	return matrix[b.length][a.length];
}

export function matchWakeWord(transcript: string, agentName: string): WakeWordMatch {
	const trimmedTranscript = (transcript || '').trim();
	const trimmedAgentName = (agentName || 'Tilora').trim();
	if (!trimmedTranscript || !trimmedAgentName) return { matched: false, query: '' };

	const isTilora = trimmedAgentName.toLowerCase() === 'tilora';

	if (isTilora) {
		const tiloraRegex = new RegExp(
			`(?:^|.*?\\b)(?:(?:hey|hi|hello|ok|okay|yo|listen)\\s+)?${TILORA_VARIANTS_PATTERN}\\b[\\s,:;!?-]*(.*)$`,
			'i',
		);
		const match = trimmedTranscript.match(tiloraRegex);
		if (match) {
			return { matched: true, query: (match[1] || '').trim() };
		}

		// Also handle short forms with greeting: "hey flora", "hey tora", "hey laura"
		const shortRegex = /(?:^|.*?\b)(?:hey|hi|hello|ok|okay|yo|listen)\s+(?:flora|tora|laura|elora)\b[\s,:;!?-]*(.*)$/i;
		const shortMatch = trimmedTranscript.match(shortRegex);
		if (shortMatch) {
			return { matched: true, query: (shortMatch[1] || '').trim() };
		}
	} else {
		// Custom agent name exact regex (allowing leading fillers & greetings)
		const customRegex = new RegExp(
			`(?:^|.*?\\b)(?:(?:hey|hi|hello|ok|okay|yo|listen)\\s+)?\\b${escapeRegex(trimmedAgentName)}\\b[\\s,:;!?-]*(.*)$`,
			'i',
		);
		const match = trimmedTranscript.match(customRegex);
		if (match) {
			return { matched: true, query: (match[1] || '').trim() };
		}
	}

	// Fuzzy match fallback for custom names or phonetic variations
	const cleanTarget = trimmedAgentName.toLowerCase().replace(/[^a-z0-9]/g, '');
	const words = trimmedTranscript.split(/\s+/);
	for (let i = 0; i < words.length; i++) {
		const cleanCandidate = words[i].toLowerCase().replace(/[^a-z0-9]/g, '');
		if (!cleanCandidate) continue;

		const maxDist = cleanTarget.length <= 4 ? 1 : 2;
		const dist = levenshteinDistance(cleanCandidate, cleanTarget);
		if (dist <= maxDist) {
			const query = words
				.slice(i + 1)
				.join(' ')
				.replace(/^[\s,:;!?-]+/, '')
				.trim();
			return { matched: true, query };
		}
	}

	return { matched: false, query: '' };
}

// Chromium populates getVoices() asynchronously the first time (fires
// 'voiceschanged'); resolve immediately if already populated, otherwise wait
// once for that event, with a timeout fallback in case it never fires.
export function listBrowserVoices(): Promise<SpeechSynthesisVoice[]> {
	if (!isSpeechSynthesisSupported()) return Promise.resolve([]);
	const existing = window.speechSynthesis.getVoices();
	if (existing.length > 0) return Promise.resolve(existing);
	return new Promise((resolve) => {
		const timeout = setTimeout(() => resolve(window.speechSynthesis.getVoices()), 1000);
		window.speechSynthesis.onvoiceschanged = () => {
			clearTimeout(timeout);
			resolve(window.speechSynthesis.getVoices());
		};
	});
}

function pickBrowserVoice(selection?: VoiceSelection): SpeechSynthesisVoice | undefined {
	if (!selection || selection.provider !== 'browser' || !isSpeechSynthesisSupported()) return undefined;
	const voices = window.speechSynthesis.getVoices();
	// Graceful fallback: a voiceURI saved on one device may not exist on
	// another (or after a browser update) — fall back to matching by name,
	// then to no explicit voice at all (the browser's own per-language
	// default), rather than throwing or silently failing to speak.
	return voices.find((v) => v.voiceURI === selection.voiceId) ?? voices.find((v) => v.name === selection.voiceName);
}

let speaking = false;
let currentRemoteAudio: HTMLAudioElement | null = null;

export function isSpeaking(): boolean {
	return speaking;
}

export function stopSpeaking(): void {
	if (isSpeechSynthesisSupported()) {
		try {
			window.speechSynthesis.cancel();
		} catch {
			// ignore
		}
	}
	if (currentRemoteAudio) {
		try {
			currentRemoteAudio.pause();
		} catch {
			// ignore
		}
		currentRemoteAudio = null;
	}
	speaking = false;
}

function speakWithBrowserVoice(text: string, selection?: VoiceSelection): void {
	if (!isSpeechSynthesisSupported()) return;
	stopSpeaking();

	const utterance = new SpeechSynthesisUtterance(text);
	const voice = pickBrowserVoice(selection);
	if (voice) utterance.voice = voice;

	speaking = true;
	utterance.onend = () => {
		speaking = false;
	};
	utterance.onerror = () => {
		speaking = false;
	};

	window.speechSynthesis.speak(utterance);
}

async function speakWithRemoteVoice(text: string, provider: 'openai' | 'piper', voiceId: string): Promise<void> {
	stopSpeaking();
	const blob = await api.synthesizeSpeech(provider, voiceId, text);
	const url = URL.createObjectURL(blob);
	const audioEl = new Audio(url);
	currentRemoteAudio = audioEl;
	speaking = true;

	audioEl.addEventListener('ended', () => {
		speaking = false;
		if (currentRemoteAudio === audioEl) currentRemoteAudio = null;
		URL.revokeObjectURL(url);
	});
	audioEl.addEventListener('error', () => {
		speaking = false;
		if (currentRemoteAudio === audioEl) currentRemoteAudio = null;
		URL.revokeObjectURL(url);
	});

	try {
		await audioEl.play();
	} catch (err) {
		speaking = false;
		if (currentRemoteAudio === audioEl) currentRemoteAudio = null;
		URL.revokeObjectURL(url);
		throw err;
	}
}

// `selection` is optional so every existing call site (speak(text)) keeps
// working unchanged, defaulting to the plain browser-default-voice behavior
// this function has always had. A remote (cloud/Piper) failure — provider
// disabled since the picker last loaded, server unreachable, etc. — falls
// back to the browser voice rather than going silent.
export async function speak(text: string, selection?: VoiceSelection): Promise<void> {
	if (!text) return;
	if (!selection || selection.provider === 'browser') {
		speakWithBrowserVoice(text, selection);
		return;
	}
	try {
		await speakWithRemoteVoice(text, selection.provider, selection.voiceId);
	} catch {
		speakWithBrowserVoice(text);
	}
}

import { isNativeSpeechReliable } from '$lib/network';

export const STT_UNAVAILABLE_MESSAGE =
	'Speech recognition is unavailable in this browser. Enable OpenAI Whisper in Settings or use Google Chrome / Edge.';

export type SpeechErrorCode =
	'not-allowed' | 'audio-capture' | 'service-unavailable' | 'no-speech' | 'network' | 'unknown';

export class SpeechError extends Error {
	code: SpeechErrorCode;
	constructor(message: string, code: SpeechErrorCode = 'unknown') {
		super(message);
		this.name = 'SpeechError';
		this.code = code;
	}
}

export interface ListenOnceOptions {
	sttAvailable?: boolean;
	onListeningMode?: (mode: 'native' | 'cloud_stt') => void;
	onTranscribing?: () => void;
}

function getSupportedAudioMimeType(): string {
	if (typeof MediaRecorder === 'undefined') return '';
	const types = [
		'audio/webm;codecs=opus',
		'audio/webm',
		'audio/ogg;codecs=opus',
		'audio/ogg',
		'audio/mp4',
		'audio/wav',
	];
	for (const t of types) {
		if (typeof MediaRecorder.isTypeSupported === 'function' && MediaRecorder.isTypeSupported(t)) {
			return t;
		}
	}
	return '';
}

export function recordAudioClip(maxDurationMs = 8000): {
	promise: Promise<Blob>;
	stop: () => void;
} {
	if (
		typeof navigator === 'undefined' ||
		!navigator.mediaDevices?.getUserMedia ||
		typeof MediaRecorder === 'undefined'
	) {
		return {
			promise: Promise.reject(
				new SpeechError('Media recording is not supported on this device', 'service-unavailable'),
			),
			stop() {},
		};
	}

	let stopFn: () => void = () => {};

	const promise = new Promise<Blob>((resolve, reject) => {
		navigator.mediaDevices
			.getUserMedia({ audio: true })
			.then((stream) => {
				const mimeType = getSupportedAudioMimeType();
				let recorder: MediaRecorder;
				try {
					recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
				} catch {
					recorder = new MediaRecorder(stream);
				}

				const chunks: Blob[] = [];
				recorder.ondataavailable = (e) => {
					if (e.data && e.data.size > 0) {
						chunks.push(e.data);
					}
				};

				let cleanedUp = false;
				const cleanup = () => {
					if (cleanedUp) return;
					cleanedUp = true;
					try {
						stream.getTracks().forEach((t) => t.stop());
					} catch {
						// ignore
					}
				};

				recorder.onstop = () => {
					cleanup();
					const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
					resolve(blob);
				};

				recorder.onerror = () => {
					cleanup();
					reject(new SpeechError('Audio recording failed', 'audio-capture'));
				};

				recorder.start(250);

				const timer = setTimeout(() => {
					if (recorder.state === 'recording') {
						try {
							recorder.stop();
						} catch {
							cleanup();
						}
					}
				}, maxDurationMs);

				stopFn = () => {
					clearTimeout(timer);
					if (recorder.state === 'recording') {
						try {
							recorder.stop();
						} catch {
							cleanup();
						}
					}
				};
			})
			.catch((err: unknown) => {
				const errName = err instanceof Error ? err.name : '';
				if (errName === 'NotAllowedError' || errName === 'PermissionDeniedError') {
					reject(new SpeechError('Microphone permission denied', 'not-allowed'));
				} else if (errName === 'NotFoundError' || errName === 'DevicesNotFoundError') {
					reject(new SpeechError('No microphone detected', 'audio-capture'));
				} else {
					reject(new SpeechError('Microphone access failed', 'audio-capture'));
				}
			});
	});

	return {
		promise,
		stop: () => stopFn(),
	};
}

function listenNative(): Promise<string> {
	const Ctor = getSpeechRecognitionCtor();
	if (!Ctor) return Promise.reject(new SpeechError('Speech recognition is not supported', 'service-unavailable'));

	return new Promise((resolve, reject) => {
		const recognition = new Ctor();
		recognition.lang = 'en-US';
		recognition.interimResults = false;
		recognition.maxAlternatives = 1;

		let hasResult = false;

		recognition.onresult = (event) => {
			const transcript = event.results[0]?.[0]?.transcript ?? '';
			if (transcript.trim()) {
				hasResult = true;
				resolve(transcript.trim());
			}
		};

		recognition.onerror = (event) => {
			const errCode = event.error;
			if (errCode === 'not-allowed') {
				reject(new SpeechError('Microphone permission denied', 'not-allowed'));
			} else if (errCode === 'audio-capture') {
				reject(new SpeechError('No microphone detected', 'audio-capture'));
			} else if (errCode === 'service-not-allowed' || errCode === 'network') {
				reject(new SpeechError('Speech recognition service unavailable', 'service-unavailable'));
			} else if (errCode === 'no-speech') {
				reject(new SpeechError('No speech detected', 'no-speech'));
			} else {
				reject(new SpeechError(`Speech recognition error: ${errCode}`, 'unknown'));
			}
		};

		recognition.onend = () => {
			if (!hasResult) {
				reject(new SpeechError('No speech detected', 'no-speech'));
			}
		};

		try {
			recognition.start();
		} catch {
			reject(new SpeechError('Could not start speech recognition', 'service-unavailable'));
		}
	});
}

export async function listenOnce(options?: ListenOnceOptions): Promise<string> {
	const sttAvailable = options?.sttAvailable ?? false;
	const isReliable = isNativeSpeechReliable();

	// In Chrome, Edge, or Safari, try native SpeechRecognition first.
	if (isReliable && getSpeechRecognitionCtor() !== undefined) {
		options?.onListeningMode?.('native');
		try {
			return await listenNative();
		} catch (err) {
			if (err instanceof SpeechError) {
				if (err.code === 'not-allowed' || err.code === 'audio-capture' || err.code === 'no-speech') {
					throw err;
				}
			}
			if (!sttAvailable) {
				throw err;
			}
		}
	}

	// Cloud STT path (Chromium, Firefox, Brave, or native fallback)
	if (sttAvailable) {
		options?.onListeningMode?.('cloud_stt');
		const recorder = recordAudioClip();
		const audioBlob = await recorder.promise;
		if (!audioBlob || audioBlob.size === 0) {
			throw new SpeechError('No speech detected', 'no-speech');
		}
		options?.onTranscribing?.();
		try {
			const ext = audioBlob.type.includes('ogg') ? 'ogg' : audioBlob.type.includes('mp4') ? 'mp4' : 'webm';
			const res = await api.transcribeAudio(audioBlob, `speech.${ext}`);
			const text = (res.text || '').trim();
			if (!text) {
				throw new SpeechError('No speech detected', 'no-speech');
			}
			return text;
		} catch (err) {
			if (err instanceof SpeechError) throw err;
			const msg = err instanceof Error ? err.message : 'Transcription failed';
			throw new SpeechError(msg, 'service-unavailable');
		}
	}

	// If native is present but unreliable (Chromium/Firefox) and no STT configured:
	if (getSpeechRecognitionCtor() !== undefined) {
		options?.onListeningMode?.('native');
		try {
			return await listenNative();
		} catch (err) {
			if (err instanceof SpeechError && (err.code === 'service-unavailable' || err.code === 'network')) {
				throw new SpeechError(STT_UNAVAILABLE_MESSAGE, 'service-unavailable');
			}
			throw err;
		}
	}

	throw new SpeechError(STT_UNAVAILABLE_MESSAGE, 'service-unavailable');
}

export interface ContinuousListenOptions {
	getAgentName: () => string;
	onWakeWordDetected: (query: string) => void;
	onError?: (error: Error) => void;
	lang?: string;
	// Whether the server has cloud STT (OpenAI Whisper) configured. Mirrors
	// ListenOnceOptions.sttAvailable — without it, browsers where native
	// SpeechRecognition is unreliable (Chromium, Firefox, Brave; see
	// isNativeSpeechReliable()) have no way to detect the wake word at all.
	sttAvailable?: boolean;
}

export interface ContinuousListenHandle {
	stop: () => void;
	pause: () => void;
	resume: () => void;
}

export async function ensureMicrophonePermission(): Promise<boolean> {
	if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
		return true;
	}
	try {
		const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
		stream.getTracks().forEach((track) => track.stop());
		return true;
	} catch {
		return false;
	}
}

// Dispatches to native browser SpeechRecognition where it's reliable (Chrome,
// Edge, Safari — see isNativeSpeechReliable()), otherwise to a cloud-STT/VAD
// fallback (Chromium, Firefox, Brave) when the server has Whisper configured,
// mirroring listenOnce()'s existing dispatch logic for the single-shot flow.
export function startContinuousListening(options: ContinuousListenOptions): ContinuousListenHandle {
	const isReliable = isNativeSpeechReliable();
	const Ctor = getSpeechRecognitionCtor();

	if (isReliable && Ctor) {
		return startNativeContinuousListening(options, Ctor);
	}
	if (options.sttAvailable) {
		return startCloudVadContinuousListening(options);
	}
	options.onError?.(new Error(STT_UNAVAILABLE_MESSAGE));
	return { stop() {}, pause() {}, resume() {} };
}

function startNativeContinuousListening(
	options: ContinuousListenOptions,
	Ctor: new () => SpeechRecognitionLike,
): ContinuousListenHandle {
	const RecognitionCtor = Ctor;
	let active = true;
	let paused = false;
	let isRunning = false;
	let recognition: SpeechRecognitionLike | null = null;
	let restartTimeout: ReturnType<typeof setTimeout> | null = null;

	function clearRestart() {
		if (restartTimeout !== null) {
			clearTimeout(restartTimeout);
			restartTimeout = null;
		}
	}

	function startRecognition() {
		if (!active || paused || isRunning) return;
		clearRestart();

		try {
			recognition = new RecognitionCtor();
			recognition.continuous = true;
			recognition.interimResults = true;
			recognition.maxAlternatives = 5;
			recognition.lang = options.lang || (typeof navigator !== 'undefined' ? navigator.language : 'en-US') || 'en-US';

			recognition.onresult = (event: SpeechRecognitionEventLike) => {
				if (!active || paused || speaking) return;

				for (let i = event.resultIndex ?? 0; i < event.results.length; i++) {
					const res = event.results[i];
					if (!res) continue;
					const altCount = typeof res.length === 'number' ? res.length : res[0] ? 1 : 0;
					for (let a = 0; a < altCount; a++) {
						const transcript = res[a]?.transcript ?? '';
						if (!transcript) continue;
						logger.debug('Continuous recognition heard:', transcript);
						const match = matchWakeWord(transcript, options.getAgentName());
						if (match.matched) {
							logger.info('Wake word matched:', transcript, '-> query:', match.query);
							paused = true;
							try {
								recognition?.abort();
							} catch {
								// ignore
							}
							options.onWakeWordDetected(match.query);
							return;
						}
					}
				}
			};

			recognition.onerror = (event: SpeechRecognitionErrorEventLike) => {
				if (!active) return;
				logger.debug('Continuous recognition error:', event.error);
				if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
					options.onError?.(new Error(`Speech recognition error: ${event.error}`));
				}
			};

			recognition.onend = () => {
				isRunning = false;
				if (active && !paused) {
					clearRestart();
					restartTimeout = setTimeout(() => {
						if (active && !paused) {
							startRecognition();
						}
					}, 150);
				}
			};

			recognition.start();
			isRunning = true;
		} catch {
			isRunning = false;
			if (active && !paused) {
				clearRestart();
				restartTimeout = setTimeout(() => {
					if (active && !paused) {
						startRecognition();
					}
				}, 500);
			}
		}
	}

	startRecognition();

	return {
		stop() {
			active = false;
			paused = false;
			clearRestart();
			if (recognition && isRunning) {
				try {
					recognition.stop();
				} catch {
					// ignore
				}
			}
			recognition = null;
		},
		pause() {
			paused = true;
			clearRestart();
			if (recognition && isRunning) {
				try {
					recognition.stop();
				} catch {
					// ignore
				}
			}
		},
		resume() {
			if (!active) return;
			paused = false;
			startRecognition();
		},
	};
}

// --- Cloud-STT continuous listening (VAD-gated) ---------------------------
//
// Used where native SpeechRecognition is unreliable (Chromium, Firefox,
// Brave) but the server has cloud STT (Whisper) configured. Keeps a single
// getUserMedia stream open for the whole session and runs a cheap local
// amplitude-based voice-activity check on it, only sending audio to Whisper
// when an actual utterance was detected — never on a fixed timer — since
// transcription is billed per minute and this runs continuously in the
// background on a kiosk.

const VAD_TICK_MS = 100;
const VAD_CALIBRATION_MS = 600;
const VAD_MIN_UTTERANCE_MS = 350;
const VAD_SILENCE_HANGOVER_MS = 900;
const VAD_MAX_UTTERANCE_MS = 6000;
const VAD_DEFAULT_THRESHOLD = 0.02;
const VAD_THRESHOLD_MULTIPLIER = 2.5;
const VAD_MAX_CONSECUTIVE_FAILURES = 3;

export type VadPhase = 'idle' | 'recording';

export interface VadRunningState {
	phase: VadPhase;
	elapsedRecordingMs: number;
	speechMs: number;
	silenceMs: number;
}

export const INITIAL_VAD_STATE: VadRunningState = { phase: 'idle', elapsedRecordingMs: 0, speechMs: 0, silenceMs: 0 };

export interface VadConfig {
	tickMs: number;
	threshold: number;
	minUtteranceMs: number;
	silenceHangoverMs: number;
	maxUtteranceMs: number;
}

export type VadAction = 'none' | 'start' | 'stop-transcribe' | 'stop-discard';

// Pure amplitude RMS over a time-domain byte buffer (as returned by
// AnalyserNode.getByteTimeDomainData) — no DOM/WebAudio dependency, so this
// and stepVad() below are unit-testable without mocking the Web Audio API.
export function computeRms(data: Uint8Array): number {
	let sum = 0;
	for (let i = 0; i < data.length; i++) {
		const n = (data[i] - 128) / 128;
		sum += n * n;
	}
	return Math.sqrt(sum / data.length);
}

// One VAD tick: idle -> recording once rms crosses threshold; recording ->
// idle (transcribe) once trailing silence exceeds silenceHangoverMs, as long
// as the accumulated in-utterance speech time cleared minUtteranceMs -
// otherwise idle (discard), so short blips/taps never reach Whisper.
export function stepVad(
	state: VadRunningState,
	rms: number,
	cfg: VadConfig,
): { state: VadRunningState; action: VadAction } {
	const isSpeech = rms >= cfg.threshold;

	if (state.phase === 'idle') {
		if (!isSpeech) return { state, action: 'none' };
		return {
			state: { phase: 'recording', elapsedRecordingMs: cfg.tickMs, speechMs: cfg.tickMs, silenceMs: 0 },
			action: 'start',
		};
	}

	const elapsedRecordingMs = state.elapsedRecordingMs + cfg.tickMs;
	const speechMs = isSpeech ? state.speechMs + cfg.tickMs : state.speechMs;
	const silenceMs = isSpeech ? 0 : state.silenceMs + cfg.tickMs;
	const shouldStop = elapsedRecordingMs >= cfg.maxUtteranceMs || silenceMs >= cfg.silenceHangoverMs;

	if (shouldStop) {
		return { state: INITIAL_VAD_STATE, action: speechMs >= cfg.minUtteranceMs ? 'stop-transcribe' : 'stop-discard' };
	}

	return { state: { phase: 'recording', elapsedRecordingMs, speechMs, silenceMs }, action: 'none' };
}

function startCloudVadContinuousListening(options: ContinuousListenOptions): ContinuousListenHandle {
	let active = true;
	let paused = false;
	let stream: MediaStream | null = null;
	let audioContext: AudioContext | null = null;
	let analyser: AnalyserNode | null = null;
	let dataArray: Uint8Array<ArrayBuffer> | null = null;
	let tickInterval: ReturnType<typeof setInterval> | null = null;
	let vadState: VadRunningState = INITIAL_VAD_STATE;
	let threshold = VAD_DEFAULT_THRESHOLD;
	let recorder: MediaRecorder | null = null;
	let recorderChunks: Blob[] = [];
	let transcribing = false;
	let consecutiveFailures = 0;

	function discardRecording() {
		if (recorder && recorder.state === 'recording') {
			try {
				recorder.stop();
			} catch {
				// ignore
			}
		}
		recorder = null;
		recorderChunks = [];
	}

	function teardown() {
		if (tickInterval !== null) {
			clearInterval(tickInterval);
			tickInterval = null;
		}
		discardRecording();
		if (stream) {
			try {
				stream.getTracks().forEach((t) => t.stop());
			} catch {
				// ignore
			}
			stream = null;
		}
		if (audioContext) {
			try {
				void audioContext.close();
			} catch {
				// ignore
			}
			audioContext = null;
		}
		analyser = null;
		dataArray = null;
		vadState = INITIAL_VAD_STATE;
	}

	function startRecording() {
		if (!stream) return;
		recorderChunks = [];
		const mimeType = getSupportedAudioMimeType();
		try {
			recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
		} catch {
			recorder = new MediaRecorder(stream);
		}
		recorder.ondataavailable = (e) => {
			if (e.data && e.data.size > 0) recorderChunks.push(e.data);
		};
		recorder.start(250);
	}

	async function handleUtterance(blob: Blob) {
		try {
			if (blob.size === 0) return;
			const ext = blob.type.includes('ogg') ? 'ogg' : blob.type.includes('mp4') ? 'mp4' : 'webm';
			const res = await api.transcribeAudio(blob, `wake.${ext}`);
			consecutiveFailures = 0;
			const text = (res.text || '').trim();
			if (!text) return;
			logger.debug('Continuous cloud STT heard:', text);
			const match = matchWakeWord(text, options.getAgentName());
			if (match.matched) {
				logger.info('Wake word matched:', text, '-> query:', match.query);
				paused = true;
				options.onWakeWordDetected(match.query);
			}
		} catch (err) {
			consecutiveFailures += 1;
			logger.debug('Continuous cloud STT transcription failed:', err);
			if (consecutiveFailures >= VAD_MAX_CONSECUTIVE_FAILURES) {
				active = false;
				teardown();
				options.onError?.(new Error(STT_UNAVAILABLE_MESSAGE));
			}
		} finally {
			transcribing = false;
		}
	}

	function stopRecordingAndTranscribe() {
		if (!recorder || recorder.state !== 'recording') return;
		const activeRecorder = recorder;
		const chunksRef = recorderChunks;
		transcribing = true;
		activeRecorder.onstop = () => {
			const blob = new Blob(chunksRef, { type: activeRecorder.mimeType || 'audio/webm' });
			void handleUtterance(blob);
		};
		try {
			activeRecorder.stop();
		} catch {
			transcribing = false;
		}
		recorder = null;
		recorderChunks = [];
	}

	function tick() {
		// A fresh AudioContext stays 'suspended' until the page has received a
		// user gesture (same Chromium policy that blocks TTS autoplay — see
		// the dashboard's audio-unlock banner); until then this just no-ops
		// rather than erroring, and starts working the moment that tap happens.
		if (!active || paused || speaking || transcribing || !analyser || !dataArray) return;
		if (audioContext && audioContext.state !== 'running') return;

		analyser.getByteTimeDomainData(dataArray);
		const rms = computeRms(dataArray);
		const { state, action } = stepVad(vadState, rms, {
			tickMs: VAD_TICK_MS,
			threshold,
			minUtteranceMs: VAD_MIN_UTTERANCE_MS,
			silenceHangoverMs: VAD_SILENCE_HANGOVER_MS,
			maxUtteranceMs: VAD_MAX_UTTERANCE_MS,
		});
		vadState = state;

		if (action === 'start') {
			startRecording();
		} else if (action === 'stop-transcribe') {
			stopRecordingAndTranscribe();
		} else if (action === 'stop-discard') {
			discardRecording();
		}
	}

	async function calibrate() {
		if (!analyser || !dataArray) return;
		const sampleCount = Math.max(1, Math.round(VAD_CALIBRATION_MS / VAD_TICK_MS));
		const samples: number[] = [];
		for (let i = 0; i < sampleCount; i++) {
			if (!active) return;
			analyser.getByteTimeDomainData(dataArray);
			samples.push(computeRms(dataArray));
			await new Promise((resolve) => setTimeout(resolve, VAD_TICK_MS));
		}
		const avg = samples.reduce((a, b) => a + b, 0) / samples.length;
		threshold = Math.max(VAD_DEFAULT_THRESHOLD, avg * VAD_THRESHOLD_MULTIPLIER);
	}

	async function init() {
		try {
			stream = await navigator.mediaDevices.getUserMedia({
				audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
			});
		} catch {
			options.onError?.(new Error('Microphone access failed'));
			return;
		}
		if (!active) {
			stream.getTracks().forEach((t) => t.stop());
			stream = null;
			return;
		}

		const Ctor = (window as unknown as { AudioContext?: typeof AudioContext }).AudioContext;
		if (!Ctor) {
			options.onError?.(new Error(STT_UNAVAILABLE_MESSAGE));
			return;
		}
		audioContext = new Ctor();
		void audioContext.resume().catch(() => {
			// Stays suspended until the page's first user gesture (see tick()) - not an error.
		});
		const source = audioContext.createMediaStreamSource(stream);
		analyser = audioContext.createAnalyser();
		source.connect(analyser);
		dataArray = new Uint8Array(analyser.fftSize);

		await calibrate();
		if (!active) {
			teardown();
			return;
		}

		tickInterval = setInterval(tick, VAD_TICK_MS);
	}

	void init();

	return {
		stop() {
			active = false;
			paused = false;
			teardown();
		},
		pause() {
			paused = true;
			discardRecording();
			vadState = INITIAL_VAD_STATE;
		},
		resume() {
			if (!active) return;
			paused = false;
		},
	};
}

export function playChime(): void {
	const Ctor = (window as unknown as { AudioContext?: typeof AudioContext }).AudioContext;
	if (!Ctor) return;

	const context = new Ctor();
	const oscillator = context.createOscillator();
	const gain = context.createGain();
	oscillator.type = 'sine';
	oscillator.frequency.value = 880;
	gain.gain.setValueAtTime(0.15, context.currentTime);
	gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.4);
	oscillator.connect(gain);
	gain.connect(context.destination);
	oscillator.start();
	oscillator.stop(context.currentTime + 0.4);
	oscillator.onended = () => context.close();
}
