// Feature-detected wrappers around the browser's native Speech APIs, plus an
// opt-in path to server-synthesized cloud/self-hosted (Piper) voices. The
// kiosk runs Chromium full-screen on a Pi touchscreen, and the built-in
// SpeechSynthesis voices there are backed by espeak-ng and sound robotic —
// so speak() also supports a specific admin-enabled cloud/Piper voice,
// fetched as audio bytes from the backend (see app/api/tts.py) and played
// back via the Audio element. Speech *recognition* (listenOnce and
// continuous wake-word detection) has no server-side equivalent and stays
// purely local either way.

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
				throw new SpeechError(
					'Speech recognition is unavailable in this browser. Enable OpenAI Whisper in Settings or use Google Chrome / Edge.',
					'service-unavailable',
				);
			}
			throw err;
		}
	}

	throw new SpeechError(
		'Speech recognition is unavailable in this browser. Enable OpenAI Whisper in Settings or use Google Chrome / Edge.',
		'service-unavailable',
	);
}

export interface ContinuousListenOptions {
	getAgentName: () => string;
	onWakeWordDetected: (query: string) => void;
	onError?: (error: Error) => void;
	lang?: string;
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

export function startContinuousListening(options: ContinuousListenOptions): ContinuousListenHandle {
	const Ctor = getSpeechRecognitionCtor();
	if (!Ctor) {
		options.onError?.(new Error('Speech recognition is not supported'));
		return { stop() {}, pause() {}, resume() {} };
	}

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
