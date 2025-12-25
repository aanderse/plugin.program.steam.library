"""
Background service for fetching game metadata from Steam Store API.

Runs in the background and progressively fetches metadata for games
that don't have cached data, respecting Steam's rate limits.

Priority order:
1. Recently played games
2. Installed games
3. All other owned games
"""
import os

import xbmc
import xbmcaddon

from resources import metadata
from resources import registry
from resources import steam
from resources.util import log

__addon__ = xbmcaddon.Addon()

# How often to refresh the game list to catch new purchases (seconds)
REFRESH_INTERVAL = 600  # 10 minutes


def credentials_available():
    """Check if Steam credentials are configured."""
    return (
        __addon__.getSetting('steam-id') != '' and
        __addon__.getSetting('steam-key') != ''
    )


def get_priority_ordered_appids():
    """
    Get all appids ordered by priority:
    1. Recently played games
    2. Installed games (not already in recently played)
    3. All other games

    Returns list of appid strings, or empty list on failure.
    """
    steam_key = __addon__.getSetting('steam-key')
    steam_id = __addon__.getSetting('steam-id')
    steam_path = __addon__.getSetting('steam-path')

    # Get all games
    try:
        all_games = steam.get_user_games(steam_key, steam_id)
        all_appids = {str(game['appid']) for game in all_games}
    except Exception as e:
        log("Service: Failed to get user games: {}".format(e))
        return []

    if not all_appids:
        return []

    # Get recently played appids
    recent_appids = set()
    try:
        recent_games = steam.get_user_games(steam_key, steam_id, recent_only=True)
        recent_appids = {str(game['appid']) for game in recent_games}
    except Exception as e:
        log("Service: Failed to get recently played games: {}".format(e))

    # Get installed appids
    installed_appids = set()
    if steam_path and os.path.isdir(steam_path):
        try:
            installed_appids = set(registry.get_installed_steam_apps(steam_path))
        except Exception as e:
            log("Service: Failed to get installed games: {}".format(e))

    # Build ordered list
    ordered = []

    # 1. Recently played first
    for appid in recent_appids:
        if appid in all_appids:
            ordered.append(appid)

    # 2. Installed games (not already added)
    added = set(ordered)
    for appid in installed_appids:
        if appid in all_appids and appid not in added:
            ordered.append(appid)
            added.add(appid)

    # 3. Everything else
    for appid in all_appids:
        if appid not in added:
            ordered.append(appid)

    return ordered


def run_service():
    """Main service loop."""
    monitor = xbmc.Monitor()
    log("Steam Library metadata service started")

    # Wait a bit for Kodi to fully start
    if monitor.waitForAbort(10):
        return

    metadata.init_cache()

    while not monitor.abortRequested():
        # Check if credentials are available
        if not credentials_available():
            log("Service: Waiting for Steam credentials...")
            if monitor.waitForAbort(30):
                break
            continue

        # Get priority-ordered list of appids
        appids = get_priority_ordered_appids()
        if not appids:
            log("Service: No games found, waiting...")
            if monitor.waitForAbort(60):
                break
            continue

        # Find games needing metadata
        uncached = metadata.get_uncached_appids(appids)

        if not uncached:
            log("Service: All {} games have cached metadata, waiting...".format(len(appids)))
            if monitor.waitForAbort(REFRESH_INTERVAL):
                break
            continue

        log("Service: {} games need metadata (priority ordered)".format(len(uncached)))

        # Process games until we need to refresh or abort
        games_fetched = 0
        last_refresh = 0

        for appid in uncached:
            if monitor.abortRequested():
                break

            # Check if it's time to refresh the game list
            elapsed = games_fetched * metadata.RATE_LIMIT_DELAY
            if elapsed - last_refresh >= REFRESH_INTERVAL:
                log("Service: Refreshing game list...")
                last_refresh = elapsed
                # Break to outer loop to get fresh priority list
                break

            # Wait for rate limit
            wait_time = metadata.get_time_until_next_request()
            if wait_time > 0:
                if monitor.waitForAbort(wait_time):
                    break

            # Fetch and cache
            log("Service: Fetching metadata for appid {}".format(appid))
            metadata.fetch_and_cache_metadata(appid)
            games_fetched += 1

    log("Steam Library metadata service stopped")


if __name__ == '__main__':
    run_service()
