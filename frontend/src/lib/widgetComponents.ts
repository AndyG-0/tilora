// Single source of truth for widget-type -> component mapping. The
// dashboard grid (`routes/+page.svelte`) and the drill-down detail view
// (`routes/widget/[id]/+page.svelte`) both index into these instead of each
// keeping its own parallel type-string list — adding a new plugin type only
// means adding one entry to each map below, not hunting down every route
// that switches on `widget.type`.
//
// Entries are import thunks, not components: resolving `import(...)` eagerly
// at module scope would bundle every widget type (including heavy libs like
// leaflet, hls.js, mpegts.js) into the dashboard route regardless of which
// ones a household actually uses. Consumers resolve a type's component via
// `$lib/lazyWidgetComponent`, which gives Rollup automatic per-type code
// splitting and caches each resolved component across the whole session.

import type { ComponentLoader } from '$lib/lazyWidgetComponent';

export const TILE_COMPONENTS: Record<string, ComponentLoader> = {
	weather: () => import('$lib/components/tiles/WeatherTile.svelte'),
	ai: () => import('$lib/components/tiles/AITile.svelte'),
	photos: () => import('$lib/components/tiles/PhotoTile.svelte'),
	movies: () => import('$lib/components/tiles/MovieTile.svelte'),
	discord: () => import('$lib/components/tiles/DiscordTile.svelte'),
	clock: () => import('$lib/components/tiles/ClockTile.svelte'),
	date: () => import('$lib/components/tiles/DateTile.svelte'),
	message: () => import('$lib/components/tiles/MessageTile.svelte'),
	rss: () => import('$lib/components/tiles/RSSTile.svelte'),
	bookmarks: () => import('$lib/components/tiles/BookmarksTile.svelte'),
	alert: () => import('$lib/components/tiles/AlertTile.svelte'),
	calendar: () => import('$lib/components/tiles/CalendarTile.svelte'),
	calendar_caldav: () => import('$lib/components/tiles/CalendarTile.svelte'),
	calendar_microsoft: () => import('$lib/components/tiles/CalendarTile.svelte'),
	jellyfin: () => import('$lib/components/tiles/JellyfinTile.svelte'),
	hdhomerun: () => import('$lib/components/tiles/HDHomeRunTile.svelte'),
	pihole: () => import('$lib/components/tiles/PiholeTile.svelte'),
	game2048: () => import('$lib/components/tiles/Game2048Tile.svelte'),
	wordle: () => import('$lib/components/tiles/WordleTile.svelte'),
	system_monitor: () => import('$lib/components/tiles/SystemMonitorTile.svelte'),
	container: () => import('$lib/components/tiles/ContainerTile.svelte'),
	synology: () => import('$lib/components/tiles/SynologyTile.svelte'),
	asus_router: () => import('$lib/components/tiles/AsusRouterTile.svelte'),
	sports: () => import('$lib/components/tiles/SportsTile.svelte'),
	steam: () => import('$lib/components/tiles/SteamTile.svelte'),
	bf6: () => import('$lib/components/tiles/BF6Tile.svelte'),
	goodreads: () => import('$lib/components/tiles/GoodreadsTile.svelte'),
	qbittorrent: () => import('$lib/components/tiles/QBittorrentTile.svelte'),
	speedtest: () => import('$lib/components/tiles/SpeedtestTile.svelte'),
	chores: () => import('$lib/components/tiles/ChoresTile.svelte'),
	shopping: () => import('$lib/components/tiles/ShoppingTile.svelte'),
	packages: () => import('$lib/components/tiles/PackageTile.svelte'),
	nasa_apod: () => import('$lib/components/tiles/NASATile.svelte'),
	flights: () => import('$lib/components/tiles/FlightsTile.svelte'),
	mapping: () => import('$lib/components/tiles/MappingTile.svelte'),
	artificial_analysis: () => import('$lib/components/tiles/ArtificialAnalysisTile.svelte'),
};

export const DETAIL_COMPONENTS: Record<string, ComponentLoader> = {
	weather: () => import('$lib/components/details/WeatherDetail.svelte'),
	ai: () => import('$lib/components/details/AIDetail.svelte'),
	photos: () => import('$lib/components/details/PhotoDetail.svelte'),
	movies: () => import('$lib/components/details/MovieDetail.svelte'),
	discord: () => import('$lib/components/details/DiscordDetail.svelte'),
	clock: () => import('$lib/components/details/ClockDetail.svelte'),
	date: () => import('$lib/components/details/DateDetail.svelte'),
	message: () => import('$lib/components/details/MessageDetail.svelte'),
	rss: () => import('$lib/components/details/RSSDetail.svelte'),
	bookmarks: () => import('$lib/components/details/BookmarksDetail.svelte'),
	alert: () => import('$lib/components/details/AlertDetail.svelte'),
	calendar: () => import('$lib/components/details/CalendarDetail.svelte'),
	calendar_caldav: () => import('$lib/components/details/CalendarDetail.svelte'),
	calendar_microsoft: () => import('$lib/components/details/CalendarDetail.svelte'),
	jellyfin: () => import('$lib/components/details/JellyfinDetail.svelte'),
	hdhomerun: () => import('$lib/components/details/HDHomeRunDetail.svelte'),
	pihole: () => import('$lib/components/details/PiholeDetail.svelte'),
	game2048: () => import('$lib/components/details/Game2048Detail.svelte'),
	wordle: () => import('$lib/components/details/WordleDetail.svelte'),
	system_monitor: () => import('$lib/components/details/SystemMonitorDetail.svelte'),
	container: () => import('$lib/components/details/ContainerDetail.svelte'),
	synology: () => import('$lib/components/details/SynologyDetail.svelte'),
	asus_router: () => import('$lib/components/details/AsusRouterDetail.svelte'),
	sports: () => import('$lib/components/details/SportsDetail.svelte'),
	steam: () => import('$lib/components/details/SteamDetail.svelte'),
	bf6: () => import('$lib/components/details/BF6Detail.svelte'),
	goodreads: () => import('$lib/components/details/GoodreadsDetail.svelte'),
	qbittorrent: () => import('$lib/components/details/QBittorrentDetail.svelte'),
	speedtest: () => import('$lib/components/details/SpeedtestDetail.svelte'),
	chores: () => import('$lib/components/details/ChoresDetail.svelte'),
	shopping: () => import('$lib/components/details/ShoppingDetail.svelte'),
	packages: () => import('$lib/components/details/PackageDetail.svelte'),
	nasa_apod: () => import('$lib/components/details/NASADetail.svelte'),
	flights: () => import('$lib/components/details/FlightsDetail.svelte'),
	mapping: () => import('$lib/components/details/MappingDetail.svelte'),
	artificial_analysis: () => import('$lib/components/details/ArtificialAnalysisDetail.svelte'),
};

// 'photos' is deliberately absent here: PhotoScreensaver needs a widget `id`
// to persist/restore its cursor, so ScreensaverContent.svelte renders it
// directly instead of through this generic (id-less) map.
export const SCREENSAVER_COMPONENTS: Record<string, ComponentLoader> = {
	clock: () => import('$lib/components/screensaver/ClockScreensaver.svelte'),
	date: () => import('$lib/components/screensaver/DateScreensaver.svelte'),
	calendar: () => import('$lib/components/screensaver/CalendarScreensaver.svelte'),
	calendar_caldav: () => import('$lib/components/screensaver/CalendarScreensaver.svelte'),
	calendar_microsoft: () => import('$lib/components/screensaver/CalendarScreensaver.svelte'),
	weather: () => import('$lib/components/screensaver/WeatherScreensaver.svelte'),
	flights: () => import('$lib/components/screensaver/FlightsScreensaver.svelte'),
};
