import xbmc
import xbmcaddon

import os
from datetime import timedelta
import requests
import requests_cache

from .util import log

__addon__ = xbmcaddon.Addon()
artFallbackEnabled = __addon__.getSetting("enable-art-fallback") == 'true'  # Kodi stores boolean settings as strings
monthsBeforeArtsExpiration = int(__addon__.getSetting("arts-expire-after-months"))  # Default is 2 months

# define the cache file to reside in the ..\Kodi\userdata\addon_data\(your addon)
addonUserDataFolder = xbmc.translatePath(__addon__.getAddonInfo('profile'))
ART_AVAILABILITY_CACHE_FILE = xbmc.translatePath(os.path.join(addonUserDataFolder, 'requests_cache_arts'))

cached_requests = requests_cache.core.CachedSession(ART_AVAILABILITY_CACHE_FILE, backend='sqlite',
                                                    expire_after= timedelta(weeks=4*monthsBeforeArtsExpiration),
                                                    allowable_methods=('HEAD',), allowable_codes=(200, 404),
                                                    old_data_on_error=True,
                                                    fast_save=True)
# Existing Steam art types urls, to format to format with appid / img_icon_path
STEAM_ARTS_TYPES = {  # img_icon_path is provided by steam API to get the icon. https://developer.valvesoftware.com/wiki/Steam_Web_API#GetOwnedGames_.28v0001.29
    'poster': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/library_600x900.jpg',  # Can return 404
    'hero': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/library_hero.jpg',  # Can return 404
    'header': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg',
    'generated_bg': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/page_bg_generated_v6b.jpg',  # Auto generated background with a shade of blue.
    'icon': 'https://steamcdn-a.akamaihd.net/steamcommunity/public/images/apps/{appid}/{img_icon_path}.jpg',
    'clearlogo': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/logo.png'  # Can return 404
}

# Dictionary containing for each art type, a url for the art (to format with appid / img_icon_path afterwards), and a fallback art type.
# Having no fallback also means that the art url won't be tested
ARTS_ASSIGNMENTS = {
    'poster': {'url': STEAM_ARTS_TYPES['poster'], 'fallback': 'landscape'},
    'banner': {'url': STEAM_ARTS_TYPES['hero'], 'fallback': 'landscape'},
    'fanart': {'url': STEAM_ARTS_TYPES['hero'], 'fallback': 'fanart1'},
    'fanart1': {'url': STEAM_ARTS_TYPES['header'], 'fallback': None},
    'fanart2': {'url': STEAM_ARTS_TYPES['generated_bg'], 'fallback': None},  # Multiple fanart https://kodi.wiki/view/Artwork_types#fanart.23
    'landscape': {'url': STEAM_ARTS_TYPES['header'], 'fallback': None},
    'thumb': {'url': STEAM_ARTS_TYPES['header'], 'fallback': None},
    'icon': {'url': STEAM_ARTS_TYPES['icon'], 'fallback': None},
    'clearlogo': {'url': STEAM_ARTS_TYPES['clearlogo'], 'fallback': None}
}


def is_art_url_available(url, timeout=2):
    """
    Sends a HEAD request to check if an online resource is available. Uses a cache mechanism to speed things up or serve offline if a connection is unavailable.

    :param url: url to check availability
    :param timeout: timeout of the request in seconds. Default is 2
    :return: boolean False if the status code is between 400&600 , True otherwise
    """
    result = False
    try:
        response = cached_requests.head(url, timeout=timeout)
        if not 400 <= response.status_code < 600:  # We consider valid any status codes below 400 or above 600
            result = True
    except IOError:
        result = False
    return result


def resolve_art_url(art_type, appid, img_icon_path='', art_fallback_enabled=artFallbackEnabled):
    """
    Resolve the art url of a specified game/app, for a given art type defined in the :const:`ARTS_DATA` dictionary.
    Handles fallback to another art type if needed (ie the requested one is unavailable and fallback is enabled).

    :param art_type: a valid art type, defined in :const:`ARTS_DATA`
    :param appid: appid of the game/app we want to get the art for.
    :param img_icon_path: A path provided by steam to get the icon art url. https://developer.valvesoftware.com/wiki/Steam_Web_API#GetOwnedGames_.28v0001.29
    :param art_fallback_enabled: Whether to fall back to another art type if an art is unavailable. Defaults to the user addon settings, which default to true
    :return: resolved art URL. Can be the URL of another available art if .
    """
    valid_art_url = None
    requested_art = ARTS_ASSIGNMENTS.get(art_type, None)

    while valid_art_url is None and requested_art is not None:  # If the current media type is defined and we did not find a valid url yet
        art_url = requested_art.get('url').format(appid=appid, img_icon_path=img_icon_path)  # We replace "{appid}" and "{img_icon_path}" in the url
        fallback_art_type = requested_art.get("fallback", None)
        if (not art_fallback_enabled) or (fallback_art_type is None) or is_art_url_available(art_url):
            # If art fallback is disabled, or if there is no fallback defined, we directly assume the art url as valid.
            # Otherwise, if art fallback is enabled and there is a fallback defined, we check if is_art_url_available before proceeding
            valid_art_url = art_url
        else:  # If art fallback is enabled and art is not available, we set the current art data to the defined fallback, before retrying.
            requested_art = ARTS_ASSIGNMENTS.get(fallback_art_type, None)  # Art data will be None if the fallback_art_type does not exist in the art_urls dict

    if valid_art_url is None:  # If the previous loop could not find a valid media url among the defined art types
        log("Issue resolving media {0} for app id {1}".format(art_type, appid))

    return valid_art_url


def delete_cache():
    """
    Deletes the cache containing the data about which art types are available or not
    """
    os.remove(ART_AVAILABILITY_CACHE_FILE + ".sqlite")
