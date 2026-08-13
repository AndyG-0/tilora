import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { locale, waitLocale } from 'svelte-i18n';

const {
	goto,
	settings,
	updateSettings,
	version,
	widgetTypes,
	listDevices,
	listUsers,
	listHouseholdUsers,
	getPreferences,
	updatePreferences,
	listWidgets,
	ttsVoices,
	listBrowserVoices,
	speak,
	listNetworkIntegrations,
} = vi.hoisted(() => ({
	goto: vi.fn(),
	settings: vi.fn(),
	updateSettings: vi.fn(),
	version: vi.fn(),
	widgetTypes: vi.fn(),
	listDevices: vi.fn(),
	listUsers: vi.fn(),
	listHouseholdUsers: vi.fn(),
	getPreferences: vi.fn(),
	updatePreferences: vi.fn(),
	listWidgets: vi.fn().mockResolvedValue([]),
	ttsVoices: vi.fn(),
	listBrowserVoices: vi.fn(),
	speak: vi.fn(),
	listNetworkIntegrations: vi.fn().mockResolvedValue([]),
}));

vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({
	api: {
		settings,
		updateSettings,
		version,
		widgetTypes,
		listDevices,
		listUsers,
		listHouseholdUsers,
		getPreferences,
		updatePreferences,
		listWidgets,
		ttsVoices,
		listNetworkIntegrations,
	},
}));
vi.mock('$lib/speech', () => ({ listBrowserVoices, speak }));

import Page from './+page.svelte';
import { user } from '$lib/stores/user';
import { widgets } from '$lib/stores/widgets';
import { screensaverSettings, forceScreensaverPreview } from '$lib/stores/screensaver';

const BASE_SETTINGS = {
	ai_model: 'anthropic/claude-sonnet-5',
	ai_reasoning_effort: 'medium',
	timezone: 'UTC',
	has_anthropic_api_key: false,
	has_openai_api_key: false,
	has_gemini_api_key: false,
	openai_tts_enabled: '',
	openai_tts_model: 'gpt-4o-mini-tts',
	piper_tts_enabled: '',
	piper_server_url: '',
	piper_voices: '',
	has_google_calendar_client_id: false,
	has_google_calendar_client_secret: false,
	has_microsoft_calendar_client_id: false,
	has_microsoft_calendar_client_secret: false,
	caldav_url: '',
	caldav_username: '',
	has_caldav_password: false,
	icloud_username: '',
	has_icloud_password: false,
};

const DEFAULT_PREFERENCES = { theme: 'dark', voice_provider: 'browser', voice_id: '', voice_name: '' };

describe('settings +page.svelte — voice sections', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		user.set(null);
		settings.mockResolvedValue({ ...BASE_SETTINGS });
		updateSettings.mockResolvedValue({ ...BASE_SETTINGS });
		version.mockResolvedValue({
			current_version: '0.1.0',
			latest_version: null,
			update_available: false,
			release_url: null,
		});
		widgetTypes.mockResolvedValue([]);
		listDevices.mockResolvedValue([]);
		listUsers.mockResolvedValue([]);
		listHouseholdUsers.mockResolvedValue([]);
		getPreferences.mockResolvedValue({ ...DEFAULT_PREFERENCES });
		updatePreferences.mockResolvedValue({ ...DEFAULT_PREFERENCES });
		listWidgets.mockResolvedValue([]);
		ttsVoices.mockResolvedValue([]);
		listBrowserVoices.mockResolvedValue([]);
		listNetworkIntegrations.mockResolvedValue([]);
	});

	it('lets an admin enable OpenAI and Piper TTS and saves the provider fields', async () => {
		user.set({ id: 'admin1', name: 'Admin', avatar: null, role: 'admin' });
		render(Page);

		await screen.findByText('Voice output');

		await fireEvent.click(screen.getByLabelText('Enable OpenAI text-to-speech'));
		await fireEvent.click(screen.getByLabelText('Enable Piper (self-hosted) text-to-speech'));

		expect(screen.getByPlaceholderText('gpt-4o-mini-tts')).toBeInTheDocument();
		await fireEvent.input(screen.getByPlaceholderText('http://piper.local:5000'), {
			target: { value: 'http://piper.local:5000' },
		});
		await fireEvent.input(screen.getByPlaceholderText('en_US-lessac-medium|Lessac,en_US-amy-medium'), {
			target: { value: 'en_US-amy-medium|Amy' },
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Save app settings' }));

		await waitFor(() => expect(updateSettings).toHaveBeenCalled());
		expect(updateSettings).toHaveBeenCalledWith(
			expect.objectContaining({
				openai_tts_enabled: 'true',
				openai_tts_model: 'gpt-4o-mini-tts',
				piper_tts_enabled: 'true',
				piper_server_url: 'http://piper.local:5000',
				piper_voices: 'en_US-amy-medium|Amy',
			}),
		);
	});

	it('does not show the Voice output section to a non-admin member', async () => {
		user.set({ id: 'u1', name: 'Member', avatar: null, role: 'member' });
		render(Page);

		await waitFor(() => expect(getPreferences).toHaveBeenCalled());

		expect(screen.queryByText('Voice output')).not.toBeInTheDocument();
	});

	it('only offers voice sources the admin has enabled', async () => {
		user.set({ id: 'u1', name: 'Member', avatar: null, role: 'member' });
		ttsVoices.mockResolvedValue([{ id: 'nova', label: 'Nova', provider: 'openai' }]);
		render(Page);

		const source = await screen.findByLabelText('Voice source');
		await waitFor(() => expect(ttsVoices).toHaveBeenCalled());

		const optionLabels = Array.from((source as HTMLSelectElement).options).map((o) => o.textContent);
		expect(optionLabels).toEqual(["This device's built-in voices", 'OpenAI (cloud)']);
		expect(optionLabels).not.toContain('Piper (self-hosted)');
	});

	it('previews and saves the selected voice', async () => {
		user.set({ id: 'u1', name: 'Member', avatar: null, role: 'member' });
		listBrowserVoices.mockResolvedValue([{ voiceURI: 'v1', name: 'Voice 1', lang: 'en-US' } as SpeechSynthesisVoice]);
		updatePreferences.mockResolvedValue({
			...DEFAULT_PREFERENCES,
			voice_provider: 'browser',
			voice_id: 'v1',
			voice_name: 'Voice 1',
		});
		render(Page);

		await waitFor(() => expect(listBrowserVoices).toHaveBeenCalled());
		const voiceSelect = await screen.findByLabelText('Voice');
		await fireEvent.change(voiceSelect, { target: { value: 'v1' } });

		await fireEvent.click(screen.getByRole('button', { name: 'Preview voice' }));
		expect(speak).toHaveBeenCalledWith('This is a preview of the selected voice.', {
			provider: 'browser',
			voiceId: 'v1',
			voiceName: 'Voice 1',
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Save voice' }));

		await waitFor(() => expect(updatePreferences).toHaveBeenCalled());
		expect(updatePreferences).toHaveBeenCalledWith({
			voice_provider: 'browser',
			voice_id: 'v1',
			voice_name: 'Voice 1',
		});
		expect(await screen.findByText('Saved.')).toBeInTheDocument();
	});

	it('shows an error if saving the voice selection fails', async () => {
		user.set({ id: 'u1', name: 'Member', avatar: null, role: 'member' });
		listBrowserVoices.mockResolvedValue([{ voiceURI: 'v1', name: 'Voice 1', lang: 'en-US' } as SpeechSynthesisVoice]);
		updatePreferences.mockRejectedValue(new Error('network error'));
		render(Page);

		await screen.findByLabelText('Voice');
		await fireEvent.click(screen.getByRole('button', { name: 'Save voice' }));

		expect(await screen.findByText('Could not save your voice selection.')).toBeInTheDocument();
	});
});

describe('settings +page.svelte — language section', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		user.set(null);
		settings.mockResolvedValue({ ...BASE_SETTINGS });
		updateSettings.mockResolvedValue({ ...BASE_SETTINGS });
		version.mockResolvedValue({
			current_version: '0.1.0',
			latest_version: null,
			update_available: false,
			release_url: null,
		});
		widgetTypes.mockResolvedValue([]);
		listDevices.mockResolvedValue([]);
		listUsers.mockResolvedValue([]);
		listHouseholdUsers.mockResolvedValue([]);
		getPreferences.mockResolvedValue({ ...DEFAULT_PREFERENCES });
		updatePreferences.mockResolvedValue({ ...DEFAULT_PREFERENCES });
		listWidgets.mockResolvedValue([]);
		ttsVoices.mockResolvedValue([]);
		listBrowserVoices.mockResolvedValue([]);
		listNetworkIntegrations.mockResolvedValue([]);
	});

	it('persists a locale change and translates the page', async () => {
		user.set({ id: 'u1', name: 'Member', avatar: null, role: 'member' });
		render(Page);

		const select = await screen.findByLabelText('Language');
		await fireEvent.change(select, { target: { value: 'es' } });

		await waitFor(() => expect(updatePreferences).toHaveBeenCalledWith({ locale: 'es' }));
		expect(await screen.findByText('Idioma')).toBeInTheDocument();

		locale.set('en');
		await waitLocale();
	});
});

describe('settings +page.svelte — screensaver test button', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		user.set({ id: 'admin1', name: 'Admin', avatar: null, role: 'admin' });
		settings.mockResolvedValue({ ...BASE_SETTINGS });
		updateSettings.mockResolvedValue({ ...BASE_SETTINGS });
		version.mockResolvedValue({
			current_version: '0.1.0',
			latest_version: null,
			update_available: false,
			release_url: null,
		});
		widgetTypes.mockResolvedValue([]);
		listDevices.mockResolvedValue([]);
		listUsers.mockResolvedValue([]);
		listHouseholdUsers.mockResolvedValue([]);
		getPreferences.mockResolvedValue({ ...DEFAULT_PREFERENCES });
		updatePreferences.mockResolvedValue({ ...DEFAULT_PREFERENCES });
		listWidgets.mockResolvedValue([]);
		ttsVoices.mockResolvedValue([]);
		listBrowserVoices.mockResolvedValue([]);
		listNetworkIntegrations.mockResolvedValue([]);
		screensaverSettings.set(null);
		forceScreensaverPreview.set(false);
	});

	it('disables the test button when there are no screensaver-eligible widgets', async () => {
		widgets.set([]);
		render(Page);

		const button = await screen.findByRole('button', { name: 'Test screensaver' });
		expect(button).toBeDisabled();
	});

	it('flips forceScreensaverPreview when clicked with an eligible widget present', async () => {
		widgets.set([{ id: 'w1', type: 'rss', layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 }, tab: 'default' }]);
		render(Page);

		const button = await screen.findByRole('button', { name: 'Test screensaver' });
		expect(button).not.toBeDisabled();

		await fireEvent.click(button);

		expect(get(forceScreensaverPreview)).toBe(true);
	});
});
