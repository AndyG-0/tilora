// Dynamic (not static) so the API base URL can be set as a runtime
// environment variable against the built Node server, rather than baked
// into the client bundle at Docker build time — lets frontend and backend
// run on different hosts without a rebuild.
import { env } from '$env/dynamic/public';

export interface WidgetLayout {
	col: number;
	row: number;
	colSpan: number;
	rowSpan: number;
}

export interface WidgetSummaryMeta {
	id: string;
	type: string;
	layout: WidgetLayout;
	tab: string;
}

export interface TabMeta {
	id: string;
	name: string;
}

export interface CityResult {
	name: string;
	admin1: string | null;
	country: string | null;
	latitude: number;
	longitude: number;
}

export interface AppSettings {
	ai_model: string;
	timezone: string;
	has_anthropic_api_key: boolean;
	has_openai_api_key: boolean;
	has_gemini_api_key: boolean;
	has_google_calendar_client_id: boolean;
	has_google_calendar_client_secret: boolean;
	has_microsoft_calendar_client_id: boolean;
	has_microsoft_calendar_client_secret: boolean;
	caldav_url: string;
	caldav_username: string;
	has_caldav_password: boolean;
	icloud_username: string;
	has_icloud_password: boolean;
}

export interface VersionInfo {
	current_version: string;
	latest_version: string | null;
	update_available: boolean;
	release_url: string | null;
}

export type AlertSeverity = 'info' | 'warning' | 'critical';

export interface Alert {
	id: number;
	widget_id: string;
	severity: AlertSeverity;
	message: string;
	created_at: string;
	expires_at: string | null;
	dismissed: boolean;
}

export interface CalendarStatus {
	connected: boolean;
}

export interface CaldavCalendar {
	id: string;
	name: string;
	color: string;
}

export interface IcloudStatus {
	connected: boolean;
}

export interface IcloudAuthStartResult {
	connected: boolean;
	requires_2fa: boolean;
}

export interface JellyfinItem {
	id: string;
	name: string;
	type: string;
	overview: string | null;
	year: number | null;
	is_folder: boolean;
	has_poster: boolean;
	runtime_minutes: number | null;
}

export interface JellyfinTestConnectionResult {
	ok: boolean;
	server_name: string | null;
	error: string | null;
}

export interface HDHomeRunGuideEntry {
	title: string;
	episode_title: string | null;
	start: number | null;
	end: number | null;
}

export interface HDHomeRunChannel {
	channel_number: string;
	name: string;
	is_hd: boolean;
	is_drm: boolean;
	stream_url: string;
	playback_url: string | null;
	now: HDHomeRunGuideEntry | null;
	next: HDHomeRunGuideEntry | null;
}

export interface HDHomeRunTuner {
	index: number;
	in_use: boolean;
	channel_number: string | null;
	channel_name: string | null;
	signal_strength_percent: number | null;
	signal_quality_percent: number | null;
	symbol_quality_percent: number | null;
	network_rate_bps: number | null;
}

export interface HDHomeRunRecording {
	title: string;
	channel_name: string | null;
	start: number | null;
	record_end: number | null;
}

export interface HDHomeRunTestConnectionResult {
	ok: boolean;
	name: string | null;
	error: string | null;
}

export interface PiholeDomainStat {
	domain: string;
	count: number;
}

export interface PiholeSummary {
	connected: boolean;
	host: string;
	port: number;
	use_https: boolean;
	has_password: boolean;
	blocking_enabled?: boolean;
	blocking_timer?: number | null;
	queries_today?: number;
	blocked_today?: number;
	percent_blocked?: number;
	error?: string;
}

export interface PiholeDetail extends PiholeSummary {
	unique_clients: number;
	clients_total: number;
	domains_blocked: number;
	gravity_last_update: number | null;
	top_blocked_domains: PiholeDomainStat[];
	top_permitted_domains: PiholeDomainStat[];
}

export interface PiholeTestConnectionResult {
	ok: boolean;
	version: string | null;
	error: string | null;
}

export interface SynologyVolumeSummary {
	name: string;
	used_percent: number;
	status: string;
}

export interface SynologyVolumeDetail extends SynologyVolumeSummary {
	total_bytes: number;
	used_bytes: number;
}

export interface SynologySummary {
	connected: boolean;
	host: string;
	port: number;
	use_https: boolean;
	username: string;
	has_password: boolean;
	volumes: SynologyVolumeSummary[];
	error?: string;
}

export interface SynologyDetail extends Omit<SynologySummary, 'volumes'> {
	volumes: SynologyVolumeDetail[];
	model: string | null;
	uptime: string | null;
	temperature_celsius: number | null;
}

export interface SynologyTestConnectionResult {
	ok: boolean;
	model: string | null;
	error: string | null;
}

export interface AsusRouterClient {
	name: string;
	ip: string;
	online: boolean;
}

export interface AsusRouterSummary {
	connected: boolean;
	wan_connected: boolean;
	client_count: number;
	host: string;
	port: number;
	use_https: boolean;
	username: string;
	has_password: boolean;
	error?: string;
}

export interface AsusRouterDetail extends AsusRouterSummary {
	wan_ip: string | null;
	clients: AsusRouterClient[];
	rx_bytes: number;
	tx_bytes: number;
}

export interface AsusRouterTestConnectionResult {
	ok: boolean;
	product_id: string | null;
	error: string | null;
}

export interface GoodreadsBookSummary {
	title: string;
	link: string;
	book_image_url: string;
	author_name: string;
}

export interface GoodreadsBookDetail extends GoodreadsBookSummary {
	isbn: string;
	average_rating: string;
	user_rating: string;
	user_date_added: string;
	user_read_at: string;
}

export interface GoodreadsSummary {
	shelf: string;
	books: GoodreadsBookSummary[];
}

export interface GoodreadsDetail {
	shelf: string;
	user_id: string;
	books: GoodreadsBookDetail[];
}

export interface SystemMonitorSummary {
	hostname: string;
	cpu_percent: number;
	memory_percent: number;
	disk_percent: number;
}

export interface SystemMonitorDetail extends SystemMonitorSummary {
	cpu_count: number;
	cpu_per_core: number[];
	memory_used_gb: number;
	memory_total_gb: number;
	disk_used_gb: number;
	disk_total_gb: number;
	network_sent_gb: number;
	network_recv_gb: number;
	uptime_seconds: number;
	load_average: [number, number, number];
}

export interface ContainerSummaryItem {
	name: string;
	state: string;
	status: string;
}

export interface ContainerDetailItem extends ContainerSummaryItem {
	id: string;
	image: string;
}

export interface ContainerSummary {
	engine: 'docker' | 'podman';
	connected: boolean;
	connection: string;
	socket_path: string;
	host: string;
	port: number;
	containers: ContainerSummaryItem[];
	running_count: number;
	stopped_count: number;
	total_count: number;
	error?: string;
}

export interface ContainerDetail extends Omit<ContainerSummary, 'containers'> {
	containers: ContainerDetailItem[];
}

export interface SportsBroadcastLink {
	name: string;
	url: string | null;
}

export interface SportsGame {
	id: string;
	date: string | null;
	state: string;
	completed: boolean;
	status_detail: string;
	home_team: string;
	home_abbreviation: string;
	away_team: string;
	away_abbreviation: string;
	home_score: string | null;
	away_score: string | null;
	broadcasts: string[];
	broadcast_links: SportsBroadcastLink[];
	venue: string | null;
	is_home: boolean;
	opponent: string;
}

export interface SportsSummaryGame extends SportsGame {
	league: string;
	league_label: string;
	team: string;
}

export interface SportsError {
	league: string;
	team: string;
	error: string;
}

export interface SportsTrendingError {
	league: string;
	error: string;
}

export interface SportsTrendingGame {
	id: string;
	league: string;
	league_label: string;
	date: string | null;
	state: string;
	completed: boolean;
	status_detail: string;
	home_team: string;
	home_abbreviation: string;
	home_rank: number | null;
	away_team: string;
	away_abbreviation: string;
	away_rank: number | null;
	home_score: string | null;
	away_score: string | null;
	broadcast_links: SportsBroadcastLink[];
	venue: string | null;
}

export interface SportsSummary {
	configured: boolean;
	games: SportsSummaryGame[];
	trending: SportsTrendingGame[];
	errors?: SportsError[];
	trending_errors?: SportsTrendingError[];
}

export interface SportsTeamEntry {
	league: string;
	team: string;
}

export interface SportsTeamDetail {
	league: string;
	league_label: string;
	team: string;
	team_name: string;
	games: SportsGame[];
	error?: string;
}

export interface SportsDetail {
	configured: boolean;
	teams: SportsTeamDetail[];
	trending: SportsTrendingGame[];
	trending_leagues: string[];
	trending_errors?: SportsTrendingError[];
}

export interface SportsTeamOption {
	abbreviation: string;
	display_name: string;
}

export interface SteamPlayer {
	steamid: string;
	name: string;
	avatar: string;
	status: string;
	online: boolean;
	current_game: string | null;
}

export interface SteamGame {
	appid: number;
	name: string;
	playtime_2weeks_minutes: number;
	playtime_forever_minutes: number;
	icon_url: string | null;
}

export type SteamFriend = SteamPlayer;

export interface SteamSummary {
	configured: boolean;
	player: SteamPlayer | null;
	current_game: string | null;
	recent_games: SteamGame[];
	steamid: string;
	has_api_key: boolean;
	error?: string;
}

export interface SteamDetail extends SteamSummary {
	friends: SteamFriend[];
}

export interface BF6Server {
	server_id: string;
	name: string;
	region: string;
	map: string;
	mode: string;
	player_count: number;
	max_players: number;
	owner_name: string | null;
}

export interface BF6PlayerStats {
	user_name: string;
	avatar: string | null;
	score: number;
	kills: number;
	deaths: number;
	wins: number;
	loses: number;
	assists: number;
	kill_death: number;
	win_percent: string | null;
	accuracy: string | null;
	headshots: string | null;
	kills_per_minute: number;
	kills_per_match: number;
	time_played: string | null;
	matches_played: number;
}

export interface BF6Summary {
	configured: boolean;
	server: BF6Server | null;
	player: BF6PlayerStats | null;
	server_name: string;
	player_name: string;
	platform: string;
	error?: string;
}

export type BF6Detail = BF6Summary;

export interface HDHomeRunTranscodePreset {
	id: string;
	label: string;
	description: string;
	input_args: string[];
	output_args: string[];
}

export interface DeviceInfo {
	id: string;
	name: string;
}

export interface DeviceListEntry extends DeviceInfo {
	last_seen_at: string;
}

export interface DeviceRegisterResult extends DeviceInfo {
	is_new: boolean;
}

export interface LayoutStatus {
	has_layout: boolean;
}

export interface UserProfile {
	id: string;
	name: string;
	avatar: string | null;
	has_pin: boolean;
}

export type UserRole = 'admin' | 'member';

export interface CurrentUser {
	id: string;
	name: string;
	avatar: string | null;
	role: UserRole;
}

export interface UserPreferences {
	theme: string;
}

export interface SetupStatus {
	needs_setup: boolean;
}

export interface HouseholdUser {
	id: string;
	name: string;
	avatar: string | null;
	has_pin: boolean;
	role: UserRole;
	created_at: string;
}

// fetch() itself throws a TypeError before ever reaching a response — that's
// the one reliable signal that the request never made it to the server (CORS
// block, DNS failure, connection refused), as opposed to a server response
// that just wasn't `ok`. Used to tell "backend unreachable" apart from
// "backend responded with an error" in first-run/login error messaging.
export type FetchErrorKind = 'network' | 'server';

export function describeFetchError(error: unknown): FetchErrorKind {
	return error instanceof TypeError ? 'network' : 'server';
}

// `credentials: 'include'` on every request so the device/session cookies
// (set by the backend as httponly, so JS can't attach them manually) round-trip
// even when the frontend and backend are on different ports/origins.
async function getJSON<T>(path: string): Promise<T> {
	const response = await fetch(`${env.PUBLIC_API_BASE_URL}${path}`, { credentials: 'include' });
	if (!response.ok) {
		throw new Error(`Request to ${path} failed: ${response.status}`);
	}
	return response.json();
}

async function patchJSON<T>(path: string, body: Record<string, unknown>): Promise<T> {
	const response = await fetch(`${env.PUBLIC_API_BASE_URL}${path}`, {
		method: 'PATCH',
		credentials: 'include',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	});
	if (!response.ok) {
		throw new Error(`Request to ${path} failed: ${response.status}`);
	}
	return response.json();
}

async function postJSON<T>(path: string, body?: Record<string, unknown>): Promise<T> {
	const response = await fetch(`${env.PUBLIC_API_BASE_URL}${path}`, {
		method: 'POST',
		credentials: 'include',
		...(body !== undefined && {
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(body),
		}),
	});
	if (!response.ok) {
		throw new Error(`Request to ${path} failed: ${response.status}`);
	}
	return response.json();
}

async function deleteJSON<T>(path: string): Promise<T> {
	const response = await fetch(`${env.PUBLIC_API_BASE_URL}${path}`, {
		method: 'DELETE',
		credentials: 'include',
	});
	if (!response.ok) {
		throw new Error(`Request to ${path} failed: ${response.status}`);
	}
	return response.json();
}

async function putJSON<T>(path: string, body: Record<string, unknown>): Promise<T> {
	const response = await fetch(`${env.PUBLIC_API_BASE_URL}${path}`, {
		method: 'PUT',
		credentials: 'include',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	});
	if (!response.ok) {
		throw new Error(`Request to ${path} failed: ${response.status}`);
	}
	return response.json();
}

export const api = {
	listWidgets: () => getJSON<WidgetSummaryMeta[]>('/api/widgets'),
	widgetSummary: <T = Record<string, unknown>>(id: string) => getJSON<T>(`/api/widgets/${id}/summary`),
	widgetDetail: <T = Record<string, unknown>>(id: string) => getJSON<T>(`/api/widgets/${id}/detail`),
	updateWidgetSettings: <T = Record<string, unknown>>(id: string, settings: Record<string, unknown>) =>
		patchJSON<T>(`/api/widgets/${id}/settings`, settings),
	getWidgetDeviceSettings: <T = Record<string, unknown>>(id: string) =>
		getJSON<T>(`/api/widgets/${id}/device-settings`),
	updateWidgetDeviceSettings: <T = Record<string, unknown>>(id: string, settings: Record<string, unknown>) =>
		patchJSON<T>(`/api/widgets/${id}/device-settings`, settings),
	clearWidgetDeviceSettings: (id: string) => deleteJSON<{ status: string }>(`/api/widgets/${id}/device-settings`),
	updateWidgetsLayout: (widgets: { id: string; layout: WidgetLayout }[]) =>
		putJSON<{ status: string }>('/api/widgets/layout', { widgets }),
	runAiWidget: <T = Record<string, unknown>>(id: string) => postJSON<T>(`/api/widgets/${id}/run`),
	searchCities: (query: string) => getJSON<CityResult[]>(`/api/weather/search?q=${encodeURIComponent(query)}`),
	themes: () => getJSON<{ themes: { id: string; name: string }[]; default: string }>('/api/theme'),
	tabs: () => getJSON<TabMeta[]>('/api/tabs'),
	settings: () => getJSON<AppSettings>('/api/settings'),
	updateSettings: (partial: Record<string, string>) => patchJSON<AppSettings>('/api/settings', partial),
	version: () => getJSON<VersionInfo>('/api/version'),
	createAlert: (alert: { message: string; severity?: AlertSeverity; expires_in_minutes?: number }) =>
		postJSON<Alert>('/api/alerts', alert),
	dismissAlert: (id: number) => postJSON<{ status: string }>(`/api/alerts/${id}/dismiss`),
	calendarStatus: () => getJSON<CalendarStatus>('/api/calendar/status'),
	listCaldavCalendars: () => getJSON<CaldavCalendar[]>('/api/calendar/caldav/calendars'),
	sportsTeams: (league: string) => getJSON<SportsTeamOption[]>(`/api/sports/${encodeURIComponent(league)}/teams`),
	icloudStatus: () => getJSON<IcloudStatus>('/api/icloud/status'),
	startIcloudAuth: () => postJSON<IcloudAuthStartResult>('/api/icloud/auth/start'),
	verifyIcloudAuth: (code: string) => postJSON<IcloudStatus>('/api/icloud/auth/verify', { code }),
	askAssistant: (text: string) => postJSON<{ text: string }>('/api/assistant/ask', { text }),
	widgetTypes: () =>
		getJSON<{ type: string; name: string; default_layout: { colSpan: number; rowSpan: number } }[]>(
			'/api/widgets/types',
		),
	addWidget: (type: string, layout: WidgetLayout, tab?: string) =>
		postJSON<WidgetSummaryMeta>('/api/widgets', { type, layout, ...(tab !== undefined && { tab }) }),
	removeWidget: (id: string) => deleteJSON<{ status: string }>(`/api/widgets/${id}`),
	jellyfinTestConnection: (id: string, settings: Record<string, unknown>) =>
		postJSON<JellyfinTestConnectionResult>(`/api/jellyfin/${id}/test-connection`, settings),
	jellyfinChildren: (id: string, parentId?: string) =>
		getJSON<JellyfinItem[]>(
			parentId
				? `/api/jellyfin/${id}/items?parent_id=${encodeURIComponent(parentId)}`
				: `/api/jellyfin/${id}/libraries`,
		),
	jellyfinImageUrl: (id: string, itemId: string) => `${env.PUBLIC_API_BASE_URL}/api/jellyfin/${id}/images/${itemId}`,
	jellyfinStreamUrl: (id: string, itemId: string) => `${env.PUBLIC_API_BASE_URL}/api/jellyfin/${id}/stream/${itemId}`,
	hdhomerunTestTunerConnection: (id: string, settings: Record<string, unknown>) =>
		postJSON<HDHomeRunTestConnectionResult>(`/api/hdhomerun/${id}/test-tuner-connection`, settings),
	hdhomerunTestDvrConnection: (id: string, settings: Record<string, unknown>) =>
		postJSON<HDHomeRunTestConnectionResult>(`/api/hdhomerun/${id}/test-dvr-connection`, settings),
	hdhomerunTranscodePresets: () => getJSON<HDHomeRunTranscodePreset[]>('/api/hdhomerun/transcode-presets'),
	// Channel playback_url is a backend-relative proxy path — resolve it
	// against the API base the same way jellyfinImageUrl/jellyfinStreamUrl do.
	hdhomerunPlaybackUrl: (url: string) => (url.startsWith('/') ? `${env.PUBLIC_API_BASE_URL}${url}` : url),
	hdhomerunPlaylistUrl: (id: string, channelNumber: string) =>
		`${env.PUBLIC_API_BASE_URL}/api/hdhomerun/${id}/playlist/${channelNumber}`,
	piholeTestConnection: (id: string, settings: Record<string, unknown>) =>
		postJSON<PiholeTestConnectionResult>(`/api/pihole/${id}/test-connection`, settings),
	piholeSetBlocking: (id: string, enabled: boolean, timer?: number | null) =>
		postJSON<{ blocking: string; timer: number | null }>(`/api/pihole/${id}/blocking`, {
			enabled,
			timer: timer ?? null,
		}),
	synologyTestConnection: (id: string, settings: Record<string, unknown>) =>
		postJSON<SynologyTestConnectionResult>(`/api/synology/${id}/test-connection`, settings),
	asusRouterTestConnection: (id: string, settings: Record<string, unknown>) =>
		postJSON<AsusRouterTestConnectionResult>(`/api/asus-router/${id}/test-connection`, settings),
	registerDevice: () => postJSON<DeviceRegisterResult>('/api/devices/register'),
	currentDevice: () => getJSON<DeviceInfo>('/api/devices/me'),
	renameDevice: (name: string) => patchJSON<DeviceInfo>('/api/devices/me', { name }),
	listDevices: () => getJSON<DeviceListEntry[]>('/api/devices'),
	deleteDevice: (id: string) => deleteJSON<{ status: string }>(`/api/devices/${id}`),
	layoutStatus: () => getJSON<LayoutStatus>('/api/devices/me/layout-status'),
	copyDeviceLayout: (sourceDeviceId: string) =>
		postJSON<{ status: string }>('/api/devices/me/copy-layout', { source_device_id: sourceDeviceId }),
	listUsers: () => getJSON<UserProfile[]>('/api/users'),
	createUser: (name: string, avatar?: string, pin?: string) =>
		postJSON<CurrentUser>('/api/users', {
			name,
			...(avatar !== undefined && { avatar }),
			...(pin !== undefined && { pin }),
		}),
	loginUser: (id: string, pin?: string) => postJSON<CurrentUser>(`/api/users/${id}/login`, { pin }),
	logoutUser: () => postJSON<{ status: string }>('/api/users/logout'),
	currentUser: () => getJSON<CurrentUser>('/api/users/me'),
	updateUser: (partial: { name?: string; avatar?: string; pin?: string }) =>
		patchJSON<CurrentUser>('/api/users/me', partial),
	deleteUser: () => deleteJSON<{ status: string }>('/api/users/me'),
	getPreferences: () => getJSON<UserPreferences>('/api/users/me/preferences'),
	updatePreferences: (partial: Partial<UserPreferences>) =>
		patchJSON<UserPreferences>('/api/users/me/preferences', partial),
	setupStatus: () => getJSON<SetupStatus>('/api/setup/status'),
	createSetupAdmin: (name: string, avatar?: string, pin?: string) =>
		postJSON<CurrentUser>('/api/setup/admin', {
			name,
			...(avatar !== undefined && { avatar }),
			...(pin !== undefined && { pin }),
		}),
	listHouseholdUsers: () => getJSON<HouseholdUser[]>('/api/admin/users'),
	updateUserRole: (id: string, role: UserRole) => patchJSON<HouseholdUser>(`/api/admin/users/${id}/role`, { role }),
	removeHouseholdUser: (id: string) => deleteJSON<{ status: string }>(`/api/admin/users/${id}`),
};
