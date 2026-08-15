// Dynamic (not static) so the API base URL can be set as a runtime
// environment variable against the built Node server, rather than baked
// into the client bundle at Docker build time — lets frontend and backend
// run on different hosts without a rebuild.
import { env } from '$env/dynamic/public';
import { logger } from '$lib/logger';

export interface WidgetLayout {
	col: number;
	row: number;
	colSpan: number;
	rowSpan: number;
}

// Which viewport class a layout applies to, not which physical device — a
// tile's position is shared by every device rendering at the same class.
export type Breakpoint = 'wide' | 'narrow';

export interface WidgetSummaryMeta {
	id: string;
	type: string;
	name: string;
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

export interface MovieProvider {
	id: number;
	name: string;
	logo_url: string | null;
}

export interface AppSettings {
	ai_model: string;
	ai_reasoning_effort: string;
	ai_agent_name: string;
	searxng_url: string;
	timezone: string;
	has_anthropic_api_key: boolean;
	has_openai_api_key: boolean;
	has_gemini_api_key: boolean;
	openai_tts_enabled: string;
	openai_tts_model: string;
	piper_tts_enabled: string;
	piper_server_url: string;
	piper_voices: string;
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

export interface JellyfinAudioStream {
	index: number;
	display_title: string;
	language: string;
	codec: string;
	channels: number;
	is_default: boolean;
}

export interface JellyfinSubtitleStream {
	index: number;
	display_title: string;
	language: string;
	codec: string;
	is_default: boolean;
	is_forced: boolean;
}

export interface JellyfinChapter {
	name: string;
	start_seconds: number;
}

export interface JellyfinVideoStream {
	codec: string;
	width: number | null;
	height: number | null;
	aspect_ratio: string;
	framerate: number | null;
	bitrate: number | null;
}

export interface JellyfinMediaDetail {
	id: string;
	name: string;
	type: string;
	overview: string | null;
	year: number | null;
	runtime_minutes: number | null;
	container: string | null;
	video_stream: JellyfinVideoStream | null;
	audio_streams: JellyfinAudioStream[];
	subtitle_streams: JellyfinSubtitleStream[];
	chapters: JellyfinChapter[];
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

export interface JellyfinSection {
	label: string;
	items: JellyfinItem[];
}

export interface HDHomeRunGuideEntry {
	series_id?: string | null;
	title: string;
	episode_title: string | null;
	episode_number?: string | null;
	synopsis?: string | null;
	start: number | null;
	end: number | null;
	original_airdate?: number | string | null;
	image_url?: string | null;
	channel_number?: string;
}

export interface HDHomeRunRecordingRule {
	RecordingRuleID: string;
	SeriesID: string;
	Title: string;
	Synopsis?: string;
	ImageURL?: string;
	ChannelOnly?: string;
	DateTimeOnly?: number;
	Priority?: number;
	StartPadding?: number;
	EndPadding?: number;
	RecentOnly?: number | boolean;
}

export interface HDHomeRunFullGuideChannel {
	channel_number: string;
	channel_name: string;
	airings: HDHomeRunGuideEntry[];
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
	recording_id?: string | null;
	series_id?: string | null;
	title: string;
	episode_title?: string | null;
	episode_number?: string | null;
	synopsis?: string | null;
	channel_number?: string | null;
	channel_name: string | null;
	start: number | null;
	record_end: number | null;
	play_url?: string | null;
	image_url?: string | null;
	duration_seconds?: number | null;
	is_dvr_file?: boolean;
}

export interface HDHomeRunRecordingVideoInfo {
	codec: string | null;
	width: number | null;
	height: number | null;
	fps: number | null;
}

export interface HDHomeRunRecordingAudioInfo {
	index: number;
	codec: string | null;
	channels: number | null;
	language: string | null;
}

/** GET /api/hdhomerun/{id}/recording-detail — see backend/app/api/hdhomerun.py. */
export interface HDHomeRunRecordingDetail {
	is_in_progress: boolean;
	duration_seconds: number | null;
	video: HDHomeRunRecordingVideoInfo | null;
	audio: HDHomeRunRecordingAudioInfo[];
	has_captions: boolean;
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

export interface QBittorrentSummary {
	connected: boolean;
	host: string;
	port: number;
	use_https: boolean;
	username: string;
	has_password: boolean;
	torrent_count?: number;
	downloading_count?: number;
	seeding_count?: number;
	download_speed_bps?: number;
	upload_speed_bps?: number;
	error?: string;
}

export interface QBittorrentTorrent {
	hash: string;
	name: string;
	state: string;
	progress: number;
	size_bytes: number;
	download_speed_bps: number;
	upload_speed_bps: number;
	eta_seconds: number | null;
}

export interface QBittorrentDetail extends QBittorrentSummary {
	torrents: QBittorrentTorrent[];
}

export interface QBittorrentTestConnectionResult {
	ok: boolean;
	version: string | null;
	error: string | null;
}

export interface SpeedtestSummary {
	title: string;
	ran_at: string | null;
	download_mbps: number | null;
	upload_mbps: number | null;
	ping_ms: number | null;
	server_name: string | null;
}

export interface SpeedtestRun {
	ran_at: string;
	download_mbps: number;
	upload_mbps: number;
	ping_ms: number;
	server_name: string;
}

export interface SpeedtestDetail extends SpeedtestSummary {
	history: SpeedtestRun[];
	interval_minutes: number;
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

export interface AsusRouterClient {
	name: string;
	hostname?: string;
	alias?: string | null;
	ip: string;
	mac: string;
	online: boolean;
	connection_type: 'wired' | 'wireless' | 'unknown';
	wireless_band?: string | null;
	rssi?: number | null;
	tx_rate?: number | null;
	rx_rate?: number | null;
	vendor?: string | null;
	ip_type?: 'dhcp' | 'static' | 'unknown';
	internet_blocked?: boolean;
}

export interface AsusRouterPortInfo {
	port: number;
	service: string;
	protocol: 'tcp' | 'udp';
	is_web: boolean;
	web_url?: string | null;
	title?: string | null;
}

export interface AsusRouterPortScanResult {
	ip: string;
	open_ports: AsusRouterPortInfo[];
	web_url?: string | null;
	scanned_at: string;
}

export interface AsusRouterPingResult {
	ip: string;
	alive: boolean;
	latency_ms?: number | null;
}

export interface AsusRouterSummary {
	connected: boolean;
	wan_connected: boolean;
	client_count: number;
	host: string;
	ssh_port: number;
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

export interface BookmarkItem {
	name: string;
	url: string;
	icon?: string;
}

export interface BookmarksData {
	title: string;
	bookmarks: BookmarkItem[];
}

export interface Chore {
	id: number;
	widget_id: string;
	user_id: string;
	text: string;
	completed: boolean;
	created_at: string;
	completed_at: string | null;
}

export interface ChoresData {
	title: string;
	chores: Chore[];
	open_count: number;
}

export interface ShoppingItem {
	id: number;
	widget_id: string;
	text: string;
	checked: boolean;
	added_by: string;
	checked_by: string | null;
	created_at: string;
	checked_at: string | null;
}

export interface ShoppingData {
	title: string;
	items: ShoppingItem[];
	open_count: number;
}

export interface Package {
	id: number;
	widget_id: string;
	tracking_number: string;
	carrier: string | null;
	label: string | null;
	status: string | null;
	last_event: string | null;
	eta_date: string | null;
	delivered: boolean;
	added_at: string;
	updated_at: string | null;
}

export interface RSSFeed {
	id: number;
	user_id: string;
	url: string;
	name: string | null;
	item_limit: number;
	created_at: string;
}

export interface RSSItem {
	title: string;
	link: string;
	published: string | null;
	source: string;
	summary?: string;
	image?: string | null;
}

export interface RSSFeedGroup {
	feed_id: number;
	name: string;
	items: RSSItem[];
	error?: string;
}

export interface RSSSummary {
	title: string;
	feed_groups: RSSFeedGroup[];
}

export interface RSSDetail extends RSSSummary {
	feed_ids: number[];
	all_feeds: RSSFeed[];
}

export interface PackagesSummary {
	title: string;
	arriving_today_count: number;
	arriving_today: Package[];
	active_count: number;
}

export interface PackagesData extends PackagesSummary {
	packages: Package[];
}

export interface NASAApodSummary {
	title: string;
	available: boolean;
	apod_title?: string;
	date?: string;
	media_type?: string;
	thumbnail_url?: string | null;
	stale?: boolean;
	fetched_at?: string;
}

export interface NASAApodDetail {
	title: string;
	available: boolean;
	apod_title?: string;
	explanation?: string;
	url?: string;
	hdurl?: string | null;
	thumbnail_url?: string | null;
	media_type?: string;
	date?: string;
	copyright?: string | null;
	stale?: boolean;
	fetched_at?: string;
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
	network_integration_id: string;
	network_integration_name: string | null;
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

// Shared connection config for a LAN device, edited once at the network
// level instead of per-widget — see backend/app/api/network_settings.py.
// `settings` is loosely typed since its shape depends on `type` (Pi-hole's
// host/port/use_https/has_password vs. Jellyfin's auth_mode/api_key/... vs.
// Container's engine/connection/socket_path/host/port); each settings page
// section narrows it to the fields it actually renders.
export interface NetworkIntegration {
	id: string;
	type: string;
	name: string;
	settings: Record<string, unknown>;
}

export interface NetworkTestConnectionResult {
	ok: boolean;
	detail: string | null;
	error: string | null;
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
	team_espn_url: string | null;
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
	home_espn_url: string | null;
	away_team: string;
	away_abbreviation: string;
	away_rank: number | null;
	away_espn_url: string | null;
	home_score: string | null;
	away_score: string | null;
	broadcast_links: SportsBroadcastLink[];
	venue: string | null;
}

export interface SportsSummary {
	configured: boolean;
	todays_games: SportsSummaryGame[];
	trending: SportsTrendingGame[];
	upcoming_games: SportsSummaryGame[];
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
	error?: string;
}

export interface SportsDetail {
	configured: boolean;
	teams: SportsTeamDetail[];
	todays_games: SportsSummaryGame[];
	trending: SportsTrendingGame[];
	upcoming_games: SportsSummaryGame[];
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

export interface SteamNewsItem {
	gid: string;
	title: string;
	url: string;
	author: string;
	contents: string;
	feedlabel: string;
	date: number; // unix seconds
	is_external_url: boolean;
	appid: number;
	game_name: string;
}

export interface SteamNewsError {
	appid: number;
	game_name: string;
	error: string;
}

export interface SteamSummary {
	configured: boolean;
	player: SteamPlayer | null;
	current_game: string | null;
	recent_games: SteamGame[];
	news: SteamNewsItem[];
	news_errors?: SteamNewsError[];
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
	hardware: boolean;
}

export interface HWAccelDevice {
	path: string;
	mode?: string;
	owner_uid?: number;
	owner_gid?: number;
	readable?: boolean;
	writable?: boolean;
	error?: string;
}

export interface HWAccelProbe {
	ok: boolean;
	command: string | null;
	exit_code: number | null;
	output: string;
}

/** Report from GET /api/hdhomerun/{id}/hwaccel-diagnostics — see backend/app/hwaccel.py. */
export interface HWAccelDiagnostics {
	device: string;
	process: { uid: number; gid: number; groups: number[] };
	dri: { dir_exists: boolean; devices: HWAccelDevice[] };
	ffmpeg: {
		version: string;
		hwaccels: string[];
		hardware_encoders: string[];
		ffmpeg_available: boolean;
	};
	vainfo: {
		ok: boolean;
		output: string;
		driver: string | null;
		profiles: Record<string, string[]>;
		can_decode_mpeg2: boolean;
		can_encode_h264: boolean;
	} | null;
	probes: Record<string, HWAccelProbe>;
	sample_error: string | null;
	summary: string[];
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
	voice_provider: string;
	voice_id: string;
	voice_name: string;
	locale: string;
}

export interface TTSVoice {
	id: string;
	label: string;
	provider: 'openai' | 'piper';
}

export interface ScreensaverSettings {
	enabled: boolean;
	idle_timeout_seconds: number;
	rotation_interval_seconds: number;
	widget_ids: string[];
	text_animation_style: 'marquee' | 'matrix' | 'flipboard' | 'led_dots';
	led_color: string;
	text_pause_seconds: number;
	flipboard_pattern: 'top_to_bottom' | 'random';
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
		logger.warn(`Request to ${path} failed: ${response.status}`);
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
		logger.warn(`Request to ${path} failed: ${response.status}`);
		throw new Error(`Request to ${path} failed: ${response.status}`);
	}
	return response.json();
}

// Reads a failed response's `{detail: string}` body (FastAPI's HTTPException
// shape), if present, so callers can surface the server's actual reason
// (e.g. why an HDHomeRun DVR recording rule was rejected) instead of just a
// bare status code. Falls back to the status-only message when the body
// isn't JSON or has no `detail`.
async function _errorMessage(path: string, response: Response): Promise<string> {
	try {
		const body = await response.json();
		if (body && typeof body.detail === 'string' && body.detail) {
			return body.detail;
		}
	} catch {
		// Not JSON, or already consumed — fall through to the generic message.
	}
	return `Request to ${path} failed: ${response.status}`;
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
		const message = await _errorMessage(path, response);
		logger.warn(`Request to ${path} failed: ${response.status}`);
		throw new Error(message);
	}
	return response.json();
}

// Like postJSON, but for an endpoint that returns raw audio bytes rather
// than JSON (/api/tts/synthesize) — used to fetch cloud/Piper speech audio
// for playback via an <audio> element.
async function postForBlob(path: string, body: Record<string, unknown>): Promise<Blob> {
	const response = await fetch(`${env.PUBLIC_API_BASE_URL}${path}`, {
		method: 'POST',
		credentials: 'include',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	});
	if (!response.ok) {
		logger.warn(`Request to ${path} failed: ${response.status}`);
		throw new Error(`Request to ${path} failed: ${response.status}`);
	}
	return response.blob();
}

async function deleteJSON<T>(path: string): Promise<T> {
	const response = await fetch(`${env.PUBLIC_API_BASE_URL}${path}`, {
		method: 'DELETE',
		credentials: 'include',
	});
	if (!response.ok) {
		const message = await _errorMessage(path, response);
		logger.warn(`Request to ${path} failed: ${response.status}`);
		throw new Error(message);
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
		logger.warn(`Request to ${path} failed: ${response.status}`);
		throw new Error(`Request to ${path} failed: ${response.status}`);
	}
	return response.json();
}

export const api = {
	listWidgets: (breakpoint: Breakpoint) => getJSON<WidgetSummaryMeta[]>(`/api/widgets?breakpoint=${breakpoint}`),
	widgetSummary: <T = Record<string, unknown>>(id: string) => getJSON<T>(`/api/widgets/${id}/summary`),
	widgetDetail: <T = Record<string, unknown>>(id: string) => getJSON<T>(`/api/widgets/${id}/detail`),
	updateWidgetSettings: <T = Record<string, unknown>>(id: string, settings: Record<string, unknown>) =>
		patchJSON<T>(`/api/widgets/${id}/settings`, settings),
	renameWidget: (id: string, name: string) =>
		patchJSON<{ id: string; name: string }>(`/api/widgets/${id}/name`, { name }),
	getWidgetDeviceSettings: <T = Record<string, unknown>>(id: string) =>
		getJSON<T>(`/api/widgets/${id}/device-settings`),
	updateWidgetDeviceSettings: <T = Record<string, unknown>>(id: string, settings: Record<string, unknown>) =>
		patchJSON<T>(`/api/widgets/${id}/device-settings`, settings),
	clearWidgetDeviceSettings: (id: string) => deleteJSON<{ status: string }>(`/api/widgets/${id}/device-settings`),
	updateWidgetsLayout: (widgets: { id: string; layout: WidgetLayout }[], breakpoint: Breakpoint) =>
		putJSON<{ status: string }>('/api/widgets/layout', { widgets, breakpoint }),
	runAiWidget: <T = Record<string, unknown>>(id: string) => postJSON<T>(`/api/widgets/${id}/run`),
	searchCities: (query: string) => getJSON<CityResult[]>(`/api/weather/search?q=${encodeURIComponent(query)}`),
	movieProviders: (region: string) =>
		getJSON<MovieProvider[]>(`/api/movies/providers?region=${encodeURIComponent(region)}`),
	themes: () => getJSON<{ themes: { id: string; name: string }[]; default: string }>('/api/theme'),
	tabs: () => getJSON<TabMeta[]>('/api/tabs'),
	settings: () => getJSON<AppSettings>('/api/settings'),
	updateSettings: (partial: Record<string, string>) => patchJSON<AppSettings>('/api/settings', partial),
	version: () => getJSON<VersionInfo>('/api/version'),
	createAlert: (alert: { message: string; severity?: AlertSeverity; expires_in_minutes?: number }) =>
		postJSON<Alert>('/api/alerts', alert),
	dismissAlert: (id: number) => postJSON<{ status: string }>(`/api/alerts/${id}/dismiss`),
	createChore: (widgetId: string, text: string) => postJSON<Chore>('/api/chores', { widget_id: widgetId, text }),
	completeChore: (id: number) => postJSON<Chore>(`/api/chores/${id}/complete`),
	removeChore: (id: number) => deleteJSON<{ status: string }>(`/api/chores/${id}`),
	createShoppingItem: (widgetId: string, text: string) =>
		postJSON<ShoppingItem>('/api/shopping', { widget_id: widgetId, text }),
	checkShoppingItem: (id: number) => postJSON<ShoppingItem>(`/api/shopping/${id}/check`),
	removeShoppingItem: (id: number) => deleteJSON<{ status: string }>(`/api/shopping/${id}`),
	createPackage: (widgetId: string, trackingNumber: string, label?: string) =>
		postJSON<Package>('/api/packages', {
			widget_id: widgetId,
			tracking_number: trackingNumber,
			...(label && { label }),
		}),
	removePackage: (id: number) => deleteJSON<{ status: string }>(`/api/packages/${id}`),
	listRSSFeeds: () => getJSON<RSSFeed[]>('/api/rss/feeds'),
	addRSSFeed: (url: string, name?: string, item_limit?: number) =>
		postJSON<RSSFeed>('/api/rss/feeds', { url, ...(name && { name }), ...(item_limit && { item_limit }) }),
	updateRSSFeed: (id: number, name: string | null, item_limit: number) =>
		patchJSON<RSSFeed>(`/api/rss/feeds/${id}`, { name, item_limit }),
	deleteRSSFeed: (id: number) => deleteJSON<{ status: string }>(`/api/rss/feeds/${id}`),
	calendarStatus: () => getJSON<CalendarStatus>('/api/calendar/status'),
	listCaldavCalendars: () => getJSON<CaldavCalendar[]>('/api/calendar/caldav/calendars'),
	sportsTeams: (league: string) => getJSON<SportsTeamOption[]>(`/api/sports/${encodeURIComponent(league)}/teams`),
	icloudStatus: () => getJSON<IcloudStatus>('/api/icloud/status'),
	startIcloudAuth: () => postJSON<IcloudAuthStartResult>('/api/icloud/auth/start'),
	verifyIcloudAuth: (code: string) => postJSON<IcloudStatus>('/api/icloud/auth/verify', { code }),
	askAssistant: (text: string) => postJSON<{ text: string }>('/api/assistant/ask', { text }),
	assistantTopics: () => getJSON<{ id: string; name: string }[]>('/api/assistant/topics'),
	widgetTypes: () =>
		getJSON<{ type: string; name: string; default_layout: { colSpan: number; rowSpan: number } }[]>(
			'/api/widgets/types',
		),
	addWidget: (type: string, layout: WidgetLayout, tab?: string) =>
		postJSON<WidgetSummaryMeta>('/api/widgets', { type, layout, ...(tab !== undefined && { tab }) }),
	removeWidget: (id: string) => deleteJSON<{ status: string }>(`/api/widgets/${id}`),
	jellyfinChildren: (id: string, parentId?: string) =>
		getJSON<JellyfinItem[]>(
			parentId
				? `/api/jellyfin/${id}/items?parent_id=${encodeURIComponent(parentId)}`
				: `/api/jellyfin/${id}/libraries`,
		),
	jellyfinItemDetail: (id: string, itemId: string) =>
		getJSON<JellyfinMediaDetail>(`/api/jellyfin/${id}/detail/${itemId}`),
	jellyfinSubtitleUrl: (id: string, itemId: string, streamIndex: number) =>
		`${env.PUBLIC_API_BASE_URL}/api/jellyfin/${id}/subtitles/${itemId}/${streamIndex}.vtt`,
	jellyfinImageUrl: (id: string, itemId: string) => `${env.PUBLIC_API_BASE_URL}/api/jellyfin/${id}/images/${itemId}`,
	jellyfinStreamUrl: (id: string, itemId: string, options?: { audioStreamIndex?: number }) => {
		const base = `${env.PUBLIC_API_BASE_URL}/api/jellyfin/${id}/stream/${itemId}`;
		if (options?.audioStreamIndex !== undefined) {
			return `${base}?audio_stream_index=${options.audioStreamIndex}`;
		}
		return base;
	},
	hdhomerunTranscodePresets: () => getJSON<HDHomeRunTranscodePreset[]>('/api/hdhomerun/transcode-presets'),
	// Channel playback_url is a backend-relative proxy path — resolve it
	// against the API base the same way jellyfinImageUrl/jellyfinStreamUrl do.
	hdhomerunPlaybackUrl: (url: string) => (url.startsWith('/') ? `${env.PUBLIC_API_BASE_URL}${url}` : url),
	hdhomerunRecordingStreamUrl: (id: string, playUrl: string, options?: { start?: number; audioIndex?: number }) => {
		const params = new URLSearchParams({ url: playUrl });
		if (options?.start !== undefined) params.set('start', String(options.start));
		if (options?.audioIndex !== undefined) params.set('audio_index', String(options.audioIndex));
		return `${env.PUBLIC_API_BASE_URL}/api/hdhomerun/${id}/recording-stream?${params.toString()}`;
	},
	hdhomerunRecordingDetail: (
		id: string,
		options: { url: string; recordingId: string; start?: number | null; recordEnd?: number | null },
	) => {
		const params = new URLSearchParams({ url: options.url, recording_id: options.recordingId });
		if (options.start !== undefined && options.start !== null) params.set('start', String(options.start));
		if (options.recordEnd !== undefined && options.recordEnd !== null) {
			params.set('record_end', String(options.recordEnd));
		}
		return getJSON<HDHomeRunRecordingDetail>(`/api/hdhomerun/${id}/recording-detail?${params.toString()}`);
	},
	hdhomerunRecordingCaptionsUrl: (
		id: string,
		options: { url: string; recordingId: string; recordEnd?: number | null },
	) => {
		const params = new URLSearchParams({ url: options.url, recording_id: options.recordingId });
		if (options.recordEnd !== undefined && options.recordEnd !== null) {
			params.set('record_end', String(options.recordEnd));
		}
		return `${env.PUBLIC_API_BASE_URL}/api/hdhomerun/${id}/recording-captions.vtt?${params.toString()}`;
	},
	hdhomerunRecordingThumbnailSpriteUrl: (
		id: string,
		options: { url: string; recordingId: string; recordEnd?: number | null },
	) => {
		const params = new URLSearchParams({ url: options.url });
		if (options.recordEnd !== undefined && options.recordEnd !== null) {
			params.set('record_end', String(options.recordEnd));
		}
		return `${env.PUBLIC_API_BASE_URL}/api/hdhomerun/${id}/recording-thumbnails/${options.recordingId}.jpg?${params.toString()}`;
	},
	hdhomerunRecordingThumbnailVttUrl: (
		id: string,
		options: { url: string; recordingId: string; recordEnd?: number | null },
	) => {
		const params = new URLSearchParams({ url: options.url });
		if (options.recordEnd !== undefined && options.recordEnd !== null) {
			params.set('record_end', String(options.recordEnd));
		}
		return `${env.PUBLIC_API_BASE_URL}/api/hdhomerun/${id}/recording-thumbnails/${options.recordingId}.vtt?${params.toString()}`;
	},
	hdhomerunPlaylistUrl: (id: string, channelNumber: string) =>
		`${env.PUBLIC_API_BASE_URL}/api/hdhomerun/${id}/playlist/${channelNumber}`,
	// Admin-only, and slow by design: it test-encodes a short clip through
	// each plausible preset, so budget several seconds.
	hdhomerunHwaccelDiagnostics: (id: string, device?: string) =>
		getJSON<HWAccelDiagnostics>(
			`/api/hdhomerun/${id}/hwaccel-diagnostics${device ? `?device=${encodeURIComponent(device)}` : ''}`,
		),
	addHDHomeRunRecordingRule: (
		id: string,
		rule: {
			series_id: string;
			date_time?: number;
			channel?: string;
			recent_only?: boolean;
			start_padding?: number;
			end_padding?: number;
		},
	) => postJSON<HDHomeRunRecordingRule[]>(`/api/hdhomerun/${id}/recording-rules`, rule),
	deleteHDHomeRunRecordingRule: (id: string, ruleId: string) =>
		deleteJSON<HDHomeRunRecordingRule[]>(`/api/hdhomerun/${id}/recording-rules/${ruleId}`),
	getHDHomeRunGuide: (id: string) => getJSON<HDHomeRunFullGuideChannel[]>(`/api/hdhomerun/${id}/guide`),
	piholeSetBlocking: (id: string, enabled: boolean, timer?: number | null) =>
		postJSON<{ blocking: string; timer: number | null }>(`/api/pihole/${id}/blocking`, {
			enabled,
			timer: timer ?? null,
		}),
	// Network-level integration settings (Pi-hole, Jellyfin, Synology, Asus
	// Router, HDHomeRun, Container) — shared per-device connection config
	// edited once, not per widget instance. See backend/app/api/network_settings.py.
	listNetworkIntegrations: () => getJSON<NetworkIntegration[]>('/api/network-settings'),
	getNetworkIntegration: (type: string) => getJSON<NetworkIntegration>(`/api/network-settings/${type}`),
	listContainerIntegrations: () => getJSON<NetworkIntegration[]>('/api/network-settings/container'),
	updateNetworkIntegration: (type: string, settings: Record<string, unknown>) =>
		patchJSON<NetworkIntegration>(`/api/network-settings/${type}`, settings),
	testNetworkIntegrationConnection: (type: string, settings: Record<string, unknown>) =>
		postJSON<NetworkTestConnectionResult>(`/api/network-settings/${type}/test-connection`, settings),
	testHDHomeRunTunerConnection: (settings: Record<string, unknown>) =>
		postJSON<NetworkTestConnectionResult>('/api/network-settings/hdhomerun/test-tuner-connection', settings),
	testHDHomeRunDvrConnection: (settings: Record<string, unknown>) =>
		postJSON<NetworkTestConnectionResult>('/api/network-settings/hdhomerun/test-dvr-connection', settings),
	createContainerIntegration: (name: string, settings: Record<string, unknown>) =>
		postJSON<NetworkIntegration>('/api/network-settings/container', { name, ...settings }),
	updateContainerIntegration: (id: string, settings: Record<string, unknown>) =>
		patchJSON<NetworkIntegration>(`/api/network-settings/container/${id}`, settings),
	deleteContainerIntegration: (id: string) => deleteJSON<{ status: string }>(`/api/network-settings/container/${id}`),
	testContainerIntegrationConnection: (id: string, settings: Record<string, unknown>) =>
		postJSON<NetworkTestConnectionResult>(`/api/network-settings/container/${id}/test-connection`, settings),
	qbittorrentTestConnection: (id: string, settings: Record<string, unknown>) =>
		postJSON<QBittorrentTestConnectionResult>(`/api/qbittorrent/${id}/test-connection`, settings),
	asusRouterScanPorts: (widgetId: string, ip: string, ports?: number[]) =>
		postJSON<AsusRouterPortScanResult>(`/api/asus-router/${widgetId}/scan-ports`, { ip, ports }),
	asusRouterWakeOnLan: (widgetId: string, mac: string) =>
		postJSON<{ ok: boolean; mac: string; message: string }>(`/api/asus-router/${widgetId}/wake-on-lan`, { mac }),
	asusRouterSetClientBlock: (widgetId: string, mac: string, blocked: boolean) =>
		postJSON<{ ok: boolean; mac: string; blocked: boolean }>(`/api/asus-router/${widgetId}/client-block`, {
			mac,
			blocked,
		}),
	asusRouterSetClientAlias: (widgetId: string, mac: string, alias: string) =>
		postJSON<{ ok: boolean; mac: string; alias: string }>(`/api/asus-router/${widgetId}/client-alias`, {
			mac,
			alias,
		}),
	asusRouterSetStaticLease: (widgetId: string, mac: string, ip: string, name: string, enabled: boolean) =>
		postJSON<{ ok: boolean; mac: string; static: boolean }>(`/api/asus-router/${widgetId}/dhcp-static-lease`, {
			mac,
			ip,
			name,
			enabled,
		}),
	asusRouterPing: (widgetId: string, ip: string) =>
		postJSON<AsusRouterPingResult>(`/api/asus-router/${widgetId}/ping`, { ip }),
	registerDevice: () => postJSON<DeviceRegisterResult>('/api/devices/register'),
	currentDevice: () => getJSON<DeviceInfo>('/api/devices/me'),
	renameDevice: (name: string) => patchJSON<DeviceInfo>('/api/devices/me', { name }),
	listDevices: () => getJSON<DeviceListEntry[]>('/api/devices'),
	deleteDevice: (id: string) => deleteJSON<{ status: string }>(`/api/devices/${id}`),
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
	getScreensaverSettings: () => getJSON<ScreensaverSettings>('/api/screensaver/settings'),
	updateScreensaverSettings: (partial: Partial<ScreensaverSettings>) =>
		patchJSON<ScreensaverSettings>('/api/screensaver/settings', partial),
	ttsVoices: () => getJSON<TTSVoice[]>('/api/tts/voices'),
	synthesizeSpeech: (provider: 'openai' | 'piper', voiceId: string, text: string) =>
		postForBlob('/api/tts/synthesize', { provider, voice_id: voiceId, text }),
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
