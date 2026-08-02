// Thin, feature-detected wrappers around the browser's native Speech APIs.
// The kiosk runs Chromium full-screen on a Pi touchscreen, so this avoids
// pulling in any native/server-side audio stack — everything here is a
// no-op (or throws) in browsers that don't support it.

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

export function speak(text: string): void {
	if (!isSpeechSynthesisSupported() || !text) return;
	window.speechSynthesis.cancel();
	window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
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
