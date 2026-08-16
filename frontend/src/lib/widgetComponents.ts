// Single source of truth for widget-type -> component mapping. The
// dashboard grid (`routes/+page.svelte`) and the drill-down detail view
// (`routes/widget/[id]/+page.svelte`) both index into these instead of each
// keeping its own parallel type-string list — adding a new plugin type only
// means adding one entry to each map below, not hunting down every route
// that switches on `widget.type`.

import WeatherTile from '$lib/components/tiles/WeatherTile.svelte';
import AITile from '$lib/components/tiles/AITile.svelte';
import PhotoTile from '$lib/components/tiles/PhotoTile.svelte';
import MovieTile from '$lib/components/tiles/MovieTile.svelte';
import DiscordTile from '$lib/components/tiles/DiscordTile.svelte';
import ClockTile from '$lib/components/tiles/ClockTile.svelte';
import DateTile from '$lib/components/tiles/DateTile.svelte';
import MessageTile from '$lib/components/tiles/MessageTile.svelte';
import RSSTile from '$lib/components/tiles/RSSTile.svelte';
import BookmarksTile from '$lib/components/tiles/BookmarksTile.svelte';
import AlertTile from '$lib/components/tiles/AlertTile.svelte';
import CalendarTile from '$lib/components/tiles/CalendarTile.svelte';
import JellyfinTile from '$lib/components/tiles/JellyfinTile.svelte';
import HDHomeRunTile from '$lib/components/tiles/HDHomeRunTile.svelte';
import PiholeTile from '$lib/components/tiles/PiholeTile.svelte';
import Game2048Tile from '$lib/components/tiles/Game2048Tile.svelte';
import WordleTile from '$lib/components/tiles/WordleTile.svelte';
import SystemMonitorTile from '$lib/components/tiles/SystemMonitorTile.svelte';
import ContainerTile from '$lib/components/tiles/ContainerTile.svelte';
import SynologyTile from '$lib/components/tiles/SynologyTile.svelte';
import AsusRouterTile from '$lib/components/tiles/AsusRouterTile.svelte';
import SportsTile from '$lib/components/tiles/SportsTile.svelte';
import SteamTile from '$lib/components/tiles/SteamTile.svelte';
import BF6Tile from '$lib/components/tiles/BF6Tile.svelte';
import GoodreadsTile from '$lib/components/tiles/GoodreadsTile.svelte';
import QBittorrentTile from '$lib/components/tiles/QBittorrentTile.svelte';
import SpeedtestTile from '$lib/components/tiles/SpeedtestTile.svelte';
import ChoresTile from '$lib/components/tiles/ChoresTile.svelte';
import ShoppingTile from '$lib/components/tiles/ShoppingTile.svelte';
import PackageTile from '$lib/components/tiles/PackageTile.svelte';
import NASATile from '$lib/components/tiles/NASATile.svelte';
import FlightsTile from '$lib/components/tiles/FlightsTile.svelte';
import MappingTile from '$lib/components/tiles/MappingTile.svelte';

import WeatherDetail from '$lib/components/details/WeatherDetail.svelte';
import AIDetail from '$lib/components/details/AIDetail.svelte';
import PhotoDetail from '$lib/components/details/PhotoDetail.svelte';
import MovieDetail from '$lib/components/details/MovieDetail.svelte';
import DiscordDetail from '$lib/components/details/DiscordDetail.svelte';
import ClockDetail from '$lib/components/details/ClockDetail.svelte';
import DateDetail from '$lib/components/details/DateDetail.svelte';
import MessageDetail from '$lib/components/details/MessageDetail.svelte';
import RSSDetail from '$lib/components/details/RSSDetail.svelte';
import BookmarksDetail from '$lib/components/details/BookmarksDetail.svelte';
import AlertDetail from '$lib/components/details/AlertDetail.svelte';
import CalendarDetail from '$lib/components/details/CalendarDetail.svelte';
import JellyfinDetail from '$lib/components/details/JellyfinDetail.svelte';
import HDHomeRunDetail from '$lib/components/details/HDHomeRunDetail.svelte';
import PiholeDetail from '$lib/components/details/PiholeDetail.svelte';
import Game2048Detail from '$lib/components/details/Game2048Detail.svelte';
import WordleDetail from '$lib/components/details/WordleDetail.svelte';
import SystemMonitorDetail from '$lib/components/details/SystemMonitorDetail.svelte';
import ContainerDetail from '$lib/components/details/ContainerDetail.svelte';
import SynologyDetail from '$lib/components/details/SynologyDetail.svelte';
import AsusRouterDetail from '$lib/components/details/AsusRouterDetail.svelte';
import SportsDetail from '$lib/components/details/SportsDetail.svelte';
import SteamDetail from '$lib/components/details/SteamDetail.svelte';
import BF6Detail from '$lib/components/details/BF6Detail.svelte';
import GoodreadsDetail from '$lib/components/details/GoodreadsDetail.svelte';
import QBittorrentDetail from '$lib/components/details/QBittorrentDetail.svelte';
import SpeedtestDetail from '$lib/components/details/SpeedtestDetail.svelte';
import ChoresDetail from '$lib/components/details/ChoresDetail.svelte';
import ShoppingDetail from '$lib/components/details/ShoppingDetail.svelte';
import PackageDetail from '$lib/components/details/PackageDetail.svelte';
import NASADetail from '$lib/components/details/NASADetail.svelte';
import FlightsDetail from '$lib/components/details/FlightsDetail.svelte';
import MappingDetail from '$lib/components/details/MappingDetail.svelte';

import ClockScreensaver from '$lib/components/screensaver/ClockScreensaver.svelte';
import DateScreensaver from '$lib/components/screensaver/DateScreensaver.svelte';
import CalendarScreensaver from '$lib/components/screensaver/CalendarScreensaver.svelte';
import WeatherScreensaver from '$lib/components/screensaver/WeatherScreensaver.svelte';
import FlightsScreensaver from '$lib/components/screensaver/FlightsScreensaver.svelte';

type TileComponent =
	| typeof WeatherTile
	| typeof AITile
	| typeof PhotoTile
	| typeof MovieTile
	| typeof DiscordTile
	| typeof ClockTile
	| typeof DateTile
	| typeof MessageTile
	| typeof RSSTile
	| typeof BookmarksTile
	| typeof AlertTile
	| typeof CalendarTile
	| typeof JellyfinTile
	| typeof HDHomeRunTile
	| typeof PiholeTile
	| typeof Game2048Tile
	| typeof WordleTile
	| typeof SystemMonitorTile
	| typeof ContainerTile
	| typeof SynologyTile
	| typeof AsusRouterTile
	| typeof SportsTile
	| typeof SteamTile
	| typeof BF6Tile
	| typeof GoodreadsTile
	| typeof QBittorrentTile
	| typeof SpeedtestTile
	| typeof ChoresTile
	| typeof ShoppingTile
	| typeof PackageTile
	| typeof NASATile
	| typeof FlightsTile
	| typeof MappingTile;

type DetailComponent =
	| typeof WeatherDetail
	| typeof AIDetail
	| typeof PhotoDetail
	| typeof MovieDetail
	| typeof DiscordDetail
	| typeof ClockDetail
	| typeof DateDetail
	| typeof MessageDetail
	| typeof RSSDetail
	| typeof BookmarksDetail
	| typeof AlertDetail
	| typeof CalendarDetail
	| typeof JellyfinDetail
	| typeof HDHomeRunDetail
	| typeof PiholeDetail
	| typeof Game2048Detail
	| typeof WordleDetail
	| typeof SystemMonitorDetail
	| typeof ContainerDetail
	| typeof SynologyDetail
	| typeof AsusRouterDetail
	| typeof SportsDetail
	| typeof SteamDetail
	| typeof BF6Detail
	| typeof GoodreadsDetail
	| typeof QBittorrentDetail
	| typeof SpeedtestDetail
	| typeof ChoresDetail
	| typeof ShoppingDetail
	| typeof PackageDetail
	| typeof NASADetail
	| typeof FlightsDetail
	| typeof MappingDetail;

export const TILE_COMPONENTS: Record<string, TileComponent> = {
	weather: WeatherTile,
	ai: AITile,
	photos: PhotoTile,
	movies: MovieTile,
	discord: DiscordTile,
	clock: ClockTile,
	date: DateTile,
	message: MessageTile,
	rss: RSSTile,
	bookmarks: BookmarksTile,
	alert: AlertTile,
	calendar: CalendarTile,
	calendar_caldav: CalendarTile,
	calendar_microsoft: CalendarTile,
	jellyfin: JellyfinTile,
	hdhomerun: HDHomeRunTile,
	pihole: PiholeTile,
	game2048: Game2048Tile,
	wordle: WordleTile,
	system_monitor: SystemMonitorTile,
	container: ContainerTile,
	synology: SynologyTile,
	asus_router: AsusRouterTile,
	sports: SportsTile,
	steam: SteamTile,
	bf6: BF6Tile,
	goodreads: GoodreadsTile,
	qbittorrent: QBittorrentTile,
	speedtest: SpeedtestTile,
	chores: ChoresTile,
	shopping: ShoppingTile,
	packages: PackageTile,
	nasa_apod: NASATile,
	flights: FlightsTile,
	mapping: MappingTile,
};

export const DETAIL_COMPONENTS: Record<string, DetailComponent> = {
	weather: WeatherDetail,
	ai: AIDetail,
	photos: PhotoDetail,
	movies: MovieDetail,
	discord: DiscordDetail,
	clock: ClockDetail,
	date: DateDetail,
	message: MessageDetail,
	rss: RSSDetail,
	bookmarks: BookmarksDetail,
	alert: AlertDetail,
	calendar: CalendarDetail,
	calendar_caldav: CalendarDetail,
	calendar_microsoft: CalendarDetail,
	jellyfin: JellyfinDetail,
	hdhomerun: HDHomeRunDetail,
	pihole: PiholeDetail,
	game2048: Game2048Detail,
	wordle: WordleDetail,
	system_monitor: SystemMonitorDetail,
	container: ContainerDetail,
	synology: SynologyDetail,
	asus_router: AsusRouterDetail,
	sports: SportsDetail,
	steam: SteamDetail,
	bf6: BF6Detail,
	goodreads: GoodreadsDetail,
	qbittorrent: QBittorrentDetail,
	speedtest: SpeedtestDetail,
	chores: ChoresDetail,
	shopping: ShoppingDetail,
	packages: PackageDetail,
	nasa_apod: NASADetail,
	flights: FlightsDetail,
	mapping: MappingDetail,
};

type ScreensaverComponent =
	| typeof ClockScreensaver
	| typeof DateScreensaver
	| typeof CalendarScreensaver
	| typeof WeatherScreensaver
	| typeof FlightsScreensaver;

// 'photos' is deliberately absent here: PhotoScreensaver needs a widget `id`
// to persist/restore its cursor, so ScreensaverContent.svelte renders it
// directly instead of through this generic (id-less) map.
export const SCREENSAVER_COMPONENTS: Record<string, ScreensaverComponent> = {
	clock: ClockScreensaver,
	date: DateScreensaver,
	calendar: CalendarScreensaver,
	calendar_caldav: CalendarScreensaver,
	calendar_microsoft: CalendarScreensaver,
	weather: WeatherScreensaver,
	flights: FlightsScreensaver,
};
