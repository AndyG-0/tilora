import { writable } from 'svelte/store';
import { api, type ScreensaverSettings } from '$lib/api';

// null until loaded for the current user — +layout.svelte's idle timer
// treats a null value the same as "disabled" so nothing can arm before a
// real setting is known.
export const screensaverSettings = writable<ScreensaverSettings | null>(null);

// Lets Settings' "Test screensaver" button show the overlay immediately,
// bypassing armIdleTimer()'s enabled/route checks entirely — useful for
// previewing unsaved changes without waiting out the idle timeout.
export const forceScreensaverPreview = writable<boolean | ScreensaverSettings>(false);

export function loadScreensaverSettings() {
	return api
		.getScreensaverSettings()
		.then(screensaverSettings.set)
		.catch(() => {
			// keep whatever was last loaded (or null on first load)
		});
}

export function persistScreensaverSettings(partial: Partial<ScreensaverSettings>) {
	return api.updateScreensaverSettings(partial).then(screensaverSettings.set);
}
