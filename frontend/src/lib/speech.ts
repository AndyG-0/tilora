// Feature-detected wrappers around the browser's native Speech APIs, plus an
// opt-in path to server-synthesized cloud/self-hosted (Piper) voices. The
// kiosk runs Chromium full-screen on a Pi touchscreen, and the built-in
// SpeechSynthesis voices there are backed by espeak-ng and sound robotic —
// so speak() also supports a specific admin-enabled cloud/Piper voice,
// fetched as audio bytes from the backend (see app/api/tts.py) and played
// back via the Audio element. Speech *recognition* (listenOnce) has no
// server-side equivalent and stays purely local either way.

import { api } from '$lib/api';

interface SpeechRecognitionResultLike {
	transcript: string;
}

interface SpeechRecognitionEventLike extends Event {
	results: { [index: number]: { [index: number]: SpeechRecognitionResultLike }; length: number };
}

interface SpeechRecognitionLike extends EventTarget {
	lang: string;
	interimResults: boolean;
	maxAlternatives: number;
	start(): void;
	stop(): void;
	onresult: ((event: SpeechRecognitionEventLike) => void) | null;
	onerror: ((event: Event) => void) | null;
	onend: (() => void) | null;
}

function getSpeechRecognitionCtor(): (new () => SpeechRecognitionLike) | undefined {
	const w = window as unknown as {
		SpeechRecognition?: new () => SpeechRecognitionLike;
		webkitSpeechRecognition?: new () => SpeechRecognitionLike;
	};
	return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

export function isSpeechRecognitionSupported(): boolean {
	return typeof window !== 'undefined' && getSpeechRecognitionCtor() !== undefined;
}

export function isSpeechSynthesisSupported(): boolean {
	return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

export interface VoiceSelection {
	provider: 'browser' | 'openai' | 'piper';
	voiceId: string;
	voiceName: string;
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

function speakWithBrowserVoice(text: string, selection?: VoiceSelection): void {
	if (!isSpeechSynthesisSupported()) return;
	window.speechSynthesis.cancel();
	const utterance = new SpeechSynthesisUtterance(text);
	const voice = pickBrowserVoice(selection);
	if (voice) utterance.voice = voice;
	window.speechSynthesis.speak(utterance);
}

let currentRemoteAudio: HTMLAudioElement | null = null;

async function speakWithRemoteVoice(text: string, provider: 'openai' | 'piper', voiceId: string): Promise<void> {
	currentRemoteAudio?.pause();
	const blob = await api.synthesizeSpeech(provider, voiceId, text);
	const url = URL.createObjectURL(blob);
	const audioEl = new Audio(url);
	currentRemoteAudio = audioEl;
	audioEl.addEventListener('ended', () => URL.revokeObjectURL(url));
	audioEl.addEventListener('error', () => URL.revokeObjectURL(url));
	await audioEl.play();
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

export function listenOnce(): Promise<string> {
	const Ctor = getSpeechRecognitionCtor();
	if (!Ctor) return Promise.reject(new Error('Speech recognition is not supported'));

	return new Promise((resolve, reject) => {
		const recognition = new Ctor();
		recognition.lang = 'en-US';
		recognition.interimResults = false;
		recognition.maxAlternatives = 1;

		recognition.onresult = (event) => {
			const transcript = event.results[0]?.[0]?.transcript ?? '';
			resolve(transcript);
		};
		recognition.onerror = () => reject(new Error('Speech recognition failed'));
		recognition.onend = () => reject(new Error('No speech detected'));

		recognition.start();
	});
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
