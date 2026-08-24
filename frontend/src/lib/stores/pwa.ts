import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export interface PWAState {
	canInstall: boolean;
	isStandalone: boolean;
	updateAvailable: boolean;
	isOnline: boolean;
}

const initialState: PWAState = {
	canInstall: false,
	isStandalone: false,
	updateAvailable: false,
	isOnline: typeof navigator !== 'undefined' ? (navigator.onLine ?? true) : true,
};

export const pwaState = writable<PWAState>(initialState);

// Reference to the browser's BeforeInstallPromptEvent
interface BeforeInstallPromptEvent extends Event {
	readonly platforms: string[];
	readonly userChoice: Promise<{
		outcome: 'accepted' | 'dismissed';
		platform: string;
	}>;
	prompt(): Promise<void>;
}

let deferredInstallPrompt: BeforeInstallPromptEvent | null = null;
let activeRegistration: ServiceWorkerRegistration | null = null;

export async function promptInstall(): Promise<boolean> {
	if (!deferredInstallPrompt) return false;

	try {
		await deferredInstallPrompt.prompt();
		const { outcome } = await deferredInstallPrompt.userChoice;
		deferredInstallPrompt = null;
		pwaState.update((s) => ({ ...s, canInstall: false }));
		return outcome === 'accepted';
	} catch {
		deferredInstallPrompt = null;
		pwaState.update((s) => ({ ...s, canInstall: false }));
		return false;
	}
}

export function applyUpdate(): void {
	if (activeRegistration?.waiting) {
		activeRegistration.waiting.postMessage({ type: 'SKIP_WAITING' });
	} else if (browser && 'serviceWorker' in navigator) {
		navigator.serviceWorker.getRegistration().then((reg) => {
			if (reg?.waiting) {
				reg.waiting.postMessage({ type: 'SKIP_WAITING' });
			} else {
				window.location.reload();
			}
		});
	} else if (browser) {
		window.location.reload();
	}
}

export function dismissUpdate(): void {
	pwaState.update((s) => ({ ...s, updateAvailable: false }));
}

export function initPwa(): () => void {
	if (!browser) return () => {};

	const isStandalone =
		(typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)').matches) ||
		(navigator as unknown as { standalone?: boolean })?.standalone === true;

	pwaState.update((s) => ({
		...s,
		isStandalone,
		isOnline: navigator.onLine ?? true,
	}));

	const handleOnline = () => {
		pwaState.update((s) => ({ ...s, isOnline: true }));
	};

	const handleOffline = () => {
		pwaState.update((s) => ({ ...s, isOnline: false }));
	};

	const handleBeforeInstallPrompt = (e: Event) => {
		e.preventDefault();
		deferredInstallPrompt = e as BeforeInstallPromptEvent;
		pwaState.update((s) => ({ ...s, canInstall: true }));
	};

	const handleAppInstalled = () => {
		deferredInstallPrompt = null;
		pwaState.update((s) => ({ ...s, canInstall: false, isStandalone: true }));
	};

	window.addEventListener('online', handleOnline);
	window.addEventListener('offline', handleOffline);
	window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
	window.addEventListener('appinstalled', handleAppInstalled);

	// Register Service Worker in secure contexts or localhost
	const isSecure =
		window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

	let refreshing = false;
	const handleControllerChange = () => {
		if (!refreshing) {
			refreshing = true;
			window.location.reload();
		}
	};

	if ('serviceWorker' in navigator && isSecure) {
		navigator.serviceWorker.addEventListener('controllerchange', handleControllerChange);

		navigator.serviceWorker
			.register('/service-worker.js', { scope: '/' })
			.then((registration) => {
				activeRegistration = registration;

				if (registration.waiting) {
					pwaState.update((s) => ({ ...s, updateAvailable: true }));
				}

				registration.addEventListener('updatefound', () => {
					const newWorker = registration.installing;
					if (!newWorker) return;

					newWorker.addEventListener('statechange', () => {
						if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
							pwaState.update((s) => ({ ...s, updateAvailable: true }));
						}
					});
				});
			})
			.catch(() => {
				// Silently fallback if service worker cannot be registered
			});
	}

	return () => {
		window.removeEventListener('online', handleOnline);
		window.removeEventListener('offline', handleOffline);
		window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
		window.removeEventListener('appinstalled', handleAppInstalled);
		if ('serviceWorker' in navigator) {
			navigator.serviceWorker.removeEventListener('controllerchange', handleControllerChange);
		}
	};
}
