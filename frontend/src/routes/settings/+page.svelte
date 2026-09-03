<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		api,
		type AppSettings,
		type VersionInfo,
		type DeviceListEntry,
		type HouseholdUser,
		type TTSVoice,
		type NetworkIntegration,
		type NetworkTestConnectionResult,
		type IcloudCredentials,
		type CityResult,
		type LocationPreference,
	} from '$lib/api';
	import ContainerHostRow from '$lib/components/settings/ContainerHostRow.svelte';
	import { user, logout } from '$lib/stores/user';
	import { device as currentDevice, renameDevice as renameCurrentDevice } from '$lib/stores/device';
	import { pwaState, promptInstall } from '$lib/stores/pwa';
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
	import {
		agentName,
		alwaysOnMic,
		loadAlwaysOnMicFromServer,
		persistAlwaysOnMic,
		loadAssistantConfigFromServer,
	} from '$lib/stores/assistant';
	import { userLocation, loadLocationFromServer, persistLocation } from '$lib/stores/location';
	import { listBrowserVoices, speak, ensureMicrophonePermission } from '$lib/speech';
	import { getInsecureOriginInfo, type InsecureOriginInfo } from '$lib/network';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';
	import { locale, persistLocale } from '$lib/i18n';
	import { theme, persistTheme } from '$lib/stores/theme';

	let settings = $state<AppSettings | null>(null);
	let version = $state<VersionInfo | null>(null);
	let checkingUpdates = $state(false);
	let updatingNow = $state(false);
	let updateError = $state<string | null>(null);
	let updateCheckedOnce = $state(false);
	let insecureOriginInfo = $state<InsecureOriginInfo | null>(null);
	let aiModelInput = $state('');
	let aiReasoningEffortInput = $state('');
	let aiAgentNameInput = $state('');
	let searxngUrlInput = $state('');
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
	let tmdbKeyInput = $state('');
	let aaKeyInput = $state('');
	let discordTokenInput = $state('');
	let icloudCredentials = $state<IcloudCredentials>({ username: '', has_password: false });
	let icloudUsernameInput = $state('');
	let icloudPasswordInput = $state('');
	let openaiSttEnabledInput = $state(false);
	let openaiSttModelInput = $state('whisper-1');
	let openaiTtsEnabledInput = $state(false);
	let openaiTtsModelInput = $state('');
	let piperTtsEnabledInput = $state(false);
	let piperServerUrlInput = $state('');
	let piperVoicesInput = $state('');
	let timezoneOptions = $state<string[]>(['UTC']);
	let error = $state<string | null>(null);

	// Each admin-settings section below (AI provider, voice input, voice output, TMDB, Discord, Google/MS
	// calendar, CalDAV, timezone) saves independently — see save*() functions
	// below — rather than sharing one big PATCH, so editing one doesn't
	// silently resubmit unrelated fields (e.g. API keys) from another. iCloud
	// Photos credentials are a personal (tier 2) setting, not admin-gated —
	// see CONTRIBUTING.md's Settings tiers — so they save independently too,
	// against /api/icloud/credentials rather than /api/settings.
	let aiProviderSaving = $state(false);
	let aiProviderSaved = $state(false);
	let aiProviderError = $state<string | null>(null);

	let voiceInputSaving = $state(false);
	let voiceInputSaved = $state(false);
	let voiceInputError = $state<string | null>(null);

	let voiceOutputSaving = $state(false);
	let voiceOutputSaved = $state(false);
	let voiceOutputError = $state<string | null>(null);

	let tmdbSaving = $state(false);
	let tmdbSaved = $state(false);
	let tmdbError = $state<string | null>(null);

	let aaSaving = $state(false);
	let aaSaved = $state(false);
	let aaError = $state<string | null>(null);

	let discordSaving = $state(false);
	let discordSaved = $state(false);
	let discordError = $state<string | null>(null);

	let googleCalendarSaving = $state(false);
	let googleCalendarSaved = $state(false);
	let googleCalendarError = $state<string | null>(null);

	let microsoftCalendarSaving = $state(false);
	let microsoftCalendarSaved = $state(false);
	let microsoftCalendarError = $state<string | null>(null);

	let caldavSaving = $state(false);
	let caldavSaved = $state(false);
	let caldavError = $state<string | null>(null);

	let icloudSaving = $state(false);
	let icloudSaved = $state(false);
	let icloudError = $state<string | null>(null);

	let timezoneSaving = $state(false);
	let timezoneSaved = $state(false);
	let timezoneError = $state<string | null>(null);

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

	// iCloud Photos credentials are a personal (tier 2) setting — any
	// logged-in user, not just admins, so this loads on $user the same way
	// profileInitialized above does, independent of settingsInitialized below.
	let icloudInitialized = false;

	$effect(() => {
		if ($user && !icloudInitialized) {
			icloudInitialized = true;
			loadIcloudCredentials();
		}
	});

	async function loadIcloudCredentials() {
		try {
			icloudCredentials = await api.icloudCredentials();
			icloudUsernameInput = icloudCredentials.username;
		} catch {
			icloudError = get(_)('settings.icloud.load_error');
		}
	}

	// /api/settings is admin-only — load it lazily once $user is known to be
	// an admin, mirroring profileInitialized above, so a member never fires a
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
			aiAgentNameInput = settings.ai_agent_name;
			searxngUrlInput = settings.searxng_url;
			timezoneInput = settings.timezone;
			caldavUrlInput = settings.caldav_url;
			caldavUsernameInput = settings.caldav_username;
			openaiSttEnabledInput = settings.openai_stt_enabled === 'true';
			openaiSttModelInput = settings.openai_stt_model || 'whisper-1';
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

	// Network integrations (Pi-hole, Jellyfin, Synology, Asus router,
	// HDHomeRun, container hosts) — same admin-only load-gate pattern as
	// loadSettings()/loadHouseholdUsers() above, since /api/network-settings
	// writes (and this page's reads) are admin-only.
	let piholeSettings = $state<Record<string, unknown>>({});
	let piholeHostInput = $state('');
	let piholePortInput = $state(80);
	let piholeUseHttpsInput = $state(false);
	let piholePasswordInput = $state('');
	let piholeSaving = $state(false);
	let piholeError = $state<string | null>(null);
	let piholeTesting = $state(false);
	let piholeTestResult = $state<NetworkTestConnectionResult | null>(null);

	let jellyfinSettings = $state<Record<string, unknown>>({});
	let jellyfinHostInput = $state('');
	let jellyfinPortInput = $state(8096);
	let jellyfinUseHttpsInput = $state(false);
	let jellyfinAuthModeInput = $state<'api_key' | 'password'>('api_key');
	let jellyfinApiKeyInput = $state('');
	let jellyfinUsernameInput = $state('');
	let jellyfinPasswordInput = $state('');
	let jellyfinSaving = $state(false);
	let jellyfinError = $state<string | null>(null);
	let jellyfinTesting = $state(false);
	let jellyfinTestResult = $state<NetworkTestConnectionResult | null>(null);

	let synologySettings = $state<Record<string, unknown>>({});
	let synologyHostInput = $state('');
	let synologyPortInput = $state(5000);
	let synologyUseHttpsInput = $state(false);
	let synologyUsernameInput = $state('');
	let synologyPasswordInput = $state('');
	let synologySaving = $state(false);
	let synologyError = $state<string | null>(null);
	let synologyTesting = $state(false);
	let synologyTestResult = $state<NetworkTestConnectionResult | null>(null);

	let asusSettings = $state<Record<string, unknown>>({});
	let asusHostInput = $state('');
	let asusSshPortInput = $state(22);
	let asusUsernameInput = $state('');
	let asusPasswordInput = $state('');
	let asusSaving = $state(false);
	let asusError = $state<string | null>(null);
	let asusTesting = $state(false);
	let asusTestResult = $state<NetworkTestConnectionResult | null>(null);

	let hdhomerunSettings = $state<Record<string, unknown>>({});
	let hdhomerunTunerHostInput = $state('');
	let hdhomerunTunerPortInput = $state(80);
	let hdhomerunDvrHostInput = $state('');
	let hdhomerunDvrPortInput = $state(59090);
	let hdhomerunEpgUrlInput = $state('');
	let hdhomerunSaving = $state(false);
	let hdhomerunError = $state<string | null>(null);
	let hdhomerunTestingTuner = $state(false);
	let hdhomerunTunerTestResult = $state<NetworkTestConnectionResult | null>(null);
	let hdhomerunTestingDvr = $state(false);
	let hdhomerunDvrTestResult = $state<NetworkTestConnectionResult | null>(null);

	let containerHosts = $state<NetworkIntegration[]>([]);
	let addHostNameInput = $state('');
	let addHostEngineInput = $state<'docker' | 'podman'>('docker');
	let addingHost = $state(false);
	let addHostError = $state<string | null>(null);

	let networkInitialized = false;

	$effect(() => {
		if ($user?.role === 'admin' && !networkInitialized) {
			networkInitialized = true;
			loadNetworkIntegrations();
		}
	});

	async function loadNetworkIntegrations() {
		try {
			const rows = await api.listNetworkIntegrations();

			const pihole = rows.find((r) => r.type === 'pihole');
			piholeSettings = pihole?.settings ?? {};
			piholeHostInput = (piholeSettings.host as string) ?? '';
			piholePortInput = (piholeSettings.port as number) ?? 80;
			piholeUseHttpsInput = (piholeSettings.use_https as boolean) ?? false;

			const jellyfin = rows.find((r) => r.type === 'jellyfin');
			jellyfinSettings = jellyfin?.settings ?? {};
			jellyfinHostInput = (jellyfinSettings.host as string) ?? '';
			jellyfinPortInput = (jellyfinSettings.port as number) ?? 8096;
			jellyfinUseHttpsInput = (jellyfinSettings.use_https as boolean) ?? false;
			jellyfinAuthModeInput = (jellyfinSettings.auth_mode as 'api_key' | 'password') ?? 'api_key';
			jellyfinUsernameInput = (jellyfinSettings.username as string) ?? '';

			const synology = rows.find((r) => r.type === 'synology');
			synologySettings = synology?.settings ?? {};
			synologyHostInput = (synologySettings.host as string) ?? '';
			synologyPortInput = (synologySettings.port as number) ?? 5000;
			synologyUseHttpsInput = (synologySettings.use_https as boolean) ?? false;
			synologyUsernameInput = (synologySettings.username as string) ?? '';

			const asus = rows.find((r) => r.type === 'asus_router');
			asusSettings = asus?.settings ?? {};
			asusHostInput = (asusSettings.host as string) ?? '';
			asusSshPortInput = (asusSettings.ssh_port as number) ?? 22;
			asusUsernameInput = (asusSettings.username as string) ?? '';

			const hdhomerun = rows.find((r) => r.type === 'hdhomerun');
			hdhomerunSettings = hdhomerun?.settings ?? {};
			hdhomerunTunerHostInput = (hdhomerunSettings.tuner_host as string) ?? '';
			hdhomerunTunerPortInput = (hdhomerunSettings.tuner_port as number) ?? 80;
			hdhomerunDvrHostInput = (hdhomerunSettings.dvr_host as string) ?? '';
			hdhomerunDvrPortInput = (hdhomerunSettings.dvr_port as number) ?? 59090;
			hdhomerunEpgUrlInput = (hdhomerunSettings.epg_url as string) ?? '';

			containerHosts = rows.filter((r) => r.type === 'container');
		} catch {
			error = 'Could not load network settings.';
		}
	}

	function piholeFormSettings(): Record<string, unknown> {
		const settings: Record<string, unknown> = {
			host: piholeHostInput,
			port: piholePortInput,
			use_https: piholeUseHttpsInput,
		};
		if (piholePasswordInput) settings.password = piholePasswordInput;
		return settings;
	}

	async function testPihole() {
		piholeTesting = true;
		piholeTestResult = null;
		try {
			piholeTestResult = await api.testNetworkIntegrationConnection('pihole', piholeFormSettings());
		} catch {
			piholeTestResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			piholeTesting = false;
		}
	}

	async function savePihole() {
		piholeSaving = true;
		piholeError = null;
		try {
			const updated = await api.updateNetworkIntegration('pihole', piholeFormSettings());
			piholeSettings = updated.settings;
			piholePasswordInput = '';
		} catch {
			piholeError = get(_)('network_settings.save_error');
		} finally {
			piholeSaving = false;
		}
	}

	function jellyfinFormSettings(): Record<string, unknown> {
		const settings: Record<string, unknown> = {
			host: jellyfinHostInput,
			port: jellyfinPortInput,
			use_https: jellyfinUseHttpsInput,
			auth_mode: jellyfinAuthModeInput,
			username: jellyfinUsernameInput,
		};
		if (jellyfinApiKeyInput) settings.api_key = jellyfinApiKeyInput;
		if (jellyfinPasswordInput) settings.password = jellyfinPasswordInput;
		return settings;
	}

	async function testJellyfin() {
		jellyfinTesting = true;
		jellyfinTestResult = null;
		try {
			jellyfinTestResult = await api.testNetworkIntegrationConnection('jellyfin', jellyfinFormSettings());
		} catch {
			jellyfinTestResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			jellyfinTesting = false;
		}
	}

	async function saveJellyfin() {
		jellyfinSaving = true;
		jellyfinError = null;
		try {
			const updated = await api.updateNetworkIntegration('jellyfin', jellyfinFormSettings());
			jellyfinSettings = updated.settings;
			jellyfinApiKeyInput = '';
			jellyfinPasswordInput = '';
		} catch {
			jellyfinError = get(_)('network_settings.save_error');
		} finally {
			jellyfinSaving = false;
		}
	}

	function synologyFormSettings(): Record<string, unknown> {
		const settings: Record<string, unknown> = {
			host: synologyHostInput,
			port: synologyPortInput,
			use_https: synologyUseHttpsInput,
			username: synologyUsernameInput,
		};
		if (synologyPasswordInput) settings.password = synologyPasswordInput;
		return settings;
	}

	async function testSynology() {
		synologyTesting = true;
		synologyTestResult = null;
		try {
			synologyTestResult = await api.testNetworkIntegrationConnection('synology', synologyFormSettings());
		} catch {
			synologyTestResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			synologyTesting = false;
		}
	}

	async function saveSynology() {
		synologySaving = true;
		synologyError = null;
		try {
			const updated = await api.updateNetworkIntegration('synology', synologyFormSettings());
			synologySettings = updated.settings;
			synologyPasswordInput = '';
		} catch {
			synologyError = get(_)('network_settings.save_error');
		} finally {
			synologySaving = false;
		}
	}

	function asusFormSettings(): Record<string, unknown> {
		const settings: Record<string, unknown> = {
			host: asusHostInput,
			ssh_port: asusSshPortInput,
			username: asusUsernameInput,
		};
		if (asusPasswordInput) settings.password = asusPasswordInput;
		return settings;
	}

	async function testAsus() {
		asusTesting = true;
		asusTestResult = null;
		try {
			asusTestResult = await api.testNetworkIntegrationConnection('asus_router', asusFormSettings());
		} catch {
			asusTestResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			asusTesting = false;
		}
	}

	async function saveAsus() {
		asusSaving = true;
		asusError = null;
		try {
			const updated = await api.updateNetworkIntegration('asus_router', asusFormSettings());
			asusSettings = updated.settings;
			asusPasswordInput = '';
		} catch {
			asusError = get(_)('network_settings.save_error');
		} finally {
			asusSaving = false;
		}
	}

	function hdhomerunFormSettings(): Record<string, unknown> {
		return {
			tuner_host: hdhomerunTunerHostInput,
			tuner_port: hdhomerunTunerPortInput,
			dvr_host: hdhomerunDvrHostInput,
			dvr_port: hdhomerunDvrPortInput,
			epg_url: hdhomerunEpgUrlInput,
		};
	}

	async function testHdhomerunTuner() {
		hdhomerunTestingTuner = true;
		hdhomerunTunerTestResult = null;
		try {
			hdhomerunTunerTestResult = await api.testHDHomeRunTunerConnection(hdhomerunFormSettings());
		} catch {
			hdhomerunTunerTestResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			hdhomerunTestingTuner = false;
		}
	}

	async function testHdhomerunDvr() {
		hdhomerunTestingDvr = true;
		hdhomerunDvrTestResult = null;
		try {
			hdhomerunDvrTestResult = await api.testHDHomeRunDvrConnection(hdhomerunFormSettings());
		} catch {
			hdhomerunDvrTestResult = { ok: false, detail: null, error: get(_)('common.backend_unreachable') };
		} finally {
			hdhomerunTestingDvr = false;
		}
	}

	async function saveHdhomerun() {
		hdhomerunSaving = true;
		hdhomerunError = null;
		try {
			const updated = await api.updateNetworkIntegration('hdhomerun', hdhomerunFormSettings());
			hdhomerunSettings = updated.settings;
		} catch {
			hdhomerunError = get(_)('network_settings.save_error');
		} finally {
			hdhomerunSaving = false;
		}
	}

	async function addHost() {
		if (!addHostNameInput.trim()) return;
		addingHost = true;
		addHostError = null;
		try {
			const defaults =
				addHostEngineInput === 'docker'
					? { engine: 'docker', connection: 'socket', socket_path: '/var/run/docker.sock', host: '', port: 2375 }
					: { engine: 'podman', connection: 'socket', socket_path: '/run/podman/podman.sock', host: '', port: 8080 };
			const created = await api.createContainerIntegration(addHostNameInput.trim(), defaults);
			containerHosts = [...containerHosts, created];
			addHostNameInput = '';
		} catch {
			addHostError = get(_)('network_settings.add_host_error');
		} finally {
			addingHost = false;
		}
	}

	function onHostUpdated(updated: NetworkIntegration) {
		containerHosts = containerHosts.map((h) => (h.id === updated.id ? updated : h));
	}

	function onHostDeleted(id: string) {
		containerHosts = containerHosts.filter((h) => h.id !== id);
	}

	// Listing every device and forgetting one requires admin on the backend
	// (devices have no per-user ownership column); a non-admin can still
	// rename their own device via $currentDevice below.
	const isAdmin = $derived($user?.role === 'admin');

	let devices = $state<DeviceListEntry[]>([]);
	let devicesError = $state<string | null>(null);
	let deviceNameInput = $state('');
	let savingDeviceName = $state(false);
	let editingDeviceName = $state(false);
	let confirmingForgetDeviceId = $state<string | null>(null);
	let forgettingDeviceId = $state<string | null>(null);

	function startEditingDeviceName() {
		deviceNameInput = $currentDevice?.name ?? '';
		devicesError = null;
		editingDeviceName = true;
	}

	function cancelEditingDeviceName() {
		editingDeviceName = false;
		deviceNameInput = $currentDevice?.name ?? '';
		devicesError = null;
	}

	async function loadDevices() {
		if (!isAdmin) return;
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

	// Fallback matches the backend's default set; refreshed from /api/theme
	// on mount so new themes show up without a frontend redeploy.
	let themeIds = $state(['light', 'dark', 'sepia', 'contrast', 'forest', 'ocean']);
	let themeNames = $state<Record<string, string>>({});

	// Widget types that make for a good screensaver slide by default — only
	// used to pre-check a sensible starting selection the first time a user
	// enables the screensaver with nothing chosen yet; never persisted unless
	// they hit Save.
	const SCREENSAVER_FRIENDLY_TYPES = ['clock', 'ai', 'discord', 'message', 'photos', 'artificial_analysis'];

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

	function previewSingleScreensaver(widgetId: string) {
		forceScreensaverPreview.set({
			enabled: true,
			idle_timeout_seconds: ssIdleTimeoutInput,
			rotation_interval_seconds: ssRotationIntervalInput,
			widget_ids: [widgetId],
			text_animation_style: ssTextAnimationStyle,
			led_color: ssLedColor,
			text_pause_seconds: ssTextPauseInput,
			flipboard_pattern: ssFlipboardPattern,
		});
	}

	function previewAllScreensavers() {
		const ids = ssSelectedIds.size > 0 ? Array.from(ssSelectedIds) : screensaverEligibleWidgets.map((w) => w.id);
		forceScreensaverPreview.set({
			enabled: true,
			idle_timeout_seconds: ssIdleTimeoutInput,
			rotation_interval_seconds: ssRotationIntervalInput,
			widget_ids: ids,
			text_animation_style: ssTextAnimationStyle,
			led_color: ssLedColor,
			text_pause_seconds: ssTextPauseInput,
			flipboard_pattern: ssFlipboardPattern,
		});
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
	let alwaysOnMicInput = $state(false);
	let voiceInitialized = false;

	// Language and theme both apply live to the DOM the instant the store is
	// set (see stores/theme.ts and $lib/i18n) — that live-preview stays, but
	// the server write (persistLocale/persistTheme) waits for Save like every
	// other section on this page, rather than firing on every selection.
	let localeSaving = $state(false);
	let localeSaved = $state(false);
	let localeError = $state<string | null>(null);

	// Optional location the AI assistant can use for location-aware answers.
	// Search stages a pending selection; Save/Clear persist it, matching
	// every other section on this page rather than auto-saving on click.
	let locationQuery = $state('');
	let locationResults = $state<CityResult[]>([]);
	let locationSearching = $state(false);
	let locationPending = $state<LocationPreference | null>(null);
	let locationSaving = $state(false);
	let locationSaved = $state(false);
	let locationError = $state<string | null>(null);
	let locationInitialized = false;
	let locationSearchTimeout: ReturnType<typeof setTimeout>;

	let themeSaving = $state(false);
	let themeSaved = $state(false);
	let themeError = $state<string | null>(null);

	async function saveLocale() {
		localeSaving = true;
		localeError = null;
		try {
			await persistLocale($locale ?? 'en');
			localeSaved = true;
		} catch {
			localeError = get(_)('settings.language.save_error');
		} finally {
			localeSaving = false;
		}
	}

	function onLocationQueryInput() {
		clearTimeout(locationSearchTimeout);
		const trimmed = locationQuery.trim();
		if (trimmed.length < 2) {
			locationResults = [];
			locationSearching = false;
			return;
		}
		locationSearching = true;
		locationSearchTimeout = setTimeout(async () => {
			try {
				locationResults = await api.searchCities(trimmed);
				locationError = null;
			} catch {
				locationError = get(_)('settings.location.search_failed');
			} finally {
				locationSearching = false;
			}
		}, 300);
	}

	function locationCityLabel(city: CityResult): string {
		const region = city.admin1 ?? city.country ?? '';
		return region ? `${city.name}, ${region}` : city.name;
	}

	function selectLocation(city: CityResult) {
		locationPending = {
			query: locationQuery.trim(),
			display_name: locationCityLabel(city),
			latitude: city.latitude,
			longitude: city.longitude,
		};
		locationSaved = false;
		locationQuery = '';
		locationResults = [];
	}

	async function saveLocation() {
		locationSaving = true;
		locationError = null;
		try {
			await persistLocation(locationPending);
			locationSaved = true;
		} catch {
			locationError = get(_)('settings.location.save_error');
		} finally {
			locationSaving = false;
		}
	}

	async function clearLocation() {
		locationSaving = true;
		locationError = null;
		try {
			await persistLocation(null);
			locationPending = null;
			locationSaved = true;
		} catch {
			locationError = get(_)('settings.location.save_error');
		} finally {
			locationSaving = false;
		}
	}

	async function saveTheme() {
		themeSaving = true;
		themeError = null;
		try {
			await persistTheme($theme);
			themeSaved = true;
		} catch {
			themeError = get(_)('settings.appearance.save_error');
		} finally {
			themeSaving = false;
		}
	}

	$effect(() => {
		if ($user && !voiceInitialized) {
			voiceInitialized = true;
			loadVoiceSelectionFromServer().then(() => {
				voiceProviderInput = $voiceSelection.provider;
				voiceIdInput = $voiceSelection.voiceId;
			});
			loadAlwaysOnMicFromServer().then(() => {
				alwaysOnMicInput = $alwaysOnMic;
			});
		}
	});

	$effect(() => {
		if ($user && !locationInitialized) {
			locationInitialized = true;
			loadLocationFromServer().then(() => {
				locationPending = $userLocation;
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
			await persistAlwaysOnMic(alwaysOnMicInput);
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

	async function saveAiProvider() {
		aiProviderSaving = true;
		aiProviderSaved = false;
		aiProviderError = null;

		const trimmedSearxngUrl = searxngUrlInput.trim();
		if (trimmedSearxngUrl && !/^https?:\/\//i.test(trimmedSearxngUrl)) {
			aiProviderError = 'SearXNG URL must start with http:// or https://';
			aiProviderSaving = false;
			return;
		}

		try {
			const partial: Record<string, string> = {
				ai_model: aiModelInput,
				ai_reasoning_effort: aiReasoningEffortInput,
				ai_agent_name: aiAgentNameInput,
				searxng_url: trimmedSearxngUrl,
			};
			if (anthropicKeyInput) partial.anthropic_api_key = anthropicKeyInput;
			if (openaiKeyInput) partial.openai_api_key = openaiKeyInput;
			if (geminiKeyInput) partial.gemini_api_key = geminiKeyInput;

			settings = await api.updateSettings(partial);
			if (settings?.ai_agent_name) {
				agentName.set(settings.ai_agent_name.trim() || 'Tilora');
			}
			anthropicKeyInput = '';
			openaiKeyInput = '';
			geminiKeyInput = '';
			aiProviderSaved = true;
		} catch (err: unknown) {
			aiProviderError = err instanceof Error ? err.message : 'Could not save AI provider settings.';
		} finally {
			aiProviderSaving = false;
		}
	}

	async function saveVoiceInput() {
		voiceInputSaving = true;
		voiceInputSaved = false;
		voiceInputError = null;
		try {
			settings = await api.updateSettings({
				openai_stt_enabled: openaiSttEnabledInput ? 'true' : '',
				openai_stt_model: openaiSttModelInput,
			});
			voiceInputSaved = true;
			await loadAssistantConfigFromServer();
		} catch {
			voiceInputError = 'Could not save voice input settings.';
		} finally {
			voiceInputSaving = false;
		}
	}

	async function saveVoiceOutput() {
		voiceOutputSaving = true;
		voiceOutputSaved = false;
		voiceOutputError = null;
		try {
			settings = await api.updateSettings({
				openai_tts_enabled: openaiTtsEnabledInput ? 'true' : '',
				openai_tts_model: openaiTtsModelInput,
				piper_tts_enabled: piperTtsEnabledInput ? 'true' : '',
				piper_server_url: piperServerUrlInput,
				piper_voices: piperVoicesInput,
			});
			voiceOutputSaved = true;
		} catch {
			voiceOutputError = 'Could not save voice output settings.';
		} finally {
			voiceOutputSaving = false;
		}
	}

	async function saveTmdb() {
		tmdbSaving = true;
		tmdbSaved = false;
		tmdbError = null;
		try {
			const partial: Record<string, string> = {};
			if (tmdbKeyInput) partial.tmdb_api_key = tmdbKeyInput;
			settings = await api.updateSettings(partial);
			tmdbKeyInput = '';
			tmdbSaved = true;
		} catch {
			tmdbError = 'Could not save TMDB settings.';
		} finally {
			tmdbSaving = false;
		}
	}

	async function saveArtificialAnalysis() {
		aaSaving = true;
		aaSaved = false;
		aaError = null;
		try {
			const partial: Record<string, string> = {};
			if (aaKeyInput) partial.artificial_analysis_api_key = aaKeyInput;
			settings = await api.updateSettings(partial);
			aaKeyInput = '';
			aaSaved = true;
		} catch {
			aaError = 'Could not save Artificial Analysis settings.';
		} finally {
			aaSaving = false;
		}
	}

	async function saveDiscord() {
		discordSaving = true;
		discordSaved = false;
		discordError = null;
		try {
			const partial: Record<string, string> = {};
			if (discordTokenInput) partial.discord_bot_token = discordTokenInput;
			settings = await api.updateSettings(partial);
			discordTokenInput = '';
			discordSaved = true;
		} catch {
			discordError = 'Could not save Discord settings.';
		} finally {
			discordSaving = false;
		}
	}

	async function saveGoogleCalendar() {
		googleCalendarSaving = true;
		googleCalendarSaved = false;
		googleCalendarError = null;
		try {
			const partial: Record<string, string> = {};
			if (googleCalendarClientIdInput) partial.google_calendar_client_id = googleCalendarClientIdInput;
			if (googleCalendarClientSecretInput) partial.google_calendar_client_secret = googleCalendarClientSecretInput;
			settings = await api.updateSettings(partial);
			googleCalendarClientIdInput = '';
			googleCalendarClientSecretInput = '';
			googleCalendarSaved = true;
		} catch {
			googleCalendarError = 'Could not save Google Calendar settings.';
		} finally {
			googleCalendarSaving = false;
		}
	}

	async function saveMicrosoftCalendar() {
		microsoftCalendarSaving = true;
		microsoftCalendarSaved = false;
		microsoftCalendarError = null;
		try {
			const partial: Record<string, string> = {};
			if (microsoftCalendarClientIdInput) partial.microsoft_calendar_client_id = microsoftCalendarClientIdInput;
			if (microsoftCalendarClientSecretInput)
				partial.microsoft_calendar_client_secret = microsoftCalendarClientSecretInput;
			settings = await api.updateSettings(partial);
			microsoftCalendarClientIdInput = '';
			microsoftCalendarClientSecretInput = '';
			microsoftCalendarSaved = true;
		} catch {
			microsoftCalendarError = 'Could not save Microsoft 365 Calendar settings.';
		} finally {
			microsoftCalendarSaving = false;
		}
	}

	async function saveCaldav() {
		caldavSaving = true;
		caldavSaved = false;
		caldavError = null;
		try {
			const partial: Record<string, string> = {
				caldav_url: caldavUrlInput,
				caldav_username: caldavUsernameInput,
			};
			if (caldavPasswordInput) partial.caldav_password = caldavPasswordInput;
			settings = await api.updateSettings(partial);
			caldavPasswordInput = '';
			caldavSaved = true;
		} catch {
			caldavError = 'Could not save CalDAV settings.';
		} finally {
			caldavSaving = false;
		}
	}

	async function saveIcloud() {
		icloudSaving = true;
		icloudSaved = false;
		icloudError = null;
		try {
			icloudCredentials = await api.setIcloudCredentials(icloudUsernameInput, icloudPasswordInput || undefined);
			icloudPasswordInput = '';
			icloudSaved = true;
		} catch {
			icloudError = get(_)('settings.icloud.save_error');
		} finally {
			icloudSaving = false;
		}
	}

	async function clearIcloudCredentials() {
		icloudError = null;
		try {
			await api.clearIcloudCredentials();
			icloudCredentials = { username: '', has_password: false };
			icloudUsernameInput = '';
		} catch {
			icloudError = get(_)('settings.icloud.clear_error');
		}
	}

	async function saveTimezone() {
		timezoneSaving = true;
		timezoneSaved = false;
		timezoneError = null;
		try {
			settings = await api.updateSettings({ timezone: timezoneInput });
			timezoneSaved = true;
		} catch {
			timezoneError = 'Could not save timezone.';
		} finally {
			timezoneSaving = false;
		}
	}

	async function clearKey(
		key:
			| 'anthropic_api_key'
			| 'openai_api_key'
			| 'gemini_api_key'
			| 'tmdb_api_key'
			| 'artificial_analysis_api_key'
			| 'discord_bot_token'
			| 'google_calendar_client_id'
			| 'google_calendar_client_secret'
			| 'microsoft_calendar_client_id'
			| 'microsoft_calendar_client_secret'
			| 'caldav_password',
		onError: (message: string) => void,
	) {
		onError('');
		try {
			settings = await api.updateSettings({ [key]: '' });
		} catch {
			onError('Could not clear the key.');
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
		const trimmed = deviceNameInput.trim();
		if (!trimmed) {
			devicesError = get(_)('settings.devices.empty_name_error');
			return;
		}
		if (trimmed.length > 40) {
			devicesError = get(_)('settings.devices.rename_error');
			return;
		}
		if (trimmed === $currentDevice?.name) {
			editingDeviceName = false;
			return;
		}
		if (devices.some((d) => d.id !== $currentDevice?.id && d.name.trim().toLowerCase() === trimmed.toLowerCase())) {
			devicesError = get(_)('settings.devices.duplicate_name_error');
			return;
		}

		savingDeviceName = true;
		devicesError = null;
		try {
			await renameCurrentDevice(trimmed);
			// renameCurrentDevice already updates $currentDevice; only admins
			// can reload the full list (used to spot duplicate names below).
			await loadDevices();
			editingDeviceName = false;
		} catch (err: unknown) {
			if (err instanceof Error && err.message) {
				devicesError = err.message;
			} else {
				devicesError = get(_)('settings.devices.rename_error');
			}
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

	async function checkForUpdates() {
		checkingUpdates = true;
		try {
			version = await api.version();
			updateCheckedOnce = true;
		} catch {
			// keep existing version data
		} finally {
			checkingUpdates = false;
		}
	}

	async function pollUntilHealthy(maxAttempts = 30, intervalMs = 3000): Promise<void> {
		for (let i = 0; i < maxAttempts; i++) {
			await new Promise<void>((r) => setTimeout(r, intervalMs));
			try {
				await api.health();
				return;
			} catch {
				// still restarting
			}
		}
	}

	async function triggerUpdate() {
		updatingNow = true;
		updateError = null;
		try {
			await api.triggerUpdate();
		} catch {
			// A network error here is expected — the backend restarts itself
			// right after accepting the request, which drops the connection.
		}
		// Poll /api/health until the backend comes back (up to ~90 s).
		await pollUntilHealthy();
		try {
			version = await api.version();
		} catch {
			// best effort — version panel will refresh on next manual check
		}
		updatingNow = false;
	}
</script>

<div class="settings-page">
	<div class="settings-header">
		<button class="back" onclick={() => goto('/')}>{$_('common.back')}</button>
		<a
			href="https://andyg-0.github.io/tilora/"
			target="_blank"
			rel="noreferrer"
			class="help-link"
			aria-label={$_('settings.help_documentation')}
		>
			<svg
				viewBox="0 0 24 24"
				width="16"
				height="16"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<circle cx="12" cy="12" r="10" />
				<path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
				<line x1="12" y1="17" x2="12.01" y2="17" />
			</svg>
			<span>{$_('settings.help_documentation')}</span>
		</a>
	</div>
	<h1>{$_('settings.page.title')}</h1>

	{#if $user?.role === 'admin'}
		<div class="settings-group">
			<h2 class="group-title">Admin settings</h2>
			<p class="group-subtitle">Shared across the whole household — visible only to admins.</p>

			<div class="settings-grid">
				{#if !settings}
					<p class="hint grid-span-all">{error ?? 'Loading…'}</p>
				{:else}
					<section>
						<h3>AI provider</h3>
						<label>
							Agent name
							<input type="text" bind:value={aiAgentNameInput} placeholder="Tilora" />
						</label>
						<p class="hint">The name the AI assistant uses to identify itself when answering questions.</p>

						<label>
							Model
							<input type="text" bind:value={aiModelInput} placeholder="anthropic/claude-sonnet-5" />
						</label>
						<p class="hint">
							Follows litellm's "&lt;provider&gt;/&lt;model&gt;" convention, e.g. anthropic/claude-sonnet-5,
							openai/gpt-5, or gemini/gemini-2.5-flash.
						</p>

						<label>
							SearXNG URL (web search)
							<input type="text" bind:value={searxngUrlInput} placeholder="http://searxng:8080" />
						</label>
						<p class="hint">
							Optional. URL of a self-hosted SearXNG instance. When configured, enables live web search and page
							fetching tools for the AI assistant.
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
							{$_('settings.ai.reasoning_hint')}
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
							<button class="clear" onclick={() => clearKey('anthropic_api_key', (m) => (aiProviderError = m))}
								>Clear key</button
							>
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
							<button class="clear" onclick={() => clearKey('openai_api_key', (m) => (aiProviderError = m))}
								>Clear key</button
							>
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
							<button class="clear" onclick={() => clearKey('gemini_api_key', (m) => (aiProviderError = m))}
								>Clear key</button
							>
						{/if}

						{#if aiProviderError}
							<p class="hint error">{aiProviderError}</p>
						{/if}
						{#if aiProviderSaved}
							<p class="hint">Saved.</p>
						{/if}
						<button class="save" disabled={aiProviderSaving} onclick={saveAiProvider}>
							{aiProviderSaving ? 'Saving…' : 'Save AI provider'}
						</button>
					</section>

					<section>
						<h3>Google Calendar</h3>
						<label>
							Client ID
							<input
								type="password"
								bind:value={googleCalendarClientIdInput}
								placeholder={settings.has_google_calendar_client_id
									? 'Set — enter a new value to replace it'
									: 'Not set'}
							/>
						</label>
						{#if settings.has_google_calendar_client_id}
							<button
								class="clear"
								onclick={() => clearKey('google_calendar_client_id', (m) => (googleCalendarError = m))}
								>Clear client ID</button
							>
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
							<button
								class="clear"
								onclick={() => clearKey('google_calendar_client_secret', (m) => (googleCalendarError = m))}
							>
								Clear client secret
							</button>
						{/if}
						<p class="hint">
							{$_('settings.google_calendar.hint')}
							<a href="https://andyg-0.github.io/tilora/admin-guide/calendar-oauth/" target="_blank" rel="noreferrer"
								>{$_('settings.docs_guide_link')}</a
							>.
						</p>

						{#if googleCalendarError}
							<p class="hint error">{googleCalendarError}</p>
						{/if}
						{#if googleCalendarSaved}
							<p class="hint">Saved.</p>
						{/if}
						<button class="save" disabled={googleCalendarSaving} onclick={saveGoogleCalendar}>
							{googleCalendarSaving ? 'Saving…' : 'Save Google Calendar'}
						</button>
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
							<button
								class="clear"
								onclick={() => clearKey('microsoft_calendar_client_id', (m) => (microsoftCalendarError = m))}
							>
								Clear client ID
							</button>
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
							<button
								class="clear"
								onclick={() => clearKey('microsoft_calendar_client_secret', (m) => (microsoftCalendarError = m))}
							>
								Clear client secret
							</button>
						{/if}
						<p class="hint">
							{$_('settings.microsoft_calendar.hint')}
							<a href="https://andyg-0.github.io/tilora/admin-guide/calendar-oauth/" target="_blank" rel="noreferrer"
								>{$_('settings.docs_guide_link')}</a
							>.
						</p>

						{#if microsoftCalendarError}
							<p class="hint error">{microsoftCalendarError}</p>
						{/if}
						{#if microsoftCalendarSaved}
							<p class="hint">Saved.</p>
						{/if}
						<button class="save" disabled={microsoftCalendarSaving} onclick={saveMicrosoftCalendar}>
							{microsoftCalendarSaving ? 'Saving…' : 'Save Microsoft 365 Calendar'}
						</button>
					</section>

					<section>
						<h3>Voice output</h3>
						<p class="hint">
							{$_('settings.voice_output.hint')}
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

						{#if voiceOutputError}
							<p class="hint error">{voiceOutputError}</p>
						{/if}
						{#if voiceOutputSaved}
							<p class="hint">Saved.</p>
						{/if}
						<button class="save" disabled={voiceOutputSaving} onclick={saveVoiceOutput}>
							{voiceOutputSaving ? 'Saving…' : 'Save voice output'}
						</button>
					</section>

					<section>
						<h3>{$_('network_settings.section_container')}</h3>

						{#if containerHosts.length === 0}
							<p class="hint">{$_('network_settings.no_container_hosts')}</p>
						{:else}
							<div class="host-list">
								{#each containerHosts as host (host.id)}
									<ContainerHostRow {host} onUpdated={onHostUpdated} onDeleted={onHostDeleted} />
								{/each}
							</div>
						{/if}

						<div class="add-host">
							<h4>{$_('network_settings.add_host_heading')}</h4>
							<label>
								{$_('network_settings.host_name_label')}
								<input
									type="text"
									bind:value={addHostNameInput}
									placeholder={$_('network_settings.host_name_placeholder')}
								/>
							</label>
							<label>
								{$_('container.detail.engine_label')}
								<select bind:value={addHostEngineInput}>
									<option value="docker">Docker</option>
									<option value="podman">Podman</option>
								</select>
							</label>
							{#if addHostError}
								<p class="hint error">{addHostError}</p>
							{/if}
							<button class="save" disabled={addingHost || !addHostNameInput.trim()} onclick={addHost}>
								{addingHost ? $_('common.saving') : $_('network_settings.add_host_button')}
							</button>
						</div>
					</section>

					<section>
						<h3>{$_('network_settings.section_synology')}</h3>
						<label>
							{$_('synology.detail.host_label')}
							<input type="text" bind:value={synologyHostInput} placeholder="synology.local" />
						</label>
						<label>
							{$_('synology.detail.port_label')}
							<input type="number" min="1" max="65535" bind:value={synologyPortInput} />
						</label>
						<label class="checkbox">
							<input type="checkbox" bind:checked={synologyUseHttpsInput} />
							{$_('synology.detail.use_https_label')}
						</label>
						<label>
							{$_('synology.detail.username_label')}
							<input type="text" bind:value={synologyUsernameInput} placeholder="admin" />
						</label>
						<label>
							{$_('synology.detail.password_label')}
							<input
								type="password"
								bind:value={synologyPasswordInput}
								placeholder={synologySettings.has_password
									? $_('common.password_set_hint')
									: $_('common.password_not_set')}
							/>
						</label>

						<div class="test-row">
							<button class="test" disabled={synologyTesting} onclick={testSynology}>
								{synologyTesting ? $_('common.testing') : $_('common.test_connection')}
							</button>
							{#if synologyTestResult}
								{#if synologyTestResult.ok}
									<span class="test-result ok"
										>{$_('network_settings.test_ok', { values: { detail: synologyTestResult.detail } })}</span
									>
								{:else}
									<span class="test-result fail"
										>{$_('network_settings.test_fail', { values: { error: synologyTestResult.error } })}</span
									>
								{/if}
							{/if}
						</div>

						{#if synologyError}
							<p class="hint error">{synologyError}</p>
						{/if}

						<button class="save" disabled={synologySaving} onclick={saveSynology}>
							{synologySaving ? $_('common.saving') : $_('common.save')}
						</button>
					</section>

					<section>
						<h3>{$_('network_settings.section_asus_router')}</h3>
						<label>
							{$_('asus_router.detail.host_label')}
							<input type="text" bind:value={asusHostInput} placeholder="router.asus.com" />
						</label>
						<label>
							{$_('asus_router.detail.ssh_port_label')}
							<input type="number" min="1" max="65535" bind:value={asusSshPortInput} />
						</label>
						<label>
							{$_('asus_router.detail.username_label')}
							<input type="text" bind:value={asusUsernameInput} placeholder="admin" />
						</label>
						<label>
							{$_('asus_router.detail.password_label')}
							<input
								type="password"
								bind:value={asusPasswordInput}
								placeholder={asusSettings.has_password ? $_('common.password_set_hint') : $_('common.password_not_set')}
							/>
						</label>

						<div class="test-row">
							<button class="test" disabled={asusTesting} onclick={testAsus}>
								{asusTesting ? $_('common.testing') : $_('common.test_connection')}
							</button>
							{#if asusTestResult}
								{#if asusTestResult.ok}
									<span class="test-result ok"
										>{$_('network_settings.test_ok', { values: { detail: asusTestResult.detail } })}</span
									>
								{:else}
									<span class="test-result fail"
										>{$_('network_settings.test_fail', { values: { error: asusTestResult.error } })}</span
									>
								{/if}
							{/if}
						</div>

						{#if asusError}
							<p class="hint error">{asusError}</p>
						{/if}

						<button class="save" disabled={asusSaving} onclick={saveAsus}>
							{asusSaving ? $_('common.saving') : $_('common.save')}
						</button>
					</section>

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
												<button
													class="clear"
													onclick={() => toggleRole(member)}
													disabled={updatingRoleId === member.id}
												>
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
							<button class="clear" onclick={() => clearKey('caldav_password', (m) => (caldavError = m))}
								>Clear password</button
							>
						{/if}
						<p class="hint">
							Works with iCloud, Fastmail, Nextcloud, and most self-hosted calendars — usually an app-specific password
							rather than your account password. Set a calendar widget's
							<code>provider</code> to <code>caldav</code> in <code>dashboard.yaml</code> to use it.
						</p>

						{#if caldavError}
							<p class="hint error">{caldavError}</p>
						{/if}
						{#if caldavSaved}
							<p class="hint">Saved.</p>
						{/if}
						<button class="save" disabled={caldavSaving} onclick={saveCaldav}>
							{caldavSaving ? 'Saving…' : 'Save CalDAV'}
						</button>
					</section>

					<section>
						<h3>Voice input (Speech recognition)</h3>
						<p class="hint">
							Open-source Chromium (e.g. Raspberry Pi kiosk, Chromium on Mac/Linux), Firefox, and Brave lack built-in
							Google Speech recognition API keys. Enable OpenAI Whisper to allow these browsers to record and transcribe
							speech via Cloud STT.
						</p>

						<label class="checkbox-label">
							<input type="checkbox" bind:checked={openaiSttEnabledInput} />
							Enable OpenAI Whisper speech-to-text (Cloud STT)
						</label>
						{#if openaiSttEnabledInput}
							<label>
								Whisper model
								<input type="text" bind:value={openaiSttModelInput} placeholder="whisper-1" />
							</label>
							<p class="hint">Uses the OpenAI API key configured above (~$0.006/min of recorded speech).</p>
						{/if}

						{#if voiceInputError}
							<p class="hint error">{voiceInputError}</p>
						{/if}
						{#if voiceInputSaved}
							<p class="hint">Saved.</p>
						{/if}
						<button class="save" disabled={voiceInputSaving} onclick={saveVoiceInput}>
							{voiceInputSaving ? 'Saving…' : 'Save voice input'}
						</button>
					</section>

					<section>
						<h3>{$_('network_settings.section_pihole')}</h3>
						<label>
							{$_('pihole.detail.host_label')}
							<input type="text" bind:value={piholeHostInput} placeholder="pi.hole" />
						</label>
						<label>
							{$_('pihole.detail.port_label')}
							<input type="number" min="1" max="65535" bind:value={piholePortInput} />
						</label>
						<label class="checkbox">
							<input type="checkbox" bind:checked={piholeUseHttpsInput} />
							{$_('pihole.detail.use_https_label')}
						</label>
						<label>
							{$_('pihole.detail.password_label')}
							<input
								type="password"
								bind:value={piholePasswordInput}
								placeholder={piholeSettings.has_password
									? $_('common.password_set_hint')
									: $_('common.password_not_set')}
							/>
						</label>

						<div class="test-row">
							<button class="test" disabled={piholeTesting} onclick={testPihole}>
								{piholeTesting ? $_('common.testing') : $_('common.test_connection')}
							</button>
							{#if piholeTestResult}
								{#if piholeTestResult.ok}
									<span class="test-result ok"
										>{$_('network_settings.test_ok', { values: { detail: piholeTestResult.detail } })}</span
									>
								{:else}
									<span class="test-result fail"
										>{$_('network_settings.test_fail', { values: { error: piholeTestResult.error } })}</span
									>
								{/if}
							{/if}
						</div>

						{#if piholeError}
							<p class="hint error">{piholeError}</p>
						{/if}

						<button class="save" disabled={piholeSaving} onclick={savePihole}>
							{piholeSaving ? $_('common.saving') : $_('common.save')}
						</button>
					</section>

					<section>
						<h3>{$_('network_settings.section_jellyfin')}</h3>
						<label>
							{$_('jellyfin.detail.host_label')}
							<input type="text" bind:value={jellyfinHostInput} placeholder="jellyfin.local" />
						</label>
						<label>
							{$_('jellyfin.detail.port_label')}
							<input type="number" min="1" max="65535" bind:value={jellyfinPortInput} />
						</label>
						<label class="checkbox">
							<input type="checkbox" bind:checked={jellyfinUseHttpsInput} />
							{$_('jellyfin.detail.use_https_label')}
						</label>

						<div class="auth-mode">
							<button
								type="button"
								class:active={jellyfinAuthModeInput === 'api_key'}
								onclick={() => (jellyfinAuthModeInput = 'api_key')}
							>
								{$_('jellyfin.detail.auth_mode_api_key')}
							</button>
							<button
								type="button"
								class:active={jellyfinAuthModeInput === 'password'}
								onclick={() => (jellyfinAuthModeInput = 'password')}
							>
								{$_('jellyfin.detail.auth_mode_password')}
							</button>
						</div>

						{#if jellyfinAuthModeInput === 'api_key'}
							<label>
								{$_('jellyfin.detail.auth_mode_api_key')}
								<input
									type="password"
									bind:value={jellyfinApiKeyInput}
									placeholder={jellyfinSettings.has_api_key
										? $_('common.password_set_hint')
										: $_('common.password_not_set')}
								/>
							</label>
						{:else}
							<label>
								{$_('jellyfin.detail.username_label')}
								<input type="text" bind:value={jellyfinUsernameInput} />
							</label>
							<label>
								{$_('jellyfin.detail.password_label')}
								<input
									type="password"
									bind:value={jellyfinPasswordInput}
									placeholder={jellyfinSettings.has_password
										? $_('common.password_set_hint')
										: $_('common.password_not_set')}
								/>
							</label>
						{/if}

						<div class="test-row">
							<button class="test" disabled={jellyfinTesting} onclick={testJellyfin}>
								{jellyfinTesting ? $_('common.testing') : $_('common.test_connection')}
							</button>
							{#if jellyfinTestResult}
								{#if jellyfinTestResult.ok}
									<span class="test-result ok"
										>{$_('network_settings.test_ok', { values: { detail: jellyfinTestResult.detail } })}</span
									>
								{:else}
									<span class="test-result fail"
										>{$_('network_settings.test_fail', { values: { error: jellyfinTestResult.error } })}</span
									>
								{/if}
							{/if}
						</div>

						{#if jellyfinError}
							<p class="hint error">{jellyfinError}</p>
						{/if}

						<button class="save" disabled={jellyfinSaving} onclick={saveJellyfin}>
							{jellyfinSaving ? $_('common.saving') : $_('common.save')}
						</button>
					</section>

					<section>
						<h3>{$_('network_settings.section_hdhomerun')}</h3>
						<h4>{$_('hdhomerun.detail.tuner_heading')}</h4>
						<label>
							{$_('hdhomerun.detail.host_label')}
							<input type="text" bind:value={hdhomerunTunerHostInput} placeholder="hdhomerun.local" />
						</label>
						<label>
							{$_('hdhomerun.detail.port_label')}
							<input type="number" min="1" max="65535" bind:value={hdhomerunTunerPortInput} />
						</label>
						<div class="test-row">
							<button class="test" disabled={hdhomerunTestingTuner} onclick={testHdhomerunTuner}>
								{hdhomerunTestingTuner ? $_('common.testing') : $_('common.test_connection')}
							</button>
							{#if hdhomerunTunerTestResult}
								{#if hdhomerunTunerTestResult.ok}
									<span class="test-result ok"
										>{$_('network_settings.test_ok', { values: { detail: hdhomerunTunerTestResult.detail } })}</span
									>
								{:else}
									<span class="test-result fail"
										>{$_('network_settings.test_fail', { values: { error: hdhomerunTunerTestResult.error } })}</span
									>
								{/if}
							{/if}
						</div>

						<h4>
							{$_('hdhomerun.detail.guide_heading')} <span class="optional">{$_('hdhomerun.detail.optional')}</span>
						</h4>
						<label>
							{$_('hdhomerun.detail.xmltv_url_label')}
							<input type="text" bind:value={hdhomerunEpgUrlInput} placeholder="http://example.com/guide.xml" />
						</label>
						<p class="hint">{$_('hdhomerun.detail.xmltv_hint')}</p>

						<h4>
							{$_('hdhomerun.detail.dvr_settings_heading')}
							<span class="optional">{$_('hdhomerun.detail.optional')}</span>
						</h4>
						<label>
							{$_('hdhomerun.detail.host_label')}
							<input type="text" bind:value={hdhomerunDvrHostInput} placeholder="dvr.local" />
						</label>
						<label>
							{$_('hdhomerun.detail.port_label')}
							<input type="number" min="1" max="65535" bind:value={hdhomerunDvrPortInput} />
						</label>
						<div class="test-row">
							<button class="test" disabled={hdhomerunTestingDvr} onclick={testHdhomerunDvr}>
								{hdhomerunTestingDvr ? $_('common.testing') : $_('common.test_connection')}
							</button>
							{#if hdhomerunDvrTestResult}
								{#if hdhomerunDvrTestResult.ok}
									<span class="test-result ok"
										>{$_('network_settings.test_ok', { values: { detail: hdhomerunDvrTestResult.detail } })}</span
									>
								{:else}
									<span class="test-result fail"
										>{$_('network_settings.test_fail', { values: { error: hdhomerunDvrTestResult.error } })}</span
									>
								{/if}
							{/if}
						</div>

						{#if hdhomerunError}
							<p class="hint error">{hdhomerunError}</p>
						{/if}

						<button class="save" disabled={hdhomerunSaving} onclick={saveHdhomerun}>
							{hdhomerunSaving ? $_('common.saving') : $_('common.save')}
						</button>
					</section>

					<section>
						<h3>Discord</h3>
						<label>
							Bot token
							<input
								type="password"
								bind:value={discordTokenInput}
								placeholder={settings.has_discord_bot_token ? 'Set — enter a new value to replace it' : 'Not set'}
							/>
						</label>
						{#if settings.has_discord_bot_token}
							<button class="clear" onclick={() => clearKey('discord_bot_token', (m) => (discordError = m))}>
								Clear bot token
							</button>
						{/if}
						<p class="hint">
							Used by the Discord widget (discord.com/developers/applications). Requires a bot token for a bot invited
							to your server.
						</p>

						{#if discordError}
							<p class="hint error">{discordError}</p>
						{/if}
						{#if discordSaved}
							<p class="hint">Saved.</p>
						{/if}
						<button class="save" disabled={discordSaving} onclick={saveDiscord}>
							{discordSaving ? 'Saving…' : 'Save Discord'}
						</button>
					</section>

					<section>
						<h3>The Movie Database (TMDB)</h3>
						<label>
							API key
							<input
								type="password"
								bind:value={tmdbKeyInput}
								placeholder={settings.has_tmdb_api_key ? 'Set — enter a new value to replace it' : 'Not set'}
							/>
						</label>
						{#if settings.has_tmdb_api_key}
							<button class="clear" onclick={() => clearKey('tmdb_api_key', (m) => (tmdbError = m))}>
								Clear API key
							</button>
						{/if}
						<p class="hint">
							Used by the Movies &amp; Shows widget (themoviedb.org/settings/api). Enter your TMDB v3 API key.
						</p>

						{#if tmdbError}
							<p class="hint error">{tmdbError}</p>
						{/if}
						{#if tmdbSaved}
							<p class="hint">Saved.</p>
						{/if}
						<button class="save" disabled={tmdbSaving} onclick={saveTmdb}>
							{tmdbSaving ? 'Saving…' : 'Save TMDB'}
						</button>
					</section>

					<section>
						<h3>Artificial Analysis</h3>
						<label>
							API key
							<input
								type="password"
								bind:value={aaKeyInput}
								placeholder={settings.has_artificial_analysis_api_key
									? 'Set — enter a new value to replace it'
									: 'Not set'}
							/>
						</label>
						{#if settings.has_artificial_analysis_api_key}
							<button class="clear" onclick={() => clearKey('artificial_analysis_api_key', (m) => (aaError = m))}>
								Clear API key
							</button>
						{/if}
						<p class="hint">
							Used by the Artificial Analysis widget (artificialanalysis.ai/data-api) for AI model
							coding/intelligence/cost/speed leaderboards. Enter your free-tier API key.
						</p>

						{#if aaError}
							<p class="hint error">{aaError}</p>
						{/if}
						{#if aaSaved}
							<p class="hint">Saved.</p>
						{/if}
						<button class="save" disabled={aaSaving} onclick={saveArtificialAnalysis}>
							{aaSaving ? 'Saving…' : 'Save Artificial Analysis'}
						</button>
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

						{#if timezoneError}
							<p class="hint error">{timezoneError}</p>
						{/if}
						{#if timezoneSaved}
							<p class="hint">Saved.</p>
						{/if}
						<button class="save" disabled={timezoneSaving} onclick={saveTimezone}>
							{timezoneSaving ? 'Saving…' : 'Save timezone'}
						</button>
					</section>
				{/if}
			</div>
		</div>
	{/if}

	<div class="settings-group">
		<h2 class="group-title">{$_('settings.your_settings.title')}</h2>
		<p class="group-subtitle">{$_('settings.your_settings.subtitle')}</p>

		<div class="settings-grid">
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
								<li class="widget-picker-item">
									<label class="checkbox-label">
										<input
											type="checkbox"
											checked={ssSelectedIds.has(w.id)}
											onchange={() => toggleScreensaverWidget(w.id)}
										/>
										<span>{w.name}</span>
									</label>
									<button
										type="button"
										class="action-link"
										onclick={() => previewSingleScreensaver(w.id)}
										aria-label={$_('settings.screensaver.test_widget_aria', { values: { name: w.name } })}
									>
										{$_('settings.screensaver.test_single')}
									</button>
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
					<button class="clear" disabled={screensaverEligibleWidgets.length === 0} onclick={previewAllScreensavers}>
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

				<label class="checkbox-label" style="margin-top: 1rem;">
					<input
						type="checkbox"
						bind:checked={alwaysOnMicInput}
						onchange={(e) => {
							if (e.currentTarget.checked) void ensureMicrophonePermission();
						}}
					/>
					{$_('settings.voice.always_on_mic_label')}
				</label>
				<p class="hint">
					{$_('settings.voice.always_on_mic_hint', { values: { agentName: $agentName } })}
				</p>

				{#if voiceError}
					<p class="hint error">{voiceError}</p>
				{/if}
				{#if voiceSaved}
					<p class="hint">{$_('common.saved')}</p>
				{/if}
				<button class="save" disabled={voiceSaving} onclick={saveVoiceSelection}>
					{voiceSaving ? $_('common.saving') : $_('settings.voice.save')}
				</button>
			</section>

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
				<div class="profile-actions">
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
				</div>
			</section>

			<section>
				<h3>{$_('settings.devices.heading')}</h3>

				{#if devicesError}
					<p class="hint error">{devicesError}</p>
				{/if}

				<ul class="device-list">
					<li>
						{#if editingDeviceName}
							<form
								class="device-rename-form"
								onsubmit={(e) => {
									e.preventDefault();
									saveDeviceName();
								}}
							>
								<input
									type="text"
									bind:value={deviceNameInput}
									maxlength="40"
									aria-label={$_('settings.devices.rename')}
									disabled={savingDeviceName}
									onkeydown={(e) => {
										if (e.key === 'Escape') cancelEditingDeviceName();
									}}
								/>
								<span class="confirm-actions">
									<button type="button" class="cancel" onclick={cancelEditingDeviceName} disabled={savingDeviceName}>
										{$_('common.cancel')}
									</button>
									<button type="submit" class="save" disabled={savingDeviceName || !deviceNameInput.trim()}>
										{savingDeviceName ? $_('common.saving') : $_('common.save')}
									</button>
								</span>
							</form>
						{:else}
							<span class="device-info">
								<span class="device-name">{$currentDevice?.name}</span>
								<span class="device-badge">{$_('settings.devices.this_device_badge')}</span>
							</span>
							<span class="device-actions">
								<button type="button" class="action-link" onclick={startEditingDeviceName}>
									{$_('settings.devices.rename_device')}
								</button>
							</span>
						{/if}
					</li>
					{#if isAdmin}
						{#each devices.filter((d) => d.id !== $currentDevice?.id) as d (d.id)}
							<li>
								<span class="device-info">
									<span class="device-name">{d.name}</span>
								</span>
								<span class="device-actions">
									{#if confirmingForgetDeviceId === d.id}
										<span class="confirm-actions">
											<button
												type="button"
												class="cancel"
												onclick={() => (confirmingForgetDeviceId = null)}
												disabled={forgettingDeviceId === d.id}
											>
												{$_('common.cancel')}
											</button>
											<button
												type="button"
												class="danger"
												onclick={() => forgetDevice(d.id)}
												disabled={forgettingDeviceId === d.id}
											>
												{forgettingDeviceId === d.id
													? $_('settings.devices.forgetting')
													: $_('settings.devices.forget')}
											</button>
										</span>
									{:else}
										<button type="button" class="danger-link" onclick={() => (confirmingForgetDeviceId = d.id)}>
											{$_('settings.devices.forget_device')}
										</button>
									{/if}
								</span>
							</li>
						{/each}
					{/if}
				</ul>
			</section>

			<section>
				<h3>{$_('settings.location.heading')}</h3>
				{#if locationPending}
					<p class="hint">{$_('settings.location.current')}: {locationPending.display_name}</p>
				{/if}
				<div class="city-search">
					<input
						type="text"
						placeholder={$_('settings.location.search_placeholder')}
						bind:value={locationQuery}
						oninput={onLocationQueryInput}
					/>
					{#if locationSearching}
						<p class="hint">{$_('settings.location.searching')}</p>
					{:else if locationError}
						<p class="hint error">{locationError}</p>
					{:else if locationQuery.trim().length >= 2 && locationResults.length === 0}
						<p class="hint">{$_('settings.location.no_results')}</p>
					{/if}
					{#if locationResults.length > 0}
						<ul class="results">
							{#each locationResults as city (city.latitude + ',' + city.longitude)}
								<li>
									<button disabled={locationSaving} onclick={() => selectLocation(city)}>
										{locationCityLabel(city)}
									</button>
								</li>
							{/each}
						</ul>
					{/if}
				</div>

				{#if locationSaved}
					<p class="hint">{$_('common.saved')}</p>
				{/if}
				<div class="button-row">
					<button class="save" disabled={locationSaving} onclick={saveLocation}>
						{locationSaving ? $_('common.saving') : $_('settings.location.save')}
					</button>
					<button class="clear" disabled={locationSaving || !locationPending} onclick={clearLocation}>
						{$_('settings.location.clear')}
					</button>
				</div>
			</section>

			<section>
				<h3>{$_('settings.icloud.heading')}</h3>

				<label>
					{$_('settings.icloud.apple_id_label')}
					<input type="text" bind:value={icloudUsernameInput} />
				</label>

				<label>
					{$_('settings.icloud.password_label')}
					<input
						type="password"
						bind:value={icloudPasswordInput}
						placeholder={icloudCredentials.has_password
							? $_('common.password_set_hint')
							: $_('common.password_not_set')}
					/>
				</label>
				{#if icloudCredentials.has_password}
					<button class="clear" onclick={clearIcloudCredentials}>{$_('settings.icloud.clear')}</button>
				{/if}
				<p class="hint">
					{$_('settings.icloud.hint_prefix')}<strong>{$_('photos.detail.provider_icloud_private')}</strong>{$_(
						'settings.icloud.hint_suffix',
					)}
				</p>

				{#if icloudError}
					<p class="hint error">{icloudError}</p>
				{/if}
				{#if icloudSaved}
					<p class="hint">{$_('common.saved')}</p>
				{/if}
				<button class="save" disabled={icloudSaving} onclick={saveIcloud}>
					{icloudSaving ? $_('common.saving') : $_('settings.icloud.save')}
				</button>
			</section>

			<section>
				<h3>{$_('pwa.install_title')}</h3>
				<p class="hint">{$_('pwa.install_description')}</p>

				<div class="pwa-settings-content">
					<div class="pwa-status-row">
						<span class="pwa-status-label">{$_('settings.devices.status_label', { default: 'Status' })}</span>
						{#if $pwaState.isStandalone}
							<span class="device-badge pwa-badge-installed">{$_('pwa.installed_badge')}</span>
						{:else}
							<span class="device-badge pwa-badge-browser">{$_('pwa.running_in_browser')}</span>
						{/if}
					</div>

					{#if $pwaState.canInstall}
						<div class="pwa-install-action">
							<button type="button" class="action-btn" onclick={promptInstall}>
								{$_('pwa.install_app')}
							</button>
						</div>
					{:else if !$pwaState.isStandalone}
						<p class="hint pwa-help-hint">
							{$_('pwa.ios_install_hint')}
						</p>
					{/if}
				</div>
			</section>

			<section>
				<h3>{$_('settings.language.title')}</h3>
				<select
					aria-label={$_('settings.language.title')}
					value={$locale}
					onchange={(e) => {
						locale.set(e.currentTarget.value);
						localeSaved = false;
					}}
				>
					<option value="en">English</option>
					<option value="es">Español</option>
					<option value="fr">Français</option>
					<option value="de">Deutsch</option>
				</select>

				{#if localeError}
					<p class="hint error">{localeError}</p>
				{/if}
				{#if localeSaved}
					<p class="hint">{$_('common.saved')}</p>
				{/if}
				<button class="save" disabled={localeSaving} onclick={saveLocale}>
					{localeSaving ? $_('common.saving') : $_('settings.language.save')}
				</button>
			</section>

			<section>
				<h3>{$_('settings.appearance.title')}</h3>
				<select
					aria-label={$_('settings.appearance.title')}
					value={$theme}
					onchange={(e) => {
						theme.set(e.currentTarget.value);
						themeSaved = false;
					}}
				>
					{#each themeIds as id (id)}
						<option value={id}>{themeNames[id] ?? id}</option>
					{/each}
				</select>

				{#if themeError}
					<p class="hint error">{themeError}</p>
				{/if}
				{#if themeSaved}
					<p class="hint">{$_('common.saved')}</p>
				{/if}
				<button class="save" disabled={themeSaving} onclick={saveTheme}>
					{themeSaving ? $_('common.saving') : $_('settings.appearance.save')}
				</button>
			</section>

			<section>
				<h3>{$_('reports.title')}</h3>
				<p class="hint">{$_('reports.subtitle')}</p>
				<button class="clear reports-nav-btn" onclick={() => goto('/reports')}>
					<svg
						viewBox="0 0 24 24"
						width="16"
						height="16"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
					>
						<line x1="18" y1="20" x2="18" y2="10" />
						<line x1="12" y1="20" x2="12" y2="4" />
						<line x1="6" y1="20" x2="6" y2="14" />
					</svg>
					<span>{$_('reports.nav_report_button')}</span>
				</button>
			</section>

			{#if insecureOriginInfo?.needsInsecureOriginFlag}
				<section class="microphone-section">
					<h3>{$_('settings.microphone.heading')}</h3>
					{#if insecureOriginInfo.browser === 'chrome'}
						<p class="hint">
							{$_('settings.microphone.chrome_intro', { values: { origin: insecureOriginInfo.origin } })}
						</p>
						<p class="hint">
							{$_('settings.microphone.open_prefix')}
							<a href="chrome://flags/#unsafely-treat-insecure-origin-as-secure" target="_blank" rel="noreferrer"
								>chrome://flags/#unsafely-treat-insecure-origin-as-secure</a
							>{$_('settings.microphone.after_link')} <code>{insecureOriginInfo.origin}</code>
							{$_('settings.microphone.chrome_list_suffix')}
						</p>
					{:else if insecureOriginInfo.browser === 'chromium'}
						<p class="hint">
							{$_('settings.microphone.chromium_intro', { values: { origin: insecureOriginInfo.origin } })}
						</p>
						<p class="hint">
							{$_('settings.microphone.open_prefix')}
							<a href="chrome://flags/#unsafely-treat-insecure-origin-as-secure" target="_blank" rel="noreferrer"
								>chrome://flags/#unsafely-treat-insecure-origin-as-secure</a
							>{$_('settings.microphone.after_link')} <code>{insecureOriginInfo.origin}</code>
							{$_('settings.microphone.chrome_list_suffix')}
						</p>
					{:else if insecureOriginInfo.browser === 'edge'}
						<p class="hint">
							{$_('settings.microphone.edge_intro', { values: { origin: insecureOriginInfo.origin } })}
						</p>
						<p class="hint">
							{$_('settings.microphone.open_prefix')}
							<a href="edge://flags/#unsafely-treat-insecure-origin-as-secure" target="_blank" rel="noreferrer"
								>edge://flags/#unsafely-treat-insecure-origin-as-secure</a
							>{$_('settings.microphone.after_link')} <code>{insecureOriginInfo.origin}</code>
							{$_('settings.microphone.edge_list_suffix')}
						</p>
					{:else if insecureOriginInfo.browser === 'brave'}
						<p class="hint">
							{$_('settings.microphone.brave_intro', { values: { origin: insecureOriginInfo.origin } })}
						</p>
						<p class="hint">
							{$_('settings.microphone.open_prefix')}
							<a href="brave://flags/#unsafely-treat-insecure-origin-as-secure" target="_blank" rel="noreferrer"
								>brave://flags/#unsafely-treat-insecure-origin-as-secure</a
							>{$_('settings.microphone.after_link')} <code>{insecureOriginInfo.origin}</code>
							{$_('settings.microphone.brave_list_suffix')}
						</p>
					{:else if insecureOriginInfo.browser === 'firefox'}
						<p class="hint">
							{$_('settings.microphone.firefox_intro')}
						</p>
					{:else if insecureOriginInfo.browser === 'safari'}
						<p class="hint">
							{$_('settings.microphone.safari_intro', { values: { origin: insecureOriginInfo.origin } })}
						</p>
						<p class="hint">
							{$_('settings.microphone.safari_https_req')}
						</p>
						<div class="cert-tips">
							<p class="hint cert-tip-heading">
								<strong>{$_('settings.microphone.safari_cert_tip_title')}</strong>
							</p>
							<ul class="cert-tips-list">
								<li>{$_('settings.microphone.safari_ios_cert_tip')}</li>
								<li>{$_('settings.microphone.safari_mac_cert_tip')}</li>
							</ul>
						</div>
					{:else}
						<p class="hint">
							{$_('settings.microphone.other_intro', { values: { origin: insecureOriginInfo.origin } })}
						</p>
						<p class="hint">
							{$_('settings.microphone.other_https_req')}
						</p>
					{/if}
				</section>
			{/if}

			{#if version}
				<section>
					<h3>{$_('settings.update.heading')}</h3>
					<p class="hint">{$_('settings.update.running_version', { values: { version: version.current_version } })}</p>

					<div class="update-check-row">
						<button
							id="check-for-updates-btn"
							class="secondary"
							onclick={checkForUpdates}
							disabled={checkingUpdates || updatingNow}
						>
							{checkingUpdates ? $_('settings.update.checking') : $_('settings.update.check_now')}
						</button>
						{#if version.update_available}
							<span class="update-badge-inline"
								>{$_('settings.update.available', { values: { version: version.latest_version } })}</span
							>
						{:else if updateCheckedOnce && !checkingUpdates}
							<span class="hint">{$_('settings.update.up_to_date')}</span>
						{/if}
					</div>

					{#if version.update_available && version.release_url}
						<p class="hint">
							<a href={version.release_url} target="_blank" rel="noreferrer">{$_('settings.update.view_release')}</a>
						</p>
					{/if}

					{#if version.install_method === 'native' && $user?.role === 'admin'}
						{#if version.update_running || updatingNow}
							<p class="hint">{$_('settings.update.update_in_progress')}</p>
						{:else if version.update_available}
							<button id="update-now-btn" class="save" onclick={triggerUpdate} disabled={updatingNow}>
								{$_('settings.update.update_now')}
							</button>
							{#if updateError}
								<p class="hint error">{updateError}</p>
							{/if}
						{/if}
					{/if}
				</section>
			{/if}
		</div>
	</div>
</div>

<style>
	.settings-page {
		padding: 1.5rem 1rem 4rem;
		min-height: 100vh;
		max-width: 1280px;
		width: 100%;
		margin: 0 auto;
	}

	@media (min-width: 640px) {
		.settings-page {
			padding: 2rem 1.5rem 4rem;
		}
	}

	@media (min-width: 1024px) {
		.settings-page {
			padding: 2.5rem 2rem 5rem;
		}
	}

	.settings-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 1.25rem;
		align-items: stretch;
	}

	@media (min-width: 700px) {
		.settings-grid {
			grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
			gap: 1.25rem;
		}
	}

	@media (min-width: 1100px) {
		.settings-grid {
			grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
			gap: 1.5rem;
		}
	}

	.grid-span-all {
		grid-column: 1 / -1;
	}

	.update-check-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.update-badge-inline {
		font-size: 0.85rem;
		color: var(--color-accent);
		font-weight: 500;
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
		margin-bottom: 0;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1.25rem;
		height: 100%;
		box-sizing: border-box;
	}

	section > .save,
	section > .button-row,
	section > .update-check-row,
	section > .pwa-settings-content,
	section > .reports-nav-btn,
	section > .profile-actions {
		margin-top: auto;
	}

	.profile-actions {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	section h3 {
		margin: 0;
		font-size: 1rem;
	}

	section h4 {
		margin: 0.5rem 0 0;
		font-size: 0.9rem;
	}

	section h4:first-of-type {
		margin-top: 0;
	}

	.optional {
		font-weight: normal;
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	label.checkbox {
		flex-direction: row;
		align-items: center;
		gap: 0.5rem;
	}

	.auth-mode {
		display: flex;
		gap: 0.5rem;
	}

	.auth-mode button {
		flex: 1;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.auth-mode button.active {
		border-color: var(--color-accent);
		color: var(--color-accent);
	}

	.test-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.test,
	.secondary {
		align-self: flex-start;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.test-result {
		font-size: 0.85rem;
	}

	.test-result.ok {
		color: var(--color-success);
	}

	.test-result.fail {
		color: var(--color-error);
	}

	.host-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.add-host {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		border-top: 1px solid var(--color-border);
		padding-top: 1rem;
	}

	.add-host h4 {
		margin: 0;
		font-size: 0.9rem;
	}

	.settings-group {
		margin-bottom: 2.5rem;
	}

	.group-title {
		margin: 0 0 0.25rem;
		font-size: 1.25rem;
		font-weight: 600;
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

	.city-search {
		margin: 0.5rem 0;
	}

	.city-search input {
		width: 100%;
	}

	.results {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0;
		width: 100%;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.results button {
		width: 100%;
		text-align: left;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
		cursor: pointer;
	}

	.results button:active {
		background: var(--color-surface-hover);
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
	.test:disabled,
	.secondary:disabled,
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
		flex-wrap: wrap;
	}

	.device-info {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.device-name {
		font-size: 0.9rem;
	}

	.device-badge {
		font-size: 0.75rem;
		color: var(--color-accent);
		border: 1px solid var(--color-accent);
		border-radius: 999px;
		padding: 0.1rem 0.5rem;
		white-space: nowrap;
	}

	.device-actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.device-rename-form {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		flex-wrap: wrap;
	}

	.device-rename-form input {
		flex: 1;
		min-width: 150px;
	}

	.action-link {
		background: none;
		border: none;
		color: var(--color-accent);
		text-decoration: underline;
		cursor: pointer;
		padding: 0;
		font-size: 0.85rem;
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

	.widget-picker-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.cert-tips {
		margin-top: 0.5rem;
		padding: 0.6rem 0.8rem;
		background: var(--color-surface-hover, rgba(255, 255, 255, 0.04));
		border: 1px solid var(--color-border);
		border-radius: 8px;
	}

	.cert-tip-heading {
		color: var(--color-text);
		font-size: 0.85rem;
		margin: 0;
	}

	.cert-tips-list {
		margin: 0.4rem 0 0;
		padding-left: 1.2rem;
		color: var(--color-text-muted);
		font-size: 0.85rem;
		line-height: 1.5;
	}

	.cert-tips-list li {
		margin-bottom: 0.25rem;
	}

	.reports-nav-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
	}

	.settings-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 0.5rem;
	}

	.help-link {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.85rem;
		color: var(--color-accent);
		text-decoration: none;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 999px;
		padding: 0.35rem 0.75rem;
		transition: all 0.15s ease;
	}

	.help-link:hover {
		background: var(--color-surface-hover);
		border-color: var(--color-accent);
	}

	.pwa-settings-content {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-top: 0.5rem;
	}

	.pwa-status-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.pwa-status-label {
		font-weight: 500;
		color: var(--color-text);
		font-size: 0.95rem;
	}

	.pwa-badge-installed {
		background: rgba(34, 197, 94, 0.15);
		color: #22c55e;
		border: 1px solid rgba(34, 197, 94, 0.3);
	}

	.pwa-badge-browser {
		background: rgba(148, 163, 184, 0.15);
		color: var(--color-text-muted);
		border: 1px solid var(--color-border);
	}

	.pwa-install-action {
		margin-top: 0.25rem;
	}

	.pwa-help-hint {
		margin-top: 0.25rem;
		font-size: 0.85rem;
		color: var(--color-text-muted);
		line-height: 1.4;
	}
</style>
