import xbmc
import xbmcaddon

import os
import requests
import requests_cache

from util import show_error

__addon__ = xbmcaddon.Addon()
artFallbackEnabled = __addon__.getSetting("enable-art-fallback") == 'true'  # Kodi stores boolean settings as strings
minutesBeforeArtsExpiration = int(__addon__.getSetting("arts-expire-after-minutes"))  # Default is 2 months

# define the cache file to reside in the ..\Kodi\userdata\addon_data\(your addon)
addonUserDataFolder = xbmc.translatePath(__addon__.getAddonInfo('profile'))
ART_AVAILABILITY_CACHE_FILE = xbmc.translatePath(os.path.join(addonUserDataFolder, 'requests_cache_arts'))

cached_requests = requests_cache.core.CachedSession(ART_AVAILABILITY_CACHE_FILE, backend='sqlite',
                                                    expire_after=60 * minutesBeforeArtsExpiration,
                                                    allowable_methods=('HEAD',), allowable_codes=(200, 404),
                                                    old_data_on_error=True,
                                                    fast_save=True)

# Dictionary containing for each art type, a base_url for the art (to format with appid / img_icon_path afterwards), and a fallback art type.
ARTS_DATA = {  # img_icon_path is a path provided by steam to get the icon. https://developer.valvesoftware.com/wiki/Steam_Web_API#GetOwnedGames_.28v0001.29
    'poster': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/library_600x900.jpg', 'fallback_media': 'landscape'},  # Can return 404
    'banner': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/library_hero.jpg', 'fallback_media': 'landscape'},  # Can return 404
    'landscape': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg', 'fallback_media': None},
    'thumb': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg', 'fallback_media': None},
    'fanart': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/library_hero.jpg', 'fallback_media': 'fanart2'},  # Can return 404
    'fanart2': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg', 'fallback_media': 'fanart3'},
    'fanart3': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/page_bg_generated_v6b.jpg', 'fallback_media': None},
    'icon': {'base_url': 'https://steamcdn-a.akamaihd.net/steamcommunity/public/images/apps/{appid}/{img_icon_path}.jpg', 'fallback_media': None},
    'clearlogo': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{appid}/logo.png', 'fallback_media': None}  # Can return 404
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
    requested_art_data = ARTS_DATA.get(art_type, None)

    while valid_art_url is None and requested_art_data is not None:  # If the current media type is defined and we did not find a valid url yet
        art_url = requested_art_data.get('base_url').format(appid=appid, img_icon_path=img_icon_path)  # We replace "{appid}" and "{img_icon_path}" in the url
        fallback_art_type = requested_art_data.get("fallback_media", None)
        if (not art_fallback_enabled) or (fallback_art_type is None) or is_art_url_available(art_url):
            # If art fallback is disabled, or if there is no fallback defined, we directly assume the art url as valid.
            # Otherwise, if art fallback is enabled and there is a fallback defined, we check if is_art_url_available before proceeding
            valid_art_url = art_url
        else:  # If art fallback is enabled and art is not available, we set the current art data to the defined fallback, before retrying.
            requested_art_data = ARTS_DATA.get(fallback_art_type, None)  # Art data will be None if the fallback_art_type does not exist in the art_urls dict

    if valid_art_url is None:  # If the previous loop could not find a valid media url among the defined art types
        show_error(None, "Issue obtaining a media", display_notification=False)
        return

    return valid_art_url


def delete_cache():
    """
    Deletes the cache containing the data about which art types are available or not
    """
    os.remove(ART_AVAILABILITY_CACHE_FILE + ".sqlite")
