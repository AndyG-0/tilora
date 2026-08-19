import { beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

const { assistantConfig, getPreferences, updatePreferences } = vi.hoisted(() => ({
	assistantConfig: vi.fn(),
	getPreferences: vi.fn(),
	updatePreferences: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { assistantConfig, getPreferences, updatePreferences } }));

beforeEach(() => {
	vi.resetModules();
	assistantConfig.mockReset();
	getPreferences.mockReset();
	updatePreferences.mockReset();
});

describe('assistant store', () => {
	it('starts with default agent name and alwaysOnMic false', async () => {
		const { agentName, alwaysOnMic } = await import('./assistant');

		expect(get(agentName)).toBe('Tilora');
		expect(get(alwaysOnMic)).toBe(false);
	});

	it('loadAssistantConfigFromServer sets agentName and STT availability', async () => {
		assistantConfig.mockResolvedValue({
			agent_name: 'Jarvis',
			stt_available: true,
			stt_provider: 'openai',
		});

		const { agentName, sttAvailable, sttProvider, loadAssistantConfigFromServer } = await import('./assistant');
		await loadAssistantConfigFromServer();

		expect(get(agentName)).toBe('Jarvis');
		expect(get(sttAvailable)).toBe(true);
		expect(get(sttProvider)).toBe('openai');
	});

	it('loadAssistantConfigFromServer leaves agentName unchanged when failing', async () => {
		assistantConfig.mockRejectedValue(new Error('network error'));

		const { agentName, loadAssistantConfigFromServer } = await import('./assistant');
		await loadAssistantConfigFromServer();

		expect(get(agentName)).toBe('Tilora');
	});

	it('loadAlwaysOnMicFromServer sets alwaysOnMic from preferences', async () => {
		getPreferences.mockResolvedValue({ always_on_mic: true });

		const { alwaysOnMic, loadAlwaysOnMicFromServer } = await import('./assistant');
		await loadAlwaysOnMicFromServer();

		expect(get(alwaysOnMic)).toBe(true);
	});

	it('loadAlwaysOnMicFromServer handles network failure gracefully', async () => {
		getPreferences.mockRejectedValue(new Error('network error'));

		const { alwaysOnMic, loadAlwaysOnMicFromServer } = await import('./assistant');
		await loadAlwaysOnMicFromServer();

		expect(get(alwaysOnMic)).toBe(false);
	});

	it('persistAlwaysOnMic updates preferences and sets alwaysOnMic', async () => {
		updatePreferences.mockResolvedValue({ always_on_mic: true });

		const { alwaysOnMic, persistAlwaysOnMic } = await import('./assistant');
		await persistAlwaysOnMic(true);

		expect(updatePreferences).toHaveBeenCalledWith({ always_on_mic: true });
		expect(get(alwaysOnMic)).toBe(true);
	});
});
