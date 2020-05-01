import xbmc
import xbmcaddon

import os
import requests
import requests_cache

from util import show_error

# define the cache file to reside in the ..\Kodi\userdata\addon_data\(your addon)
addonUserDataFolder = xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
art_availability_cache_file = xbmc.translatePath(os.path.join(addonUserDataFolder, 'requests_cache_arts'))

# cache expires after: 86400=1 day   604800=7 days
cached_requests = requests_cache.core.CachedSession(art_availability_cache_file, backend='sqlite',
                                                    expire_after=604800 * 2,
                                                    allowable_methods=('HEAD',),
                                                    allowable_codes=(200, 404),
                                                    old_data_on_error=True)

# Todo : tweak fallbacks and arts to have the best look in Kodi
#  TODO note which are safe to use and which can be missing

# Dictionary containing for each art type, a base_url for the art (to format with appid / img_icon_path afterwards), and a fallback art type.
arts_urls = {  # {0} is appid, {1} is a special path provided by steam api for the icon
    'poster': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{0}/library_600x900.jpg', 'fallback_media': 'landscape'},
    'landscape': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{0}//header.jpg', 'fallback_media': 'thumb'},
    'banner': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{0}/library_hero.jpg', 'fallback_media': 'thumb'},
    'thumb': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{0}/header.jpg', 'fallback_media': 'fanart'},
    'fanart': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{0}/page_bg_generated_v6b.jpg', 'fallback_media': None},
    'icon': {'base_url': 'https://steamcdn-a.akamaihd.net/steamcommunity/public/images/apps/{0}/{1}.jpg', 'fallback_media': None},
    'clearlogo': {'base_url': 'http://cdn.akamai.steamstatic.com/steam/apps/{0}/logo.png', 'fallback_media': None}  # No fallback possible for clearlogo
}


def is_art_url_available(url, timeout=2):
    """
    Sends a HEAD request to check if an online resource is available. Uses a cache mechanism to speed things up or serve offline.

    :param url: url to check availability
    :param timeout: timeout of the request in seconds. Default 2
    :return: boolean False if the status code is between 400&600 , True otherwise
    """
    result = False
    try:
        response = cached_requests.head(url, timeout=timeout)
        if not 400 <= response.status_code < 600:  # We consider valid any status codes belwo 400 or above 600
            result = True
    except IOError:
        result = False
    return result


def resolve_media_url(media_type, appid, img_icon_path=''):
    valid_media_url = None

    art_data = arts_urls.get(media_type, None)

    while valid_media_url is None and art_data is not None:
        art_url = art_data.get('base_url').format(appid, img_icon_path)
        if is_art_url_available(art_url):
            valid_media_url = art_url
        else:
            fallback_media_type = art_data.get("fallback", None)
            art_data = arts_urls.get(fallback_media_type, None)

    if valid_media_url is None:
        show_error(None, "Issue obtaining a media", False)
        return

    return valid_media_url
