import { writable } from 'svelte/store';
import { api, type LocationPreference, type UserPreferences } from '$lib/api';

export const userLocation = writable<LocationPreference | null>(null);

function fromPreferences(prefs: UserPreferences): LocationPreference | null {
	return prefs.location ?? null;
}

export function loadLocationFromServer() {
	return api
		.getPreferences()
		.then((prefs) => userLocation.set(fromPreferences(prefs)))
		.catch(() => {
			// keep whatever was last loaded (or null on first load)
		});
}

export function persistLocation(location: LocationPreference | null) {
	return api.updatePreferences({ location }).then((prefs) => userLocation.set(fromPreferences(prefs)));
}
