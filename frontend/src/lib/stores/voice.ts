import { writable } from 'svelte/store';
import { api, type UserPreferences } from '$lib/api';

export type VoiceProvider = 'browser' | 'openai' | 'piper';

export interface VoiceSelection {
	provider: VoiceProvider;
	voiceId: string;
	// Browser-only fallback match key: a saved voiceId (SpeechSynthesisVoice.voiceURI)
	// may not exist on a different device or after a browser update, so
	// speech.ts also tries matching by name before falling back to the
	// device's own default voice.
	voiceName: string;
}

const DEFAULT_SELECTION: VoiceSelection = { provider: 'browser', voiceId: '', voiceName: '' };

export const voiceSelection = writable<VoiceSelection>(DEFAULT_SELECTION);

function fromPreferences(prefs: UserPreferences): VoiceSelection {
	return {
		provider: (prefs.voice_provider as VoiceProvider) || 'browser',
		voiceId: prefs.voice_id ?? '',
		voiceName: prefs.voice_name ?? '',
	};
}

export function loadVoiceSelectionFromServer() {
	return api
		.getPreferences()
		.then((prefs) => voiceSelection.set(fromPreferences(prefs)))
		.catch(() => {
			// keep whatever was last loaded (or the default on first load)
		});
}

export function persistVoiceSelection(selection: VoiceSelection) {
	return api
		.updatePreferences({
			voice_provider: selection.provider,
			voice_id: selection.voiceId,
			voice_name: selection.voiceName,
		})
		.then((prefs) => voiceSelection.set(fromPreferences(prefs)));
}
