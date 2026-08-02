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
import AlertTile from '$lib/components/tiles/AlertTile.svelte';
import CalendarTile from '$lib/components/tiles/CalendarTile.svelte';
import JellyfinTile from '$lib/components/tiles/JellyfinTile.svelte';
import HDHomeRunTile from '$lib/components/tiles/HDHomeRunTile.svelte';
import PiholeTile from '$lib/components/tiles/PiholeTile.svelte';
import Game2048Tile from '$lib/components/tiles/Game2048Tile.svelte';
import SystemMonitorTile from '$lib/components/tiles/SystemMonitorTile.svelte';
import DockerTile from '$lib/components/tiles/DockerTile.svelte';
import PodmanTile from '$lib/components/tiles/PodmanTile.svelte';
import SynologyTile from '$lib/components/tiles/SynologyTile.svelte';
import AsusRouterTile from '$lib/components/tiles/AsusRouterTile.svelte';
import SportsTile from '$lib/components/tiles/SportsTile.svelte';
import SteamTile from '$lib/components/tiles/SteamTile.svelte';
import BF6Tile from '$lib/components/tiles/BF6Tile.svelte';
import GoodreadsTile from '$lib/components/tiles/GoodreadsTile.svelte';

import WeatherDetail from '$lib/components/details/WeatherDetail.svelte';
import AIDetail from '$lib/components/details/AIDetail.svelte';
import PhotoDetail from '$lib/components/details/PhotoDetail.svelte';
import MovieDetail from '$lib/components/details/MovieDetail.svelte';
import DiscordDetail from '$lib/components/details/DiscordDetail.svelte';
import ClockDetail from '$lib/components/details/ClockDetail.svelte';
import DateDetail from '$lib/components/details/DateDetail.svelte';
import MessageDetail from '$lib/components/details/MessageDetail.svelte';
import RSSDetail from '$lib/components/details/RSSDetail.svelte';
import AlertDetail from '$lib/components/details/AlertDetail.svelte';
import CalendarDetail from '$lib/components/details/CalendarDetail.svelte';
import JellyfinDetail from '$lib/components/details/JellyfinDetail.svelte';
import HDHomeRunDetail from '$lib/components/details/HDHomeRunDetail.svelte';
import PiholeDetail from '$lib/components/details/PiholeDetail.svelte';
import Game2048Detail from '$lib/components/details/Game2048Detail.svelte';
import SystemMonitorDetail from '$lib/components/details/SystemMonitorDetail.svelte';
import DockerDetail from '$lib/components/details/DockerDetail.svelte';
import PodmanDetail from '$lib/components/details/PodmanDetail.svelte';
import SynologyDetail from '$lib/components/details/SynologyDetail.svelte';
import AsusRouterDetail from '$lib/components/details/AsusRouterDetail.svelte';
import SportsDetail from '$lib/components/details/SportsDetail.svelte';
import SteamDetail from '$lib/components/details/SteamDetail.svelte';
import BF6Detail from '$lib/components/details/BF6Detail.svelte';
import GoodreadsDetail from '$lib/components/details/GoodreadsDetail.svelte';

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
	| typeof AlertTile
	| typeof CalendarTile
	| typeof JellyfinTile
	| typeof HDHomeRunTile
	| typeof PiholeTile
	| typeof Game2048Tile
	| typeof SystemMonitorTile
	| typeof DockerTile
	| typeof PodmanTile
	| typeof SynologyTile
	| typeof AsusRouterTile
	| typeof SportsTile
	| typeof SteamTile
	| typeof BF6Tile
	| typeof GoodreadsTile;

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
	| typeof AlertDetail
	| typeof CalendarDetail
	| typeof JellyfinDetail
	| typeof HDHomeRunDetail
	| typeof PiholeDetail
	| typeof Game2048Detail
	| typeof SystemMonitorDetail
	| typeof DockerDetail
	| typeof PodmanDetail
	| typeof SynologyDetail
	| typeof AsusRouterDetail
	| typeof SportsDetail
	| typeof SteamDetail
	| typeof BF6Detail
	| typeof GoodreadsDetail;

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
	alert: AlertTile,
	calendar: CalendarTile,
	calendar_caldav: CalendarTile,
	calendar_microsoft: CalendarTile,
	jellyfin: JellyfinTile,
	hdhomerun: HDHomeRunTile,
	pihole: PiholeTile,
	game2048: Game2048Tile,
	system_monitor: SystemMonitorTile,
	docker: DockerTile,
	podman: PodmanTile,
	synology: SynologyTile,
	asus_router: AsusRouterTile,
	sports: SportsTile,
	steam: SteamTile,
	bf6: BF6Tile,
	goodreads: GoodreadsTile,
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
	alert: AlertDetail,
	calendar: CalendarDetail,
	calendar_caldav: CalendarDetail,
	calendar_microsoft: CalendarDetail,
	jellyfin: JellyfinDetail,
	hdhomerun: HDHomeRunDetail,
	pihole: PiholeDetail,
	game2048: Game2048Detail,
	system_monitor: SystemMonitorDetail,
	docker: DockerDetail,
	podman: PodmanDetail,
	synology: SynologyDetail,
	asus_router: AsusRouterDetail,
	sports: SportsDetail,
	steam: SteamDetail,
	bf6: BF6Detail,
	goodreads: GoodreadsDetail,
};
