import os
import routing
import sys
import xbmcplugin

from . import arts
from . import registry
from . import steam
from .util import *

__addon__ = xbmcaddon.Addon()

plugin = routing.Plugin()


# Note : the Kodi routing plugin also obtains and casts the handle. We can use it through plugin.handle instead of redefining it.

@plugin.route('/')
def index():
    xbmcplugin.addDirectoryItem(handle=plugin.handle, url=plugin.url_for(all_games), listitem=xbmcgui.ListItem('All games'), isFolder=True)
    xbmcplugin.addDirectoryItem(handle=plugin.handle, url=plugin.url_for(installed_games), listitem=xbmcgui.ListItem('Installed games'), isFolder=True)
    xbmcplugin.addDirectoryItem(handle=plugin.handle, url=plugin.url_for(recent_games), listitem=xbmcgui.ListItem('Recently played games'), isFolder=True)
    xbmcplugin.endOfDirectory(plugin.handle, succeeded=True)


@plugin.route('/all')
def all_games():
    if not all_required_credentials_available():
        return

    try:
        steam_games_details = steam.get_user_games(__addon__.getSetting('steam-key'), __addon__.getSetting('steam-id'))

    except IOError as e:
        # something went wrong, can't scan the steam library
        show_error(e, 'An unexpected error has occurred while contacting Steam. Please ensure your Steam credentials are correct and then try again. '
                      'If this problem persists please contact support.')
        return

    directory_items = create_directory_items(steam_games_details)
    xbmcplugin.addDirectoryItems(plugin.handle, directory_items)

    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_PLAYCOUNT)
    xbmcplugin.endOfDirectory(plugin.handle, succeeded=True)


@plugin.route('/installed')
def installed_games():
    if not all_required_credentials_available():
        return

    if not os.path.isdir(__addon__.getSetting('steam-path')):
        # ensure required data is available
        show_error(NameError("steam-path not found"), 'Unable to find your Steam path, please check your settings.')
        return

    try:
        steam_games_details = steam.get_user_games(__addon__.getSetting('steam-key'), __addon__.getSetting('steam-id'))

    except IOError as e:
        # something went wrong, can't scan the steam library
        show_error(e, 'An unexpected error has occurred while contacting Steam. Please ensure your Steam credentials are correct and then try again. '
                      'If this problem persists please contact support.')
        return

    installed_appids = registry.get_installed_steam_apps(os.path.join(__addon__.getSetting('steam-path'), 'registry.vdf'))

    # filter out any applications not listed as installed
    steam_installed_games = filter(lambda app_entry: str(app_entry['appid']) in installed_appids, steam_games_details)

    directory_items = create_directory_items(steam_installed_games)
    xbmcplugin.addDirectoryItems(plugin.handle, directory_items)

    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_PLAYCOUNT)
    xbmcplugin.endOfDirectory(plugin.handle, succeeded=True)


@plugin.route('/recent')
def recent_games():
    if not all_required_credentials_available():
        return

    try:
        steam_games_details = steam.get_user_games(__addon__.getSetting('steam-key'), __addon__.getSetting('steam-id'), recent_only=True)

    except IOError as e:
        # something went wrong, can't scan the steam library
        show_error(e, 'An unexpected error has occurred while contacting Steam. Please ensure your Steam credentials are correct and then try again. '
                      'If this problem persists please contact support.')
        return

    directory_items = create_directory_items(steam_games_details)
    xbmcplugin.addDirectoryItems(plugin.handle, directory_items)

    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_UNSORTED, "Last played")
    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_PLAYCOUNT)
    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(plugin.handle, succeeded=True)


@plugin.route('/install/<appid>')
def install(appid):
    if not os.path.isfile(__addon__.getSetting('steam-exe')):
        # ensure required data is available
        show_error(NameError('steam-exe not found'), 'Unable to find your Steam executable, please check your settings.')
        return

    steam.install(__addon__.getSetting('steam-exe'), appid)


@plugin.route('/run/<appid>')
def run(appid):
    if not os.path.isfile(__addon__.getSetting('steam-exe')):
        # ensure required data is available
        show_error(NameError('steam-exe not found'), 'Unable to find your Steam executable, please check your settings.')
        return

    steam.run(__addon__.getSetting('steam-exe'), __addon__.getSetting('steam-args'), appid)


@plugin.route('/delete_cache')
def delete_cache():
    steam.delete_cache()
    arts.delete_cache()


def create_directory_items(app_entries):
    """
    Creates a list item for each game/app entry provided

    :param app_entries: array of game entries, with each entry containing at least keys : appid, name, img_icon_url, img_logo_url, playtime_forever
    :returns: an array of list items of the game entries, formatted like so : [(url,listItem,bool),..]
    """

    # We set the folder content to "movies" as the program/game contents are locked out of many useful views, such as posters, headers, and more.
    xbmcplugin.setContent(plugin.handle, "movies")
    # TODO setContent to games when more skins support this content type.

    directory_items = []
    for app_entry in app_entries:
        appid = str(app_entry['appid'])
        name = app_entry['name']

        run_url = plugin.url_for(run, appid=appid)
        item = xbmcgui.ListItem(name)
        item.setUniqueIDs({'steam': appid, 'steam_img_icon': app_entry['img_icon_url']})
        item.setInfo('video', {'playcount': app_entry.get('playtime_forever', 0)})
        item.setContentLookup(False)  # Tells Kodi not to send HEAD requests (used to determine MIME type for example) to the item's run URL.

        item.addContextMenuItems([('Play', 'RunPlugin(' + run_url + ')'),
                                  ('Install', 'RunPlugin(' + plugin.url_for(install, appid=appid) + ')')],
                                 replaceItems=True)  # Since we set the content type to "movies", default movie context elements may appear. We replace them.

        art_dictionary = create_arts_dictionary(app_entry)
        item.setArt(art_dictionary)

        directory_items.append((run_url, item, False))

    return directory_items


def create_arts_dictionary(app_entry):
    """
    Creates a dictionary of arts keys and their associated links, for a given app entry.
    :param app_entry: dictionary of app information, containing at least the keys : appid, img_icon_url, img_logo_url
    :return: dictionary of arts for the app.
    """

    appid = str(app_entry['appid'])
    img_icon_url = app_entry['img_icon_url']
    art_dictionary = {}

    # Multiple fanart https://kodi.wiki/view/Artwork_types#fanart.23
    SUPPORTED_ART_TYPES = ['poster', 'landscape', 'banner', 'clearlogo', 'thumb', 'fanart', 'fanart1', 'fanart2', 'icon']

    for art_type in SUPPORTED_ART_TYPES:
        art_dictionary[art_type] = arts.resolve_art_url(art_type, appid, img_icon_url)
    return art_dictionary


def main():
    log('steam-id = ' + __addon__.getSetting('steam-id'))
    log('steam-key = ' + __addon__.getSetting('steam-key'))
    log('steam-exe = ' + __addon__.getSetting('steam-exe'))
    log('steam-path = ' + __addon__.getSetting('steam-path'))

    # backwards compatibility for versions prior to 0.6.0
    if __addon__.getSetting('steam-id') != '' and __addon__.getSetting('steam-key') != '' \
            and __addon__.getSetting('steam-path') != '' and __addon__.getSetting('steam-exe') == '':

        __addon__.setSetting('steam-exe', __addon__.getSetting('steam-path'))

        if sys.platform == "linux" or sys.platform == "linux2":

            __addon__.setSetting('steam-path', os.path.expanduser('~/.steam'))

        elif sys.platform == "win32":

            __addon__.setSetting('steam-path', os.path.expandvars('%ProgramFiles%\\Steam\\Steam.exe'))

        elif sys.platform == "win64":

            __addon__.setSetting('steam-path', os.path.expandvars('%ProgramFiles(x86)%\\Steam\\Steam.exe'))

    # all settings are empty, assume this is the first run
    # best guess at steam executable path
    if __addon__.getSetting('steam-id') == '' and __addon__.getSetting('steam-key') == '' and __addon__.getSetting('steam-exe') == '':

        if sys.platform == "linux" or sys.platform == "linux2":

            __addon__.setSetting('steam-exe', '/usr/bin/steam')
            __addon__.setSetting('steam-path', os.path.expanduser('~/.steam'))

        elif sys.platform == "darwin":

            __addon__.setSetting('steam-exe', os.path.expanduser('~/Library/Application Support/Steam/Steam.app/Contents/MacOS/steam_osx'))
            # TODO: not a clue

        elif sys.platform == "win32":

            __addon__.setSetting('steam-exe', os.path.expandvars('%ProgramFiles%\\Steam\\Steam.exe'))
            __addon__.setSetting('steam-path', os.path.expandvars('%ProgramFiles%\\Steam\\Steam.exe'))

        elif sys.platform == "win64":

            __addon__.setSetting('steam-exe', os.path.expandvars('%ProgramFiles(x86)%\\Steam\\Steam.exe'))
            __addon__.setSetting('steam-path', os.path.expandvars('%ProgramFiles(x86)%\\Steam\\Steam.exe'))

    if __addon__.getSetting('version') == '':
        # first time run, store version
        __addon__.setSetting('version', __addon__.getAddonInfo('version'))

    # prompt the user to configure the plugin with their steam details
    if not all_required_credentials_available():
        __addon__.openSettings()

    plugin.run()
