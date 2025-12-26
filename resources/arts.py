import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

import requests
import requests_cache
import xbmcaddon
import xbmcvfs

from .util import log

__addon__ = xbmcaddon.Addon()

# Cache setup for HEAD requests
addonUserDataFolder = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))
ART_CACHE_FILE = xbmcvfs.translatePath(os.path.join(addonUserDataFolder, 'requests_cache_arts'))

# Cache HEAD request results for 2 months
cached_session = requests_cache.CachedSession(
    ART_CACHE_FILE,
    backend='sqlite',
    expire_after=timedelta(weeks=8),
    allowable_methods=('HEAD',),
    allowable_codes=(200, 404),
    old_data_on_error=True
)

# Steam art URL templates
STEAM_ARTS = {
    'poster': 'https://cdn.akamai.steamstatic.com/steam/apps/{appid}/library_600x900.jpg',
    'hero': 'https://cdn.akamai.steamstatic.com/steam/apps/{appid}/library_hero.jpg',
    'header': 'https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg',
    'logo': 'https://cdn.akamai.steamstatic.com/steam/apps/{appid}/logo.png',
    'icon': 'https://steamcdn-a.akamaihd.net/steamcommunity/public/images/apps/{appid}/{img_icon_path}.jpg',
}

# Map Kodi art types to Steam art (primary -> fallback)
# header.jpg is available for all games, so it's the ultimate fallback
ART_TYPE_CONFIG = {
    'poster': {'primary': 'poster', 'fallback': 'header'},
    'banner': {'primary': 'hero', 'fallback': 'header'},
    'fanart': {'primary': 'hero', 'fallback': 'header'},
    'fanart1': {'primary': 'header', 'fallback': None},
    'fanart2': {'primary': 'header', 'fallback': None},
    'landscape': {'primary': 'header', 'fallback': None},
    'thumb': {'primary': 'header', 'fallback': None},
    'icon': {'primary': 'icon', 'fallback': None},
    'clearlogo': {'primary': 'logo', 'fallback': None},
}


def check_url_exists(url, timeout=2):
    """
    Check if a URL exists (returns 200). Results are cached.
    """
    try:
        response = cached_session.head(url, timeout=timeout)
        return response.status_code == 200
    except:
        return False


def get_art_url(art_key, appid, img_icon_path=''):
    """Get a formatted Steam art URL."""
    template = STEAM_ARTS.get(art_key)
    if not template:
        return None
    return template.format(appid=appid, img_icon_path=img_icon_path)


def resolve_art_for_game(appid, img_icon_path=''):
    """
    Resolve all art URLs for a single game, checking availability and using fallbacks.
    Returns a dict of {art_type: url}.
    """
    art_dict = {}
    urls_to_check = []

    # Build list of primary URLs that need checking (have fallbacks)
    for art_type, config in ART_TYPE_CONFIG.items():
        primary_url = get_art_url(config['primary'], appid, img_icon_path)
        fallback_key = config.get('fallback')

        if fallback_key:
            # This art type has a fallback, so we need to check if primary exists
            urls_to_check.append((art_type, primary_url, fallback_key))
        else:
            # No fallback, just use the primary URL directly
            art_dict[art_type] = primary_url

    # Check all primary URLs that have fallbacks
    for art_type, primary_url, fallback_key in urls_to_check:
        if check_url_exists(primary_url):
            art_dict[art_type] = primary_url
        else:
            art_dict[art_type] = get_art_url(fallback_key, appid, img_icon_path)

    return art_dict


def resolve_art_for_all_games(games):
    """
    Resolve art URLs for all games in parallel.

    :param games: list of game dicts with 'appid' and 'img_icon_url' keys
    :return: dict mapping appid -> art_dict
    """
    start_time = time.time()

    # First, collect all URLs that need checking
    urls_to_check = set()
    game_art_info = []  # (appid, img_icon_path, [(art_type, primary_url, fallback_key), ...])

    for game in games:
        appid = str(game['appid'])
        img_icon_path = game.get('img_icon_url', '')

        art_checks = []
        for art_type, config in ART_TYPE_CONFIG.items():
            if config.get('fallback'):
                primary_url = get_art_url(config['primary'], appid, img_icon_path)
                urls_to_check.add(primary_url)
                art_checks.append((art_type, primary_url, config['fallback']))

        game_art_info.append((appid, img_icon_path, art_checks))

    # Check all URLs in parallel
    url_exists = {}
    check_start = time.time()

    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_url = {executor.submit(check_url_exists, url): url for url in urls_to_check}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                url_exists[url] = future.result()
            except:
                url_exists[url] = False

    log("Checked {} URLs in {:.2f}s".format(len(urls_to_check), time.time() - check_start))

    # Build art dictionaries using check results
    results = {}
    for appid, img_icon_path, art_checks in game_art_info:
        art_dict = {}

        # Add art types that don't need checking
        for art_type, config in ART_TYPE_CONFIG.items():
            if not config.get('fallback'):
                art_dict[art_type] = get_art_url(config['primary'], appid, img_icon_path)

        # Add art types that were checked
        for art_type, primary_url, fallback_key in art_checks:
            if url_exists.get(primary_url, False):
                art_dict[art_type] = primary_url
            else:
                art_dict[art_type] = get_art_url(fallback_key, appid, img_icon_path)

        results[appid] = art_dict

    log("Resolved art for {} games in {:.2f}s".format(len(games), time.time() - start_time))
    return results


def resolve_art_url(art_type, appid, img_icon_path=''):
    """
    Resolve a single art URL (legacy interface).
    For better performance, use resolve_art_for_all_games() instead.
    """
    config = ART_TYPE_CONFIG.get(art_type)
    if not config:
        return None

    primary_url = get_art_url(config['primary'], appid, img_icon_path)
    fallback_key = config.get('fallback')

    if fallback_key and not check_url_exists(primary_url):
        return get_art_url(fallback_key, appid, img_icon_path)

    return primary_url


def delete_cache():
    """Delete the art availability cache."""
    try:
        cached_session.cache.clear()
        log("Art cache cleared successfully")
    except Exception as e:
        log("Failed to clear art cache: {}".format(e))
        try:
            os.remove(ART_CACHE_FILE + ".sqlite")
            log("Art cache file deleted")
        except:
            log("Failed to delete art cache file")
