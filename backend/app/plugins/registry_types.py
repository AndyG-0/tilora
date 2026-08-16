"""Maps a widget's `type` string (dashboard.yaml or a UI-added widget) to its
plugin class.

Lives outside `main.py` so `app/api/widgets.py` can import it too, without a
circular import between the two.
"""

from __future__ import annotations

from app.plugins.ai_insights.plugin import AIInsightsPlugin
from app.plugins.alert.plugin import AlertPlugin
from app.plugins.asus_router.plugin import AsusRouterPlugin
from app.plugins.bf6.plugin import BF6Plugin
from app.plugins.bookmarks.plugin import BookmarksPlugin
from app.plugins.calendar.plugin import CaldavCalendarPlugin, CalendarPlugin, MicrosoftCalendarPlugin
from app.plugins.chores.plugin import ChoresPlugin
from app.plugins.clock.plugin import ClockPlugin
from app.plugins.container.plugin import ContainerPlugin
from app.plugins.date.plugin import DatePlugin
from app.plugins.discord.plugin import DiscordPlugin
from app.plugins.flights.plugin import FlightsPlugin
from app.plugins.game2048.plugin import Game2048Plugin
from app.plugins.goodreads.plugin import GoodreadsPlugin
from app.plugins.hdhomerun.plugin import HDHomeRunPlugin
from app.plugins.jellyfin.plugin import JellyfinPlugin
from app.plugins.mapping.plugin import MappingPlugin
from app.plugins.message.plugin import MessagePlugin
from app.plugins.movies.plugin import MoviesPlugin
from app.plugins.nasa_apod.plugin import NASAApodPlugin
from app.plugins.packages.plugin import PackagesPlugin
from app.plugins.photos.plugin import PhotosPlugin
from app.plugins.pihole.plugin import PiholePlugin
from app.plugins.qbittorrent.plugin import QBittorrentPlugin
from app.plugins.rss.plugin import RSSPlugin
from app.plugins.shopping.plugin import ShoppingPlugin
from app.plugins.speedtest.plugin import SpeedtestPlugin
from app.plugins.sports.plugin import SportsPlugin
from app.plugins.steam.plugin import SteamPlugin
from app.plugins.synology.plugin import SynologyPlugin
from app.plugins.system_monitor.plugin import SystemMonitorPlugin
from app.plugins.weather.plugin import WeatherPlugin
from app.plugins.wordle.plugin import WordlePlugin

PLUGIN_CLASSES_BY_TYPE = {
    "weather": WeatherPlugin,
    "ai": AIInsightsPlugin,
    "photos": PhotosPlugin,
    "movies": MoviesPlugin,
    "discord": DiscordPlugin,
    "jellyfin": JellyfinPlugin,
    "hdhomerun": HDHomeRunPlugin,
    "pihole": PiholePlugin,
    "clock": ClockPlugin,
    "date": DatePlugin,
    "message": MessagePlugin,
    "bookmarks": BookmarksPlugin,
    "rss": RSSPlugin,
    "flights": FlightsPlugin,
    "mapping": MappingPlugin,
    "chores": ChoresPlugin,
    "shopping": ShoppingPlugin,
    "alert": AlertPlugin,
    "calendar": CalendarPlugin,
    "calendar_caldav": CaldavCalendarPlugin,
    "calendar_microsoft": MicrosoftCalendarPlugin,
    "game2048": Game2048Plugin,
    "wordle": WordlePlugin,
    "system_monitor": SystemMonitorPlugin,
    "container": ContainerPlugin,
    "sports": SportsPlugin,
    "steam": SteamPlugin,
    "bf6": BF6Plugin,
    "synology": SynologyPlugin,
    "asus_router": AsusRouterPlugin,
    "goodreads": GoodreadsPlugin,
    "qbittorrent": QBittorrentPlugin,
    "speedtest": SpeedtestPlugin,
    "packages": PackagesPlugin,
    "nasa_apod": NASAApodPlugin,
}
