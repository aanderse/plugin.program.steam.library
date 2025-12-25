"""
Get installed Steam games across platforms.

Supports:
- Linux: ~/.steam, ~/.local/share/Steam
- macOS: ~/Library/Application Support/Steam
- Windows: Registry + Program Files
"""

import os
import sys

from .util import log, show_error

# Add bundled libraries to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
import vdf

if os.name == 'nt':
    import winreg


def get_default_steam_paths():
    """
    Returns a list of possible Steam installation paths for the current platform.
    Used as fallback when steam-path setting is not configured.
    """
    paths = []

    if sys.platform == 'darwin':
        # macOS
        paths.append(os.path.expanduser('~/Library/Application Support/Steam'))
    elif os.name == 'nt':
        # Windows - try to get from registry first
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
            steam_path, _ = winreg.QueryValueEx(key, 'SteamPath')
            winreg.CloseKey(key)
            if steam_path:
                paths.append(steam_path)
        except WindowsError:
            pass
        # Fallback paths
        paths.extend([
            os.path.expandvars(r'%ProgramFiles(x86)%\Steam'),
            os.path.expandvars(r'%ProgramFiles%\Steam'),
        ])
    else:
        # Linux and other Unix-like systems
        paths.extend([
            os.path.expanduser('~/.steam/steam'),
            os.path.expanduser('~/.steam'),
            os.path.expanduser('~/.local/share/Steam'),
        ])

    return paths


def find_libraryfolders_vdf(steam_path):
    """
    Finds the libraryfolders.vdf file given a Steam path.
    Returns the path if found, None otherwise.
    """
    # Handle symlinks (common on Linux where ~/.steam/steam -> ~/.local/share/Steam)
    if os.path.islink(steam_path):
        steam_path = os.path.realpath(steam_path)

    possible_locations = [
        os.path.join(steam_path, 'steamapps', 'libraryfolders.vdf'),
        os.path.join(steam_path, 'steam', 'steamapps', 'libraryfolders.vdf'),
        os.path.join(steam_path, 'Steam', 'steamapps', 'libraryfolders.vdf'),
    ]

    for path in possible_locations:
        if os.path.isfile(path):
            return path

    return None


def is_installed_win(app_id):
    """
    Gets whether an app with the given app id is installed, on Windows.
    :param app_id: app_id to check
    :return: True if the app is installed, false otherwise
    """
    try:
        app = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam\Apps\{}'.format(app_id))
        for i in range(winreg.QueryInfoKey(app)[1]):
            name, value, _ = winreg.EnumValue(app, i)
            if name == 'Installed':
                winreg.CloseKey(app)
                return value == 1
        winreg.CloseKey(app)
    except WindowsError:
        pass
    return False


def get_installed_steam_apps(steam_path):
    """
    Obtains the Steam games/apps installed on the computer.
    :param steam_path: Path to the Steam folder (from settings, or auto-detected)
    :return: a list of appids that are installed.
    """
    installed_apps = []

    # Build list of paths to try: user setting first, then defaults
    paths_to_try = []
    if steam_path and os.path.isdir(steam_path):
        paths_to_try.append(steam_path)
    paths_to_try.extend(get_default_steam_paths())

    # Windows: Try registry first
    if os.name == 'nt':
        try:
            apps = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam\Apps')
            num_apps = winreg.QueryInfoKey(apps)[0]
            log("Found {} apps in Windows registry".format(num_apps))
            for i in range(num_apps):
                app_id = winreg.EnumKey(apps, i)
                if is_installed_win(app_id):
                    installed_apps.append(app_id)
            winreg.CloseKey(apps)
            return installed_apps
        except WindowsError:
            log("Windows registry method failed, falling back to libraryfolders.vdf")

    # Try libraryfolders.vdf method (all platforms)
    for path in paths_to_try:
        libraryfolders_path = find_libraryfolders_vdf(path)
        if libraryfolders_path:
            try:
                with open(libraryfolders_path, 'r', encoding='utf-8') as f:
                    data = vdf.load(f)

                libraryfolders = data.get('libraryfolders', {})

                # Each library folder entry (0, 1, 2, etc.) contains an 'apps' dict
                for folder_id, folder_info in libraryfolders.items():
                    if isinstance(folder_info, dict) and 'apps' in folder_info:
                        installed_apps.extend(folder_info['apps'].keys())

                log("Found {} installed apps via {}".format(len(installed_apps), libraryfolders_path))
                return installed_apps

            except (SyntaxError, IOError, KeyError) as e:
                log("Error reading {}: {}".format(libraryfolders_path, e))
                continue

    show_error(
        FileNotFoundError("libraryfolders.vdf not found"),
        "Could not find Steam library folders. Please check your Steam path setting."
    )
    return installed_apps
