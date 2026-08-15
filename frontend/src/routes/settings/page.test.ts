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
	renameDevice,
	deleteDevice,
	listUsers,
	listHouseholdUsers,
	getPreferences,
	updatePreferences,
	listWidgets,
	ttsVoices,
	listBrowserVoices,
	speak,
	listNetworkIntegrations,
	getInsecureOriginInfo,
} = vi.hoisted(() => ({
	goto: vi.fn(),
	settings: vi.fn(),
	updateSettings: vi.fn(),
	version: vi.fn(),
	widgetTypes: vi.fn(),
	listDevices: vi.fn(),
	renameDevice: vi.fn(),
	deleteDevice: vi.fn(),
	listUsers: vi.fn(),
	listHouseholdUsers: vi.fn(),
	getPreferences: vi.fn(),
	updatePreferences: vi.fn(),
	listWidgets: vi.fn().mockResolvedValue([]),
	ttsVoices: vi.fn(),
	listBrowserVoices: vi.fn(),
	speak: vi.fn(),
	listNetworkIntegrations: vi.fn().mockResolvedValue([]),
	getInsecureOriginInfo: vi.fn().mockReturnValue(null),
}));

vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/network', () => ({ getInsecureOriginInfo }));
vi.mock('$lib/api', () => ({
	api: {
		settings,
		updateSettings,
		version,
		widgetTypes,
		listDevices,
		renameDevice,
		deleteDevice,
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
import { device } from '$lib/stores/device';
import { widgets } from '$lib/stores/widgets';
import { screensaverSettings, forceScreensaverPreview } from '$lib/stores/screensaver';

const BASE_SETTINGS = {
	ai_model: 'anthropic/claude-sonnet-5',
	ai_reasoning_effort: 'medium',
	ai_agent_name: 'Tilora',
	searxng_url: '',
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

		await fireEvent.click(screen.getByRole('button', { name: 'Save voice output' }));

		await waitFor(() => expect(updateSettings).toHaveBeenCalled());
		expect(updateSettings).toHaveBeenCalledWith({
			openai_tts_enabled: 'true',
			openai_tts_model: 'gpt-4o-mini-tts',
			piper_tts_enabled: 'true',
			piper_server_url: 'http://piper.local:5000',
			piper_voices: 'en_US-amy-medium|Amy',
		});
	});

	it('lets an admin update AI provider settings including agent name and SearXNG URL', async () => {
		user.set({ id: 'admin1', name: 'Admin', avatar: null, role: 'admin' });
		render(Page);

		await screen.findByText('AI provider');

		await fireEvent.input(screen.getByPlaceholderText('Tilora'), {
			target: { value: 'Jarvis' },
		});
		await fireEvent.input(screen.getByPlaceholderText('http://searxng:8080'), {
			target: { value: 'http://searxng.internal:8080' },
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Save AI provider' }));

		await waitFor(() => expect(updateSettings).toHaveBeenCalled());
		expect(updateSettings).toHaveBeenCalledWith({
			ai_model: 'anthropic/claude-sonnet-5',
			ai_reasoning_effort: 'medium',
			ai_agent_name: 'Jarvis',
			searxng_url: 'http://searxng.internal:8080',
		});
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

		expect(await screen.findByText('Idioma')).toBeInTheDocument();

		// The locale (and this button's own label) switches live as soon as the
		// select changes — the network write is what waits for Save.
		await fireEvent.click(screen.getByRole('button', { name: 'Guardar idioma' }));
		await waitFor(() => expect(updatePreferences).toHaveBeenCalledWith({ locale: 'es' }));

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
		widgets.set([
			{ id: 'w1', type: 'rss', name: 'RSS', layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 }, tab: 'default' },
		]);
		render(Page);

		const button = await screen.findByRole('button', { name: 'Test screensaver' });
		expect(button).not.toBeDisabled();

		await fireEvent.click(button);

		expect(get(forceScreensaverPreview)).toBe(true);
	});

	it('renders each eligible widget’s backend-provided name directly in the picker, unmodified', async () => {
		widgets.set([
			{
				id: 'weather-b',
				type: 'weather',
				name: 'Weather (Chicago, IL) (2)',
				layout: { col: 1, row: 1, colSpan: 1, rowSpan: 1 },
				tab: 'default',
			},
		]);
		render(Page);

		await fireEvent.click(await screen.findByLabelText('Enable on this device'));

		expect(await screen.findByLabelText('Weather (Chicago, IL) (2)')).toBeInTheDocument();
	});
});

describe('settings +page.svelte — microphone guidance on insecure origins', () => {
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
	});

	it('shows Chrome-specific flag instructions when on HTTP private IP in Chrome', async () => {
		getInsecureOriginInfo.mockReturnValue({
			needsInsecureOriginFlag: true,
			browser: 'chrome',
			isChrome: true,
			isChromium: true,
			origin: 'http://192.168.1.50:8080',
		});

		render(Page);

		expect(await screen.findByText('Microphone access')).toBeInTheDocument();
		expect(screen.getByText(/Chrome blocks microphone access on insecure origins/)).toBeInTheDocument();
		expect(
			screen.getByRole('link', { name: 'chrome://flags/#unsafely-treat-insecure-origin-as-secure' }),
		).toHaveAttribute('href', 'chrome://flags/#unsafely-treat-insecure-origin-as-secure');
	});

	it('shows Edge-specific flag instructions when on HTTP private IP in Edge', async () => {
		getInsecureOriginInfo.mockReturnValue({
			needsInsecureOriginFlag: true,
			browser: 'edge',
			isChrome: false,
			isChromium: true,
			origin: 'http://192.168.1.50:8080',
		});

		render(Page);

		expect(await screen.findByText('Microphone access')).toBeInTheDocument();
		expect(screen.getByText(/Microsoft Edge blocks microphone access on insecure origins/)).toBeInTheDocument();
		expect(
			screen.getByRole('link', { name: 'edge://flags/#unsafely-treat-insecure-origin-as-secure' }),
		).toHaveAttribute('href', 'edge://flags/#unsafely-treat-insecure-origin-as-secure');
	});

	it('shows Brave-specific flag instructions when on HTTP private IP in Brave', async () => {
		getInsecureOriginInfo.mockReturnValue({
			needsInsecureOriginFlag: true,
			browser: 'brave',
			isChrome: false,
			isChromium: true,
			origin: 'http://192.168.1.50:8080',
		});

		render(Page);

		expect(await screen.findByText('Microphone access')).toBeInTheDocument();
		expect(screen.getByText(/Brave blocks microphone access on insecure origins/)).toBeInTheDocument();
		expect(
			screen.getByRole('link', { name: 'brave://flags/#unsafely-treat-insecure-origin-as-secure' }),
		).toHaveAttribute('href', 'brave://flags/#unsafely-treat-insecure-origin-as-secure');
	});

	it('shows Safari-specific HTTPS and cert trust instructions when on HTTP private IP in Safari', async () => {
		getInsecureOriginInfo.mockReturnValue({
			needsInsecureOriginFlag: true,
			browser: 'safari',
			isChrome: false,
			isChromium: false,
			origin: 'http://192.168.1.50:8080',
		});

		render(Page);

		expect(await screen.findByText('Microphone access')).toBeInTheDocument();
		expect(
			screen.getByText(
				/Safari strictly blocks microphone access on insecure origins and does not provide browser flags/,
			),
		).toBeInTheDocument();
		expect(
			screen.getByText('To use the voice assistant in Safari, connect to Tilora over HTTPS (or localhost).'),
		).toBeInTheDocument();
		expect(screen.getByText('Using a self-signed or private SSL certificate?')).toBeInTheDocument();
		expect(screen.getByText(/Certificate Trust Settings/)).toBeInTheDocument();
		expect(screen.getByText(/In Keychain Access/)).toBeInTheDocument();
	});

	it('shows general HTTPS requirement for other browsers on HTTP private IP', async () => {
		getInsecureOriginInfo.mockReturnValue({
			needsInsecureOriginFlag: true,
			browser: 'firefox',
			isChrome: false,
			isChromium: false,
			origin: 'http://192.168.1.50:8080',
		});

		render(Page);

		expect(await screen.findByText('Microphone access')).toBeInTheDocument();
		expect(screen.getByText(/Most browsers block microphone access on insecure connections/)).toBeInTheDocument();
		expect(
			screen.getByText(/To use voice commands, connect to Tilora over a secure HTTPS connection/),
		).toBeInTheDocument();
	});

	it('hides the microphone section when in a secure context', async () => {
		getInsecureOriginInfo.mockReturnValue({
			needsInsecureOriginFlag: false,
			browser: 'chrome',
			isChrome: true,
			isChromium: true,
			origin: 'https://192.168.1.50',
		});

		render(Page);

		await waitFor(() => expect(settings).toHaveBeenCalled());
		expect(screen.queryByText('Microphone access')).not.toBeInTheDocument();
	});
});

describe('settings +page.svelte — devices section', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		user.set({ id: 'user1', name: 'User 1', avatar: null, role: 'member' });
		device.set({ id: 'dev1', name: 'Kitchen Tablet' });
		settings.mockResolvedValue({ ...BASE_SETTINGS });
		version.mockResolvedValue({
			current_version: '0.1.0',
			latest_version: null,
			update_available: false,
			release_url: null,
		});
		widgetTypes.mockResolvedValue([]);
		listUsers.mockResolvedValue([]);
		listHouseholdUsers.mockResolvedValue([]);
		getPreferences.mockResolvedValue({ ...DEFAULT_PREFERENCES });
		listWidgets.mockResolvedValue([]);
		ttsVoices.mockResolvedValue([]);
		listBrowserVoices.mockResolvedValue([]);
		listNetworkIntegrations.mockResolvedValue([]);
	});

	it('renders a unified list of devices with (this device) badge on current device', async () => {
		listDevices.mockResolvedValue([
			{ id: 'dev1', name: 'Kitchen Tablet', last_seen_at: '2026-01-01T00:00:00Z' },
			{ id: 'dev2', name: 'Living Room TV', last_seen_at: '2026-01-01T00:00:00Z' },
		]);

		render(Page);

		expect(await screen.findByText('Kitchen Tablet')).toBeInTheDocument();
		expect(screen.getByText('Living Room TV')).toBeInTheDocument();
		expect(screen.getByText('this device')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Rename' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Forget device' })).toBeInTheDocument();
		expect(screen.queryByPlaceholderText('This device')).not.toBeInTheDocument();
	});

	it('opens rename form when Rename is clicked and allows saving new name', async () => {
		listDevices.mockResolvedValue([{ id: 'dev1', name: 'Kitchen Tablet', last_seen_at: '2026-01-01T00:00:00Z' }]);
		renameDevice.mockResolvedValue({ id: 'dev1', name: 'Countertop Tablet' });

		render(Page);

		expect(await screen.findByText('Kitchen Tablet')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Rename' }));

		const input = screen.getByDisplayValue('Kitchen Tablet');
		expect(input).toBeInTheDocument();

		await fireEvent.input(input, { target: { value: 'Countertop Tablet' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));

		await waitFor(() => expect(renameDevice).toHaveBeenCalledWith('Countertop Tablet'));
	});

	it('cancels rename form and restores previous view', async () => {
		listDevices.mockResolvedValue([{ id: 'dev1', name: 'Kitchen Tablet', last_seen_at: '2026-01-01T00:00:00Z' }]);

		render(Page);

		expect(await screen.findByText('Kitchen Tablet')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Rename' }));

		expect(screen.getByDisplayValue('Kitchen Tablet')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

		expect(screen.queryByDisplayValue('Kitchen Tablet')).not.toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Rename' })).toBeInTheDocument();
	});

	it('prevents renaming to a duplicate device name and shows error', async () => {
		listDevices.mockResolvedValue([
			{ id: 'dev1', name: 'Kitchen Tablet', last_seen_at: '2026-01-01T00:00:00Z' },
			{ id: 'dev2', name: 'Living Room TV', last_seen_at: '2026-01-01T00:00:00Z' },
		]);

		render(Page);

		expect(await screen.findByText('Kitchen Tablet')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Rename' }));

		const input = screen.getByDisplayValue('Kitchen Tablet');
		await fireEvent.input(input, { target: { value: 'Living Room TV' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));

		expect(renameDevice).not.toHaveBeenCalled();
		expect(await screen.findByText('A device with that name already exists.')).toBeInTheDocument();
	});

	it('allows forgetting other devices with confirmation', async () => {
		listDevices.mockResolvedValue([
			{ id: 'dev1', name: 'Kitchen Tablet', last_seen_at: '2026-01-01T00:00:00Z' },
			{ id: 'dev2', name: 'Living Room TV', last_seen_at: '2026-01-01T00:00:00Z' },
		]);
		deleteDevice.mockResolvedValue({ status: 'ok' });

		render(Page);

		expect(await screen.findByText('Living Room TV')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Forget device' }));

		expect(screen.getByRole('button', { name: 'Forget' })).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Forget' }));

		await waitFor(() => expect(deleteDevice).toHaveBeenCalledWith('dev2'));
	});
});
