import { beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

const { getPreferences, updatePreferences } = vi.hoisted(() => ({
	getPreferences: vi.fn(),
	updatePreferences: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { getPreferences, updatePreferences } }));

beforeEach(() => {
	vi.resetModules();
	getPreferences.mockReset();
	updatePreferences.mockReset();
});

const DEFAULTS = { theme: 'dark', voice_provider: 'browser', voice_id: '', voice_name: '' };

describe('voice store', () => {
	it('starts with the browser default before anything is loaded', async () => {
		const { voiceSelection } = await import('./voice');

		expect(get(voiceSelection)).toEqual({ provider: 'browser', voiceId: '', voiceName: '' });
	});

	it('loadVoiceSelectionFromServer populates the store from preferences', async () => {
		getPreferences.mockResolvedValue({ ...DEFAULTS, voice_provider: 'openai', voice_id: 'nova', voice_name: '' });

		const { voiceSelection, loadVoiceSelectionFromServer } = await import('./voice');
		await loadVoiceSelectionFromServer();

		expect(get(voiceSelection)).toEqual({ provider: 'openai', voiceId: 'nova', voiceName: '' });
	});

	it('loadVoiceSelectionFromServer leaves the store untouched when the request fails', async () => {
		getPreferences.mockRejectedValue(new Error('network error'));

		const { voiceSelection, loadVoiceSelectionFromServer } = await import('./voice');
		await loadVoiceSelectionFromServer();

		expect(get(voiceSelection)).toEqual({ provider: 'browser', voiceId: '', voiceName: '' });
	});

	it('persistVoiceSelection sends the selection and stores the merged response', async () => {
		updatePreferences.mockResolvedValue({
			...DEFAULTS,
			voice_provider: 'piper',
			voice_id: 'en_US-amy-medium',
			voice_name: '',
		});

		const { voiceSelection, persistVoiceSelection } = await import('./voice');
		await persistVoiceSelection({ provider: 'piper', voiceId: 'en_US-amy-medium', voiceName: '' });

		expect(updatePreferences).toHaveBeenCalledWith({
			voice_provider: 'piper',
			voice_id: 'en_US-amy-medium',
			voice_name: '',
		});
		expect(get(voiceSelection)).toEqual({ provider: 'piper', voiceId: 'en_US-amy-medium', voiceName: '' });
	});

	it('persistVoiceSelection rejects when the request fails', async () => {
		updatePreferences.mockRejectedValue(new Error('network error'));

		const { persistVoiceSelection } = await import('./voice');

		await expect(persistVoiceSelection({ provider: 'browser', voiceId: 'v1', voiceName: 'Voice 1' })).rejects.toThrow(
			'network error',
		);
	});
});
