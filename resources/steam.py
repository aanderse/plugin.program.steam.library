import os
import sys
import shlex
import subprocess

import xbmc
import xbmcaddon
import xbmcplugin

import requests
import requests_cache

from .util import log

__addon__ = xbmcaddon.Addon()
minutesBeforeGamesListsExpiration = int(__addon__.getSetting("games-expire-after-minutes"))  # Default is 3 days

# define the cache file to reside in the ..\Kodi\userdata\addon_data\(your addon)
addonUserDataFolder = xbmc.translatePath(__addon__.getAddonInfo('profile'))
STEAM_GAMES_CACHE_FILE = xbmc.translatePath(os.path.join(addonUserDataFolder, 'requests_cache_games'))

# cache expires after: 86400=1 day   604800=7 days
cached_requests = requests_cache.core.CachedSession(STEAM_GAMES_CACHE_FILE, backend='sqlite',
                                                    expire_after=60 * minutesBeforeGamesListsExpiration,
                                                    old_data_on_error=True)


def install(steam_exe_path, appid):
    """
    Calls Steam to install a game/app. This will display Steam's game install prompt, which displays install configurations and asks for confirmation.

    :param steam_exe_path: path to the steam executable
    :param appid: appid of the game/app to install
    """
    log('executing ' + steam_exe_path + ' steam://install/' + appid)
    # https://developer.valvesoftware.com/wiki/Steam_browser_protocol
    subprocess.call([steam_exe_path, 'steam://install/' + appid])


def run(steam_exe_path, steam_launch_args, appid):
    """
    Calls Steam to run a game/app. This will run it, or in not installed display Steam install prompt

    :param steam_exe_path: path to the steam executable
    :param steam_launch_args: A string of Steam launch arguments (format "-arg1 -arg2 ...")
    :param appid: appid of the game/app to run
    """
    user_args = shlex.split(steam_launch_args)
    log('executing ' + steam_exe_path + ' ' + steam_launch_args + ' steam://rungameid/' + appid)

    # https://developer.valvesoftware.com/wiki/Steam_browser_protocol
    subprocess.call([steam_exe_path] + user_args + ['steam://rungameid/' + appid])  # Concatenate the arrays into one


def get_user_games(steam_api_key, steam_user_id, recent_only=False):
    """
    Queries the Steam Web API for a full list of steam applications/games that belong to a user, along with the games details and playtime

    :param steam_api_key: A steam API key with access to the Steam Web API
    :param steam_user_id: steam id of the user we want to get the games list for.
        To access their informations, their steam profile must be public, or the Steam API Key provided must belong to that user.
    :param recent_only: A boolean indicating whether to obtain only the recently played games (true) or all owned games (false, default)
    :returns: A dictionary containing a game_count value, along with a games array containing details for each individual game or app.
    :raises:
        :class:IOError: request.RequestException raised when there is an issue querying the web api for any reason.

    :example:
    >>> get_user_games("myAPIKey","76561197960434622")#Random profile number
        {
            "game_count": 1,
            "games": [
                {
                    "appid": 400,
                    "name": "Portal"
                    "playtime_forever": 253,
                    "playtime_2weeks": 172,#Key only present if the game was recently played
                    "img_icon_url": "cfa928ab4119dd137e50d728e8fe703e4e970aff",
                    "img_logo_url": "4184d4c0d915bd3a45210667f7b25361352acd8f",
                    "has_community_visible_stats": true,
                    "playtime_windows_forever": 0,
                    "playtime_mac_forever": 0,
                    "playtime_linux_forever": 0
                }
            ]
        }
    """

    if recent_only:
        # https://developer.valvesoftware.com/wiki/Steam_Web_API#GetRecentlyPlayedGames_.28v0001.29
        api_url = 'http://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/'
    else:
        # https://developer.valvesoftware.com/wiki/Steam_Web_API#GetOwnedGames_.28v0001.29
        api_url = 'https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/'

    # We send a request to the API, including needed parameters and "include_appinfo" so that game details are returned with the response.
    response = cached_requests.get(url=api_url,
                                   params={'key': steam_api_key,
                                           'steamid': steam_user_id,
                                           'include_appinfo': 1,
                                           'format': 'json'},
                                   timeout=5)

    response.raise_for_status()  # If the status code indicates an error, raise a HTTPError, which is itself a RequestException, based on the builtin IOError
    response_data = response.json().get('response', {})
    return response_data.get('games', {})


def delete_cache():
    os.remove(STEAM_GAMES_CACHE_FILE + ".sqlite")
