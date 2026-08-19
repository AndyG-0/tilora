import { writable } from 'svelte/store';
import { api, type UserPreferences } from '$lib/api';

export const DEFAULT_AGENT_NAME = 'Tilora';

export const agentName = writable<string>(DEFAULT_AGENT_NAME);
export const alwaysOnMic = writable<boolean>(false);
export const sttAvailable = writable<boolean>(false);
export const sttProvider = writable<string | null>(null);

export function loadAssistantConfigFromServer() {
	return api
		.assistantConfig()
		.then((config) => {
			if (config?.agent_name) {
				agentName.set(config.agent_name.trim() || DEFAULT_AGENT_NAME);
			}
			sttAvailable.set(Boolean(config?.stt_available));
			sttProvider.set(config?.stt_provider ?? null);
		})
		.catch(() => {
			// keep whatever was last loaded (or default)
		});
}

export function loadAlwaysOnMicFromServer() {
	return api
		.getPreferences()
		.then((prefs: UserPreferences) => {
			alwaysOnMic.set(Boolean(prefs.always_on_mic));
		})
		.catch(() => {
			// keep whatever was last loaded
		});
}

export function persistAlwaysOnMic(enabled: boolean) {
	return api
		.updatePreferences({
			always_on_mic: enabled,
		})
		.then((prefs: UserPreferences) => {
			alwaysOnMic.set(Boolean(prefs.always_on_mic));
		});
}
