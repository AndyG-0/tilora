<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		api,
		type AppSettings,
		type VersionInfo,
		type DeviceListEntry,
		type HouseholdUser,
		type WidgetSummaryMeta,
		type TTSVoice,
	} from '$lib/api';
	import { user, logout } from '$lib/stores/user';
	import { device as currentDevice, renameDevice as renameCurrentDevice } from '$lib/stores/device';
	import { widgets } from '$lib/stores/widgets';
	import { screensaverSettings, persistScreensaverSettings, forceScreensaverPreview } from '$lib/stores/screensaver';
	import {
		isScreensaverAllowedType,
		TEXT_ANIMATION_STYLES,
		type TextAnimationStyle,
		FLIPBOARD_PATTERNS,
		type FlipboardPattern,
	} from '$lib/screensaverTypes';
	import {
		voiceSelection,
		loadVoiceSelectionFromServer,
		persistVoiceSelection,
		type VoiceProvider,
	} from '$lib/stores/voice';
	import { listBrowserVoices, speak } from '$lib/speech';
	import { getInsecureOriginInfo, type InsecureOriginInfo } from '$lib/network';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';
	import { locale, persistLocale } from '$lib/i18n';
	import { theme, persistTheme } from '$lib/stores/theme';

	let settings = $state<AppSettings | null>(null);
	let version = $state<VersionInfo | null>(null);
	let insecureOriginInfo = $state<InsecureOriginInfo | null>(null);
	let aiModelInput = $state('');
	let aiReasoningEffortInput = $state('');
	let timezoneInput = $state('UTC');
	let anthropicKeyInput = $state('');
	let openaiKeyInput = $state('');
	let geminiKeyInput = $state('');
	let googleCalendarClientIdInput = $state('');
	let googleCalendarClientSecretInput = $state('');
	let microsoftCalendarClientIdInput = $state('');
	let microsoftCalendarClientSecretInput = $state('');
	let caldavUrlInput = $state('');
	let caldavUsernameInput = $state('');
	let caldavPasswordInput = $state('');
	let icloudUsernameInput = $state('');
	let icloudPasswordInput = $state('');
	let openaiTtsEnabledInput = $state(false);
	let openaiTtsModelInput = $state('');
	let piperTtsEnabledInput = $state(false);
	let piperServerUrlInput = $state('');
	let piperVoicesInput = $state('');
	let timezoneOptions = $state<string[]>(['UTC']);
	let saving = $state(false);
	let saved = $state(false);
	let error = $state<string | null>(null);

	// Name/avatar/PIN for the logged-in profile — separate save flow from
	// the app-wide settings above since it hits /api/users/me, not
	// /api/settings.
	let profileNameInput = $state('');
	let profileAvatarInput = $state('');
	let profilePinInput = $state('');
	let profileHasPin = $state(false);
	let profileSaving = $state(false);
	let profileSaved = $state(false);
	let profileError = $state<string | null>(null);
	let confirmingDeleteProfile = $state(false);
	let deletingProfile = $state(false);
	let profileInitialized = false;

	// $user loads asynchronously (see +layout.svelte's gate), so seed these
	// inputs the first time it becomes available rather than in onMount.
	$effect(() => {
		if ($user && !profileInitialized) {
			profileInitialized = true;
			profileNameInput = $user.name;
			profileAvatarInput = $user.avatar ?? '';
			const currentUserId = $user.id;
			api
				.listUsers()
				.then((profiles) => {
					profileHasPin = profiles.find((p) => p.id === currentUserId)?.has_pin ?? false;
				})
				.catch(() => {
					// leave the PIN section assuming no PIN is set
				});
		}
	});

	// /api/settings is admin-only — load it lazily once $user is known to be
	// an admin, mirroring profileInitialized below, so a member never fires a
	// request that's guaranteed to 403.
	let settingsInitialized = false;

	$effect(() => {
		if ($user?.role === 'admin' && !settingsInitialized) {
			settingsInitialized = true;
			loadSettings();
		}
	});

	async function loadSettings() {
		try {
			settings = await api.settings();
			aiModelInput = settings.ai_model;
			aiReasoningEffortInput = settings.ai_reasoning_effort;
			timezoneInput = settings.timezone;
			caldavUrlInput = settings.caldav_url;
			caldavUsernameInput = settings.caldav_username;
			icloudUsernameInput = settings.icloud_username;
			openaiTtsEnabledInput = settings.openai_tts_enabled === 'true';
			openaiTtsModelInput = settings.openai_tts_model;
			piperTtsEnabledInput = settings.piper_tts_enabled === 'true';
			piperServerUrlInput = settings.piper_server_url;
			piperVoicesInput = settings.piper_voices;
			if (!timezoneOptions.includes(timezoneInput)) timezoneOptions = [timezoneInput, ...timezoneOptions];
		} catch {
			error = 'Could not load settings.';
		}
	}

	let householdUsers = $state<HouseholdUser[]>([]);
	let householdError = $state<string | null>(null);
	let householdLoading = $state(false);
	let updatingRoleId = $state<string | null>(null);
	let confirmingRemoveId = $state<string | null>(null);
	let removingId = $state<string | null>(null);
	let householdInitialized = false;

	$effect(() => {
		if ($user?.role === 'admin' && !householdInitialized) {
			householdInitialized = true;
			loadHouseholdUsers();
		}
	});

	async function loadHouseholdUsers() {
		householdLoading = true;
		householdError = null;
		try {
			householdUsers = await api.listHouseholdUsers();
		} catch {
			householdError = 'Could not load household members.';
		} finally {
			householdLoading = false;
		}
	}

	async function toggleRole(member: HouseholdUser) {
		const nextRole = member.role === 'admin' ? 'member' : 'admin';
		updatingRoleId = member.id;
		householdError = null;
		try {
			const updated = await api.updateUserRole(member.id, nextRole);
			householdUsers = householdUsers.map((existing) => (existing.id === member.id ? updated : existing));
		} catch {
			householdError = member.role === 'admin' ? "Can't demote the last remaining admin." : 'Could not update role.';
		} finally {
			updatingRoleId = null;
		}
	}

	async function removeMember(id: string) {
		removingId = id;
		householdError = null;
		try {
			await api.removeHouseholdUser(id);
			householdUsers = householdUsers.filter((u) => u.id !== id);
		} catch {
			householdError = 'Could not remove this member.';
		} finally {
			removingId = null;
			confirmingRemoveId = null;
		}
	}

	let devices = $state<DeviceListEntry[]>([]);
	let devicesError = $state<string | null>(null);
	let deviceNameInput = $state('');
	let savingDeviceName = $state(false);
	let confirmingForgetDeviceId = $state<string | null>(null);
	let forgettingDeviceId = $state<string | null>(null);
	let deviceNameInitialized = false;

	$effect(() => {
		if ($currentDevice && !deviceNameInitialized) {
			deviceNameInitialized = true;
			deviceNameInput = $currentDevice.name;
		}
	});

	async function loadDevices() {
		try {
			devices = await api.listDevices();
		} catch {
			devicesError = get(_)('settings.devices.load_error');
		}
	}

	// Screensaver settings are scoped to this (user, device) pair — same tier
	// as the device name above. $screensaverSettings is loaded app-wide by
	// +layout.svelte once $user is known, so it's typically already populated
	// by the time this page mounts; seed the form the first time it arrives
	// rather than in onMount.
	let ssEnabled = $state(false);
	let ssIdleTimeoutInput = $state(300);
	let ssRotationIntervalInput = $state(25);
	let ssSelectedIds = $state<Set<string>>(new Set());
	let ssTextAnimationStyle = $state<TextAnimationStyle>('marquee');
	let ssLedColor = $state('#ff8a00');
	let ssTextPauseInput = $state(8);
	let ssFlipboardPattern = $state<FlipboardPattern>('top_to_bottom');
	let ssSaving = $state(false);
	let ssSaved = $state(false);
	let ssError = $state<string | null>(null);
	let ssInitialized = false;

	// Only the widget types the screensaver actually knows how to render
	// full-screen (see $lib/screensaverTypes) show up in the picker below —
	// dashboard-utility types like Pi-hole or container stats are hidden
	// entirely rather than shown disabled.
	const screensaverEligibleWidgets = $derived($widgets.filter((w) => isScreensaverAllowedType(w.type)));

	$effect(() => {
		if ($screensaverSettings && !ssInitialized) {
			ssInitialized = true;
			ssEnabled = $screensaverSettings.enabled;
			ssIdleTimeoutInput = $screensaverSettings.idle_timeout_seconds;
			ssRotationIntervalInput = $screensaverSettings.rotation_interval_seconds;
			ssSelectedIds = new Set($screensaverSettings.widget_ids);
			ssTextAnimationStyle = $screensaverSettings.text_animation_style;
			ssLedColor = $screensaverSettings.led_color;
			ssTextPauseInput = $screensaverSettings.text_pause_seconds;
			ssFlipboardPattern = $screensaverSettings.flipboard_pattern;
		}
	});

	// Friendly type -> label lookup (e.g. "clock" -> "Clock"), same source
	// the dashboard's "+ Add widget" picker uses — falls back to the raw
	// type string per-widget below if this never loads.
	let widgetTypeNames = $state<Record<string, string>>({});

	// Fallback matches the backend's default set; refreshed from /api/theme
	// on mount so new themes show up without a frontend redeploy.
	let themeIds = $state(['light', 'dark', 'sepia', 'contrast', 'forest', 'ocean']);
	let themeNames = $state<Record<string, string>>({});

	// Widget types that make for a good screensaver slide by default — only
	// used to pre-check a sensible starting selection the first time a user
	// enables the screensaver with nothing chosen yet; never persisted unless
	// they hit Save.
	const SCREENSAVER_FRIENDLY_TYPES = ['clock', 'ai', 'discord', 'message', 'photos'];

	const TEXT_ANIMATION_STYLE_LABELS: Record<TextAnimationStyle, string> = $derived({
		marquee: $_('settings.screensaver.animation_marquee'),
		matrix: $_('settings.screensaver.animation_matrix'),
		flipboard: $_('settings.screensaver.animation_flipboard'),
		led_dots: $_('settings.screensaver.animation_led_dots'),
	});

	const FLIPBOARD_PATTERN_LABELS: Record<FlipboardPattern, string> = $derived({
		top_to_bottom: $_('settings.screensaver.pattern_top_to_bottom'),
		random: $_('settings.screensaver.pattern_random'),
	});

	function widgetLabel(widget: WidgetSummaryMeta, list: WidgetSummaryMeta[]) {
		const base = widgetTypeNames[widget.type] ?? widget.type;
		const sameType = list.filter((w) => w.type === widget.type);
		if (sameType.length <= 1) return base;
		return `${base} (${sameType.indexOf(widget) + 1})`;
	}

	function toggleScreensaverEnabled() {
		ssEnabled = !ssEnabled;
		if (ssEnabled && ssSelectedIds.size === 0) {
			const preChecked = $widgets.filter((w) => SCREENSAVER_FRIENDLY_TYPES.includes(w.type)).map((w) => w.id);
			if (preChecked.length > 0) ssSelectedIds = new Set(preChecked);
		}
	}

	function toggleScreensaverWidget(id: string) {
		const next = new Set(ssSelectedIds);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		ssSelectedIds = next;
	}

	async function saveScreensaverSettings() {
		ssSaving = true;
		ssSaved = false;
		ssError = null;
		try {
			await persistScreensaverSettings({
				enabled: ssEnabled,
				idle_timeout_seconds: ssIdleTimeoutInput,
				rotation_interval_seconds: ssRotationIntervalInput,
				widget_ids: Array.from(ssSelectedIds),
				text_animation_style: ssTextAnimationStyle,
				led_color: ssLedColor,
				text_pause_seconds: ssTextPauseInput,
				flipboard_pattern: ssFlipboardPattern,
			});
			ssSaved = true;
		} catch {
			ssError = get(_)('settings.screensaver.save_error');
		} finally {
			ssSaving = false;
		}
	}

	// Voice choice for the AI assistant/read-aloud, scoped to this user's
	// account (not this device) — see stores/voice.ts. Seeded independently
	// (rather than relying on +layout.svelte's fire-and-forget load having
	// already resolved) the same way profileInitialized re-fetches its own
	// data above, since $voiceSelection starts as a real (default) value
	// rather than null, so there's no "not loaded yet" sentinel to gate on.
	let browserVoices = $state<SpeechSynthesisVoice[]>([]);
	let cloudVoices = $state<TTSVoice[]>([]);
	let voiceProviderInput = $state<VoiceProvider>('browser');
	let voiceIdInput = $state('');
	let voiceSaving = $state(false);
	let voiceSaved = $state(false);
	let voiceError = $state<string | null>(null);
	let voiceInitialized = false;

	$effect(() => {
		if ($user && !voiceInitialized) {
			voiceInitialized = true;
			loadVoiceSelectionFromServer().then(() => {
				voiceProviderInput = $voiceSelection.provider;
				voiceIdInput = $voiceSelection.voiceId;
			});
		}
	});

	const availableVoiceProviders = $derived(
		(['browser', 'openai', 'piper'] as VoiceProvider[]).filter(
			(p) => p === 'browser' || cloudVoices.some((v) => v.provider === p),
		),
	);

	const voiceOptions = $derived(
		voiceProviderInput === 'browser'
			? browserVoices.map((v) => ({ id: v.voiceURI, label: `${v.name} (${v.lang})` }))
			: cloudVoices.filter((v) => v.provider === voiceProviderInput).map((v) => ({ id: v.id, label: v.label })),
	);

	function voiceProviderLabel(p: VoiceProvider) {
		if (p === 'browser') return $_('settings.voice.provider_browser');
		return p === 'openai' ? $_('settings.voice.provider_openai') : $_('settings.voice.provider_piper');
	}

	function selectVoiceProvider(p: VoiceProvider) {
		voiceProviderInput = p;
		const ids =
			p === 'browser'
				? browserVoices.map((v) => v.voiceURI)
				: cloudVoices.filter((v) => v.provider === p).map((v) => v.id);
		if (!ids.includes(voiceIdInput)) voiceIdInput = ids[0] ?? '';
	}

	function currentVoiceSelection() {
		const voiceName =
			voiceProviderInput === 'browser' ? (browserVoices.find((v) => v.voiceURI === voiceIdInput)?.name ?? '') : '';
		return { provider: voiceProviderInput, voiceId: voiceIdInput, voiceName };
	}

	function previewVoice() {
		speak(get(_)('settings.voice.preview_text'), currentVoiceSelection());
	}

	async function saveVoiceSelection() {
		voiceSaving = true;
		voiceSaved = false;
		voiceError = null;
		try {
			await persistVoiceSelection(currentVoiceSelection());
			voiceSaved = true;
		} catch {
			voiceError = get(_)('settings.voice.save_error');
		} finally {
			voiceSaving = false;
		}
	}

	onMount(async () => {
		try {
			// Intl.supportedValuesOf isn't in every browser's types yet, but is
			// available in the Chromium the kiosk runs — avoids shipping a
			// hardcoded IANA timezone list.
			const supported = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.(
				'timeZone',
			);
			if (supported?.length) timezoneOptions = supported;
		} catch {
			// keep the UTC-only fallback
		}

		try {
			version = await api.version();
		} catch {
			// leave the update section hidden
		}

		insecureOriginInfo = getInsecureOriginInfo();

		try {
			const types = await api.widgetTypes();
			widgetTypeNames = Object.fromEntries(types.map((t) => [t.type, t.name]));
		} catch {
			// fall back to showing raw type strings below
		}

		try {
			const { themes } = await api.themes();
			themeIds = themes.map((t) => t.id);
			themeNames = Object.fromEntries(themes.map((t) => [t.id, t.name]));
		} catch {
			// keep the fallback list
		}

		try {
			browserVoices = await listBrowserVoices();
		} catch {
			// leave browserVoices empty — the Voice section then only offers cloud/Piper voices, if any
		}

		try {
			cloudVoices = await api.ttsVoices();
		} catch {
			// leave cloudVoices empty — the Voice section then only offers the browser source
		}

		await loadDevices();
	});

	async function save() {
		saving = true;
		saved = false;
		error = null;
		try {
			const partial: Record<string, string> = {
				ai_model: aiModelInput,
				ai_reasoning_effort: aiReasoningEffortInput,
				timezone: timezoneInput,
				caldav_url: caldavUrlInput,
				caldav_username: caldavUsernameInput,
				icloud_username: icloudUsernameInput,
				openai_tts_enabled: openaiTtsEnabledInput ? 'true' : '',
				openai_tts_model: openaiTtsModelInput,
				piper_tts_enabled: piperTtsEnabledInput ? 'true' : '',
				piper_server_url: piperServerUrlInput,
				piper_voices: piperVoicesInput,
			};
			if (anthropicKeyInput) partial.anthropic_api_key = anthropicKeyInput;
			if (openaiKeyInput) partial.openai_api_key = openaiKeyInput;
			if (geminiKeyInput) partial.gemini_api_key = geminiKeyInput;
			if (googleCalendarClientIdInput) partial.google_calendar_client_id = googleCalendarClientIdInput;
			if (googleCalendarClientSecretInput) partial.google_calendar_client_secret = googleCalendarClientSecretInput;
			if (microsoftCalendarClientIdInput) partial.microsoft_calendar_client_id = microsoftCalendarClientIdInput;
			if (microsoftCalendarClientSecretInput)
				partial.microsoft_calendar_client_secret = microsoftCalendarClientSecretInput;
			if (caldavPasswordInput) partial.caldav_password = caldavPasswordInput;
			if (icloudPasswordInput) partial.icloud_password = icloudPasswordInput;

			settings = await api.updateSettings(partial);
			anthropicKeyInput = '';
			openaiKeyInput = '';
			geminiKeyInput = '';
			googleCalendarClientIdInput = '';
			googleCalendarClientSecretInput = '';
			microsoftCalendarClientIdInput = '';
			microsoftCalendarClientSecretInput = '';
			caldavPasswordInput = '';
			icloudPasswordInput = '';
			saved = true;
		} catch {
			error = 'Could not save settings.';
		} finally {
			saving = false;
		}
	}

	async function clearKey(
		key:
			| 'anthropic_api_key'
			| 'openai_api_key'
			| 'gemini_api_key'
			| 'google_calendar_client_id'
			| 'google_calendar_client_secret'
			| 'microsoft_calendar_client_id'
			| 'microsoft_calendar_client_secret'
			| 'caldav_password'
			| 'icloud_password',
	) {
		error = null;
		try {
			settings = await api.updateSettings({ [key]: '' });
		} catch {
			error = 'Could not clear the key.';
		}
	}

	async function saveProfile() {
		if (profilePinInput && !/^\d{4,8}$/.test(profilePinInput)) {
			profileError = get(_)('settings.profile.pin_invalid');
			return;
		}
		profileSaving = true;
		profileSaved = false;
		profileError = null;
		try {
			const partial: { name?: string; avatar?: string; pin?: string } = {
				name: profileNameInput.trim(),
				avatar: profileAvatarInput.trim(),
			};
			if (profilePinInput) partial.pin = profilePinInput;
			const updated = await api.updateUser(partial);
			user.set(updated);
			if (profilePinInput) profileHasPin = true;
			profilePinInput = '';
			profileSaved = true;
		} catch {
			profileError = get(_)('settings.profile.save_error');
		} finally {
			profileSaving = false;
		}
	}

	async function clearPin() {
		profileError = null;
		try {
			const updated = await api.updateUser({ pin: '' });
			user.set(updated);
			profileHasPin = false;
		} catch {
			profileError = get(_)('settings.profile.clear_pin_error');
		}
	}

	async function deleteProfile() {
		deletingProfile = true;
		profileError = null;
		try {
			await api.deleteUser();
			await logout().catch(() => {});
			goto('/login');
		} catch {
			profileError = get(_)('settings.profile.delete_error');
			deletingProfile = false;
			confirmingDeleteProfile = false;
		}
	}

	async function saveDeviceName() {
		savingDeviceName = true;
		devicesError = null;
		try {
			await renameCurrentDevice(deviceNameInput.trim());
			await loadDevices();
		} catch {
			devicesError = get(_)('settings.devices.rename_error');
		} finally {
			savingDeviceName = false;
		}
	}

	async function forgetDevice(id: string) {
		forgettingDeviceId = id;
		devicesError = null;
		try {
			await api.deleteDevice(id);
			devices = devices.filter((d) => d.id !== id);
		} catch {
			devicesError = get(_)('settings.devices.forget_error');
		} finally {
			forgettingDeviceId = null;
			confirmingForgetDeviceId = null;
		}
	}
</script>

<div class="settings-page">
	<button class="back" onclick={() => goto('/')}>{$_('common.back')}</button>
	<h1>{$_('settings.page.title')}</h1>

	{#if $user?.role === 'admin'}
		<div class="settings-group">
			<h2 class="group-title">Admin settings</h2>
			<p class="group-subtitle">Shared across the whole household — visible only to admins.</p>

			<section>
				<h3>Household members</h3>
				{#if householdError}
					<p class="hint error">{householdError}</p>
				{/if}
				{#if householdLoading && householdUsers.length === 0}
					<p class="hint">Loading…</p>
				{:else}
					<ul class="member-list">
						{#each householdUsers as member (member.id)}
							<li>
								<span class="member-info">
									<span class="avatar-sm">{member.avatar || member.name.charAt(0).toUpperCase()}</span>
									<span class="member-name">{member.name}</span>
									<span class="role-badge" class:admin={member.role === 'admin'}>{member.role}</span>
								</span>
								{#if member.id === $user.id}
									<span class="hint">(you)</span>
								{:else}
									<span class="member-actions">
										<button class="clear" onclick={() => toggleRole(member)} disabled={updatingRoleId === member.id}>
											{member.role === 'admin' ? 'Demote to member' : 'Promote to admin'}
										</button>
										{#if confirmingRemoveId === member.id}
											<span class="confirm-actions">
												<button
													class="cancel"
													onclick={() => (confirmingRemoveId = null)}
													disabled={removingId === member.id}
												>
													Cancel
												</button>
												<button
													class="danger"
													onclick={() => removeMember(member.id)}
													disabled={removingId === member.id}
												>
													{removingId === member.id ? 'Removing…' : 'Remove'}
												</button>
											</span>
										{:else}
											<button class="danger-link" onclick={() => (confirmingRemoveId = member.id)}>Remove</button>
										{/if}
									</span>
								{/if}
							</li>
						{/each}
					</ul>
				{/if}
			</section>

			<section>
				<h3>{$_('network_settings.title')}</h3>
				<p class="hint">{$_('network_settings.subtitle')}</p>
				<button class="clear" onclick={() => goto('/settings/network')}>{$_('network_settings.nav_link')}</button>
			</section>

			{#if !settings}
				<p class="hint">{error ?? 'Loading…'}</p>
			{:else}
				<section>
					<h3>AI provider</h3>
					<label>
						Model
						<input type="text" bind:value={aiModelInput} placeholder="anthropic/claude-sonnet-5" />
					</label>
					<p class="hint">
						Follows litellm's "&lt;provider&gt;/&lt;model&gt;" convention, e.g. anthropic/claude-sonnet-5, openai/gpt-5,
						or gemini/gemini-2.5-flash.
					</p>

					<label>
						Reasoning effort
						<select bind:value={aiReasoningEffortInput}>
							<option value="">Not set (provider default)</option>
							<option value="none">None</option>
							<option value="minimal">Minimal</option>
							<option value="low">Low</option>
							<option value="medium">Medium</option>
							<option value="high">High</option>
							<option value="xhigh">Extra high</option>
						</select>
					</label>
					<p class="hint">
						Only affects models that support tunable reasoning (OpenAI o-series/gpt-5.x, Anthropic extended thinking,
						Gemini thinking) — ignored otherwise. Some OpenAI gpt-5.x models reject tool calls unless this is set to at
						least "None".
					</p>

					<label>
						Anthropic API key
						<input
							type="password"
							bind:value={anthropicKeyInput}
							placeholder={settings.has_anthropic_api_key ? 'Set — enter a new value to replace it' : 'Not set'}
						/>
					</label>
					{#if settings.has_anthropic_api_key}
						<button class="clear" onclick={() => clearKey('anthropic_api_key')}>Clear key</button>
					{/if}

					<label>
						OpenAI API key
						<input
							type="password"
							bind:value={openaiKeyInput}
							placeholder={settings.has_openai_api_key ? 'Set — enter a new value to replace it' : 'Not set'}
						/>
					</label>
					{#if settings.has_openai_api_key}
						<button class="clear" onclick={() => clearKey('openai_api_key')}>Clear key</button>
					{/if}

					<label>
						Gemini API key
						<input
							type="password"
							bind:value={geminiKeyInput}
							placeholder={settings.has_gemini_api_key ? 'Set — enter a new value to replace it' : 'Not set'}
						/>
					</label>
					{#if settings.has_gemini_api_key}
						<button class="clear" onclick={() => clearKey('gemini_api_key')}>Clear key</button>
					{/if}
				</section>

				<section>
					<h3>Voice output</h3>
					<p class="hint">
						Controls which text-to-speech options household members can choose from in "Your settings". The browser's
						built-in voice is always available and needs no setup.
					</p>

					<label class="checkbox-label">
						<input type="checkbox" bind:checked={openaiTtsEnabledInput} />
						Enable OpenAI text-to-speech
					</label>
					{#if openaiTtsEnabledInput}
						<label>
							Model
							<input type="text" bind:value={openaiTtsModelInput} placeholder="gpt-4o-mini-tts" />
						</label>
						<p class="hint">Uses the OpenAI API key set above.</p>
					{/if}

					<label class="checkbox-label">
						<input type="checkbox" bind:checked={piperTtsEnabledInput} />
						Enable Piper (self-hosted) text-to-speech
					</label>
					{#if piperTtsEnabledInput}
						<label>
							Server URL
							<input type="text" bind:value={piperServerUrlInput} placeholder="http://piper.local:5000" />
						</label>
						<label>
							Voices
							<input
								type="text"
								bind:value={piperVoicesInput}
								placeholder="en_US-lessac-medium|Lessac,en_US-amy-medium"
							/>
						</label>
						<p class="hint">
							Comma-separated list of voice IDs from your Piper server, each optionally followed by
							<code>|Display Name</code>.
						</p>
					{/if}
				</section>

				<section>
					<h3>Google Calendar</h3>
					<label>
						Client ID
						<input
							type="password"
							bind:value={googleCalendarClientIdInput}
							placeholder={settings.has_google_calendar_client_id ? 'Set — enter a new value to replace it' : 'Not set'}
						/>
					</label>
					{#if settings.has_google_calendar_client_id}
						<button class="clear" onclick={() => clearKey('google_calendar_client_id')}> Clear client ID </button>
					{/if}

					<label>
						Client secret
						<input
							type="password"
							bind:value={googleCalendarClientSecretInput}
							placeholder={settings.has_google_calendar_client_secret
								? 'Set — enter a new value to replace it'
								: 'Not set'}
						/>
					</label>
					{#if settings.has_google_calendar_client_secret}
						<button class="clear" onclick={() => clearKey('google_calendar_client_secret')}>
							Clear client secret
						</button>
					{/if}
					<p class="hint">
						From an OAuth 2.0 Client ID (console.cloud.google.com). Once saved, connect your account from the Calendar
						widget's detail view.
					</p>
				</section>

				<section>
					<h3>Microsoft 365 Calendar</h3>
					<label>
						Client ID
						<input
							type="password"
							bind:value={microsoftCalendarClientIdInput}
							placeholder={settings.has_microsoft_calendar_client_id
								? 'Set — enter a new value to replace it'
								: 'Not set'}
						/>
					</label>
					{#if settings.has_microsoft_calendar_client_id}
						<button class="clear" onclick={() => clearKey('microsoft_calendar_client_id')}> Clear client ID </button>
					{/if}

					<label>
						Client secret
						<input
							type="password"
							bind:value={microsoftCalendarClientSecretInput}
							placeholder={settings.has_microsoft_calendar_client_secret
								? 'Set — enter a new value to replace it'
								: 'Not set'}
						/>
					</label>
					{#if settings.has_microsoft_calendar_client_secret}
						<button class="clear" onclick={() => clearKey('microsoft_calendar_client_secret')}>
							Clear client secret
						</button>
					{/if}
					<p class="hint">
						From an app registration (portal.azure.com -> Microsoft Entra ID -> App registrations). Once saved, connect
						your account from a Calendar widget's detail view whose
						<code>provider</code> is <code>microsoft</code>.
					</p>
				</section>

				<section>
					<h3>CalDAV Calendar</h3>
					<label>
						Server URL
						<input type="text" bind:value={caldavUrlInput} placeholder="https://caldav.icloud.com" />
					</label>

					<label>
						Username
						<input type="text" bind:value={caldavUsernameInput} />
					</label>

					<label>
						Password
						<input
							type="password"
							bind:value={caldavPasswordInput}
							placeholder={settings.has_caldav_password ? 'Set — enter a new value to replace it' : 'Not set'}
						/>
					</label>
					{#if settings.has_caldav_password}
						<button class="clear" onclick={() => clearKey('caldav_password')}>Clear password</button>
					{/if}
					<p class="hint">
						Works with iCloud, Fastmail, Nextcloud, and most self-hosted calendars — usually an app-specific password
						rather than your account password. Set a calendar widget's
						<code>provider</code> to <code>caldav</code> in <code>dashboard.yaml</code> to use it.
					</p>
				</section>

				<section>
					<h3>iCloud Photos</h3>
					<label>
						Apple ID
						<input type="text" bind:value={icloudUsernameInput} />
					</label>

					<label>
						Password
						<input
							type="password"
							bind:value={icloudPasswordInput}
							placeholder={settings.has_icloud_password ? 'Set — enter a new value to replace it' : 'Not set'}
						/>
					</label>
					{#if settings.has_icloud_password}
						<button class="clear" onclick={() => clearKey('icloud_password')}>Clear password</button>
					{/if}
					<p class="hint">
						Your real Apple ID and account password (Apple doesn't support app-specific passwords here), so this grants
						full account access, not just Photos — only fill this in if you're comfortable with that. Save this section,
						then switch a Photos widget to <strong>iCloud (Private Library)</strong> from that widget's detail view and connect
						(including any 2FA prompt) there.
					</p>
				</section>

				<section>
					<h3>Timezone</h3>
					<label>
						Used by the clock and date widgets
						<select bind:value={timezoneInput}>
							{#each timezoneOptions as tz (tz)}
								<option value={tz}>{tz}</option>
							{/each}
						</select>
					</label>
				</section>

				{#if error}
					<p class="hint error">{error}</p>
				{/if}
				{#if saved}
					<p class="hint">Saved.</p>
				{/if}

				<button class="save" disabled={saving} onclick={save}>
					{saving ? 'Saving…' : 'Save'}
				</button>
			{/if}
		</div>
	{/if}

	<div class="settings-group">
		<h2 class="group-title">{$_('settings.your_settings.title')}</h2>
		<p class="group-subtitle">{$_('settings.your_settings.subtitle')}</p>

		<section>
			<h3>{$_('settings.profile.heading')}</h3>
			<label>
				{$_('settings.profile.name_label')}
				<input type="text" bind:value={profileNameInput} maxlength="40" />
			</label>
			<label>
				{$_('settings.profile.avatar_label')}
				<input type="text" bind:value={profileAvatarInput} placeholder="🐱" maxlength="8" />
			</label>
			<label>
				{$_('settings.profile.pin_label')}
				<input
					type="password"
					inputmode="numeric"
					bind:value={profilePinInput}
					placeholder={profileHasPin ? $_('common.password_set_hint') : $_('settings.profile.pin_not_set')}
					maxlength="8"
				/>
			</label>
			{#if profileHasPin}
				<button class="clear" onclick={clearPin}>{$_('settings.profile.clear_pin')}</button>
			{/if}
			{#if profileError}
				<p class="hint error">{profileError}</p>
			{/if}
			{#if profileSaved}
				<p class="hint">{$_('common.saved')}</p>
			{/if}
			<button class="save" disabled={profileSaving || !profileNameInput.trim()} onclick={saveProfile}>
				{profileSaving ? $_('common.saving') : $_('settings.profile.save')}
			</button>

			{#if confirmingDeleteProfile}
				<p class="hint error">{$_('settings.profile.delete_confirm')}</p>
				<div class="confirm-actions">
					<button class="cancel" onclick={() => (confirmingDeleteProfile = false)} disabled={deletingProfile}>
						{$_('common.cancel')}
					</button>
					<button class="danger" onclick={deleteProfile} disabled={deletingProfile}>
						{deletingProfile ? $_('settings.profile.deleting') : $_('settings.profile.delete')}
					</button>
				</div>
			{:else}
				<button class="danger-link" onclick={() => (confirmingDeleteProfile = true)}
					>{$_('settings.profile.delete_link')}</button
				>
			{/if}
		</section>

		<section>
			<h3>{$_('settings.devices.heading')}</h3>
			{#if $currentDevice}
				<label>
					{$_('settings.devices.this_device_label')}
					<input type="text" bind:value={deviceNameInput} maxlength="40" />
				</label>
				<button class="save" disabled={savingDeviceName || !deviceNameInput.trim()} onclick={saveDeviceName}>
					{savingDeviceName ? $_('common.saving') : $_('settings.devices.rename')}
				</button>
			{/if}

			{#if devicesError}
				<p class="hint error">{devicesError}</p>
			{/if}

			{#if devices.filter((d) => d.id !== $currentDevice?.id).length > 0}
				<ul class="device-list">
					{#each devices.filter((d) => d.id !== $currentDevice?.id) as d (d.id)}
						<li>
							<span class="device-name">{d.name}</span>
							{#if confirmingForgetDeviceId === d.id}
								<span class="confirm-actions">
									<button
										class="cancel"
										onclick={() => (confirmingForgetDeviceId = null)}
										disabled={forgettingDeviceId === d.id}
									>
										{$_('common.cancel')}
									</button>
									<button class="danger" onclick={() => forgetDevice(d.id)} disabled={forgettingDeviceId === d.id}>
										{forgettingDeviceId === d.id ? $_('settings.devices.forgetting') : $_('settings.devices.forget')}
									</button>
								</span>
							{:else}
								<button class="danger-link" onclick={() => (confirmingForgetDeviceId = d.id)}
									>{$_('settings.devices.forget_device')}</button
								>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		</section>

		<section>
			<h3>{$_('settings.screensaver.heading')}</h3>
			<label class="checkbox-label">
				<input type="checkbox" checked={ssEnabled} onchange={toggleScreensaverEnabled} />
				{$_('settings.screensaver.enable_label')}
			</label>

			{#if ssEnabled}
				<label>
					{$_('settings.screensaver.idle_timeout_label')}
					<input type="number" min="10" bind:value={ssIdleTimeoutInput} />
				</label>
				<label>
					{$_('settings.screensaver.rotation_interval_label')}
					<input type="number" min="5" bind:value={ssRotationIntervalInput} />
				</label>
				<label>
					{$_('settings.screensaver.animation_label')}
					<select bind:value={ssTextAnimationStyle}>
						{#each TEXT_ANIMATION_STYLES as style (style)}
							<option value={style}>{TEXT_ANIMATION_STYLE_LABELS[style]}</option>
						{/each}
					</select>
				</label>

				{#if ssTextAnimationStyle !== 'marquee'}
					<label>
						{$_('settings.screensaver.reading_pause_label')}
						<input type="number" min="1" bind:value={ssTextPauseInput} />
					</label>
					<p class="hint">{$_('settings.screensaver.reading_pause_hint')}</p>
				{/if}

				{#if ssTextAnimationStyle === 'led_dots'}
					<label>
						{$_('settings.screensaver.led_color_label')}
						<input type="color" bind:value={ssLedColor} />
					</label>
				{/if}

				{#if ssTextAnimationStyle === 'flipboard'}
					<label>
						{$_('settings.screensaver.flipboard_pattern_label')}
						<select bind:value={ssFlipboardPattern}>
							{#each FLIPBOARD_PATTERNS as pattern (pattern)}
								<option value={pattern}>{FLIPBOARD_PATTERN_LABELS[pattern]}</option>
							{/each}
						</select>
					</label>
				{/if}

				{#if screensaverEligibleWidgets.length > 0}
					<p class="hint">{$_('settings.screensaver.widgets_hint')}</p>
					<ul class="widget-picker">
						{#each screensaverEligibleWidgets as w (w.id)}
							<li>
								<label class="checkbox-label">
									<input
										type="checkbox"
										checked={ssSelectedIds.has(w.id)}
										onchange={() => toggleScreensaverWidget(w.id)}
									/>
									{widgetLabel(w, screensaverEligibleWidgets)}
								</label>
							</li>
						{/each}
					</ul>
				{:else}
					<p class="hint">{$_('settings.screensaver.no_widgets_hint')}</p>
				{/if}
			{/if}

			{#if ssError}
				<p class="hint error">{ssError}</p>
			{/if}
			{#if ssSaved}
				<p class="hint">{$_('common.saved')}</p>
			{/if}
			<div class="button-row">
				<button class="save" disabled={ssSaving} onclick={saveScreensaverSettings}>
					{ssSaving ? $_('common.saving') : $_('settings.screensaver.save')}
				</button>
				<button
					class="clear"
					disabled={screensaverEligibleWidgets.length === 0}
					onclick={() => forceScreensaverPreview.set(true)}
				>
					{$_('settings.screensaver.test')}
				</button>
			</div>
		</section>

		<section>
			<h3>{$_('settings.voice.heading')}</h3>
			<label>
				{$_('settings.voice.source_label')}
				<select
					value={voiceProviderInput}
					onchange={(e) => selectVoiceProvider(e.currentTarget.value as VoiceProvider)}
				>
					{#each availableVoiceProviders as p (p)}
						<option value={p}>{voiceProviderLabel(p)}</option>
					{/each}
				</select>
			</label>

			{#if voiceOptions.length > 0}
				<label>
					{$_('settings.voice.voice_label')}
					<select bind:value={voiceIdInput}>
						{#each voiceOptions as opt (opt.id)}
							<option value={opt.id}>{opt.label}</option>
						{/each}
					</select>
				</label>
			{:else}
				<p class="hint">{$_('settings.voice.no_voices_hint')}</p>
			{/if}

			<button class="clear" disabled={!voiceIdInput} onclick={previewVoice}>{$_('settings.voice.preview')}</button>

			{#if voiceError}
				<p class="hint error">{voiceError}</p>
			{/if}
			{#if voiceSaved}
				<p class="hint">{$_('common.saved')}</p>
			{/if}
			<button class="save" disabled={voiceSaving || !voiceIdInput} onclick={saveVoiceSelection}>
				{voiceSaving ? $_('common.saving') : $_('settings.voice.save')}
			</button>
		</section>

		<section>
			<h3>{$_('settings.language.title')}</h3>
			<select
				aria-label={$_('settings.language.title')}
				value={$locale}
				onchange={(e) => {
					locale.set(e.currentTarget.value);
					persistLocale(e.currentTarget.value);
				}}
			>
				<option value="en">English</option>
				<option value="es">Español</option>
				<option value="fr">Français</option>
				<option value="de">Deutsch</option>
			</select>
		</section>

		<section>
			<h3>{$_('settings.appearance.title')}</h3>
			<select
				aria-label={$_('settings.appearance.title')}
				value={$theme}
				onchange={(e) => {
					theme.set(e.currentTarget.value);
					persistTheme(e.currentTarget.value);
				}}
			>
				{#each themeIds as id (id)}
					<option value={id}>{themeNames[id] ?? id}</option>
				{/each}
			</select>
		</section>

		{#if insecureOriginInfo?.needsInsecureOriginFlag}
			<section>
				<h3>{$_('settings.microphone.heading')}</h3>
				<p class="hint">
					{$_('settings.microphone.intro', { values: { origin: insecureOriginInfo.origin } })}
				</p>
				{#if insecureOriginInfo.isChrome}
					<p class="hint">
						{$_('settings.microphone.open_prefix')}
						<a href="chrome://flags/#unsafely-treat-insecure-origin-as-secure" target="_blank" rel="noreferrer"
							>chrome://flags/#unsafely-treat-insecure-origin-as-secure</a
						>{$_('settings.microphone.after_link')} <code>{insecureOriginInfo.origin}</code>
						{$_('settings.microphone.list_suffix')}
					</p>
				{:else}
					<p class="hint">
						{$_('settings.microphone.in_chrome_open')}
						<code>chrome://flags/#unsafely-treat-insecure-origin-as-secure</code>{$_('settings.microphone.after_link')}
						<code>{insecureOriginInfo.origin}</code>
						{$_('settings.microphone.list_suffix')}
					</p>
				{/if}
			</section>
		{/if}

		{#if version}
			<section>
				<h3>{$_('settings.update.heading')}</h3>
				<p class="hint">{$_('settings.update.running_version', { values: { version: version.current_version } })}</p>
				{#if version.update_available}
					<p class="hint">
						{$_('settings.update.available', { values: { version: version.latest_version } })}
						{#if version.release_url}
							— <a href={version.release_url} target="_blank" rel="noreferrer">{$_('settings.update.view_release')}</a>
						{/if}
					</p>
				{/if}
			</section>
		{/if}
	</div>
</div>

<style>
	.settings-page {
		padding: 2rem;
		min-height: 100vh;
		max-width: 30rem;
	}

	.back {
		background: none;
		border: none;
		font-size: 1.1rem;
		color: var(--color-accent);
		margin-bottom: 1.5rem;
		cursor: pointer;
		padding: 0.5rem 0;
	}

	h1 {
		margin: 0 0 1.5rem;
	}

	section {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-bottom: 1.5rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem;
	}

	section h3 {
		margin: 0;
		font-size: 1rem;
	}

	.settings-group {
		margin-bottom: 2rem;
	}

	.group-title {
		margin: 0 0 0.25rem;
		font-size: 1.2rem;
	}

	.group-subtitle {
		margin: 0 0 1rem;
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	input,
	select {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.clear {
		align-self: flex-start;
		background: none;
		border: none;
		color: var(--color-text-muted);
		text-decoration: underline;
		cursor: pointer;
		padding: 0;
		font-size: 0.85rem;
	}

	.button-row {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.save {
		align-self: flex-start;
		background: var(--color-accent);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.save:disabled,
	.danger:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.danger-link {
		align-self: flex-start;
		background: none;
		border: none;
		color: var(--color-error);
		text-decoration: underline;
		cursor: pointer;
		padding: 0;
		font-size: 0.85rem;
	}

	.confirm-actions {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.confirm-actions .cancel {
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		padding: 0;
		font-size: 0.85rem;
	}

	.danger {
		background: var(--color-error);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		cursor: pointer;
		font-size: 0.85rem;
	}

	.device-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.device-list li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.device-name {
		font-size: 0.9rem;
	}

	.member-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.member-list li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.member-info {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.avatar-sm {
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		background: var(--color-surface-hover, var(--color-border));
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1rem;
	}

	.member-name {
		font-size: 0.9rem;
	}

	.role-badge {
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-text-muted);
		border: 1px solid var(--color-border);
		border-radius: 999px;
		padding: 0.1rem 0.5rem;
	}

	.role-badge.admin {
		color: var(--color-accent);
		border-color: var(--color-accent);
	}

	.member-actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.hint a {
		color: var(--color-accent);
	}

	.hint {
		color: var(--color-text-muted);
		margin: 0.25rem 0 0;
	}

	.hint.error {
		color: var(--color-error);
	}

	.checkbox-label {
		flex-direction: row;
		align-items: center;
		gap: 0.5rem;
	}

	.widget-picker {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
</style>
