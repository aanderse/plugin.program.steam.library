"""
Fetch and cache game metadata from Steam Store API.

Rate limited to respect Steam's API limits (~200 requests per 5 minutes).
Metadata is fetched by a background service and cached for 30 days.
"""
import json
import os
import sqlite3
import time

import requests
import xbmcaddon
import xbmcvfs

from .util import log

__addon__ = xbmcaddon.Addon()

# Cache setup
addonUserDataFolder = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))
METADATA_CACHE_FILE = xbmcvfs.translatePath(os.path.join(addonUserDataFolder, 'metadata_cache.sqlite'))

# Cache duration: 30 days in seconds
CACHE_DURATION = 30 * 24 * 60 * 60

# Steam Store API
STEAM_STORE_API = 'https://store.steampowered.com/api/appdetails'

# Rate limiting: Steam allows ~200 requests per 5 minutes
# We'll be conservative: 1 request per 2 seconds
RATE_LIMIT_DELAY = 2.0  # seconds between requests


def _get_last_request_time():
    """Get the last API request timestamp from the database."""
    try:
        conn = sqlite3.connect(METADATA_CACHE_FILE)
        cursor = conn.execute(
            "SELECT value FROM settings WHERE key = 'last_request_time'"
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return float(row[0])
    except:
        pass
    return 0


def _set_last_request_time(timestamp):
    """Store the last API request timestamp in the database."""
    try:
        conn = sqlite3.connect(METADATA_CACHE_FILE)
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('last_request_time', ?)",
            (str(timestamp),)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log("Failed to store last_request_time: {}".format(e))


def get_time_until_next_request():
    """Get seconds until we can make another API request. Returns 0 if ready."""
    last_time = _get_last_request_time()
    elapsed = time.time() - last_time
    if elapsed >= RATE_LIMIT_DELAY:
        return 0
    return RATE_LIMIT_DELAY - elapsed


def can_make_request():
    """Check if we can make an API request without violating rate limits."""
    return get_time_until_next_request() <= 0


def init_cache():
    """Initialize the metadata cache database."""
    os.makedirs(os.path.dirname(METADATA_CACHE_FILE), exist_ok=True)
    conn = sqlite3.connect(METADATA_CACHE_FILE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            appid TEXT PRIMARY KEY,
            data TEXT,
            fetched_at INTEGER
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()


def get_cached_metadata(appid):
    """Get cached metadata for an appid, or None if not cached/expired."""
    try:
        conn = sqlite3.connect(METADATA_CACHE_FILE)
        cursor = conn.execute(
            'SELECT data, fetched_at FROM metadata WHERE appid = ?',
            (str(appid),)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            data, fetched_at = row
            # Check if cache is still valid
            if time.time() - fetched_at < CACHE_DURATION:
                return json.loads(data)
    except:
        pass
    return None


def cache_metadata(appid, data):
    """Store metadata in cache."""
    try:
        conn = sqlite3.connect(METADATA_CACHE_FILE)
        conn.execute(
            'INSERT OR REPLACE INTO metadata (appid, data, fetched_at) VALUES (?, ?, ?)',
            (str(appid), json.dumps(data), int(time.time()))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log("Failed to cache metadata for {}: {}".format(appid, e))


def fetch_metadata_from_api(appid):
    """Fetch metadata for a single game from Steam Store API."""
    # Record the request time BEFORE making the request
    _set_last_request_time(time.time())

    try:
        response = requests.get(
            STEAM_STORE_API,
            params={'appids': appid, 'l': 'english'},
            timeout=10
        )
        response.raise_for_status()

        result = response.json()
        app_data = result.get(str(appid), {})

        if app_data.get('success') and 'data' in app_data:
            data = app_data['data']
            # Extract the fields we care about
            metadata = {
                'short_description': data.get('short_description', ''),
                'developers': data.get('developers', []),
                'publishers': data.get('publishers', []),
                'genres': [g['description'] for g in data.get('genres', [])],
                'release_date': data.get('release_date', {}).get('date', ''),
                'metacritic': data.get('metacritic', {}).get('score'),
                'categories': [c['description'] for c in data.get('categories', [])],
            }
            return metadata
    except Exception as e:
        log("Failed to fetch metadata for {}: {}".format(appid, e))

    return None


def get_metadata(appid):
    """
    Get cached metadata for a game.
    Returns dict with metadata or empty dict if not cached.
    Does NOT fetch from API - that's handled by the background service.
    """
    cached = get_cached_metadata(appid)
    return cached if cached is not None else {}


def get_metadata_for_games(appids):
    """
    Get cached metadata for multiple games.
    Returns dict mapping appid -> metadata (empty dict if not cached).
    Does NOT fetch from API - that's handled by the background service.

    :param appids: list of appids to fetch
    :return: dict mapping appid -> metadata
    """
    init_cache()
    results = {}
    cached_count = 0

    for appid in appids:
        appid = str(appid)
        cached = get_cached_metadata(appid)
        if cached is not None:
            results[appid] = cached
            cached_count += 1
        else:
            results[appid] = {}

    log("Metadata: {} cached, {} pending".format(cached_count, len(appids) - cached_count))
    return results


def get_uncached_appids(appids):
    """
    Get list of appids that don't have cached metadata.
    Used by the background service to know what to fetch.

    :param appids: list of appids to check
    :return: list of appids needing metadata
    """
    init_cache()
    uncached = []

    for appid in appids:
        appid = str(appid)
        if get_cached_metadata(appid) is None:
            uncached.append(appid)

    return uncached


def fetch_and_cache_metadata(appid):
    """
    Fetch metadata for a single game and cache it.
    Called by the background service.
    Returns True if successful, False otherwise.
    """
    if not can_make_request():
        return False

    metadata = fetch_metadata_from_api(appid)

    if metadata:
        cache_metadata(appid, metadata)
        return True

    # Cache empty result to avoid re-fetching failed games
    cache_metadata(appid, {})
    return True


def delete_cache():
    """Delete the metadata cache."""
    try:
        if os.path.exists(METADATA_CACHE_FILE):
            os.remove(METADATA_CACHE_FILE)
            log("Metadata cache deleted")
    except Exception as e:
        log("Failed to delete metadata cache: {}".format(e))
