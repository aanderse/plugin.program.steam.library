import os
import routing
import sys
import xbmcplugin
import registry

import steam
from util import *

__addon__ = xbmcaddon.Addon()

plugin = routing.Plugin()
# Note : the Kodi routing plugin also obtains and casts the handle. We can use it through plugin.handle instead of redefining it.

@plugin.route('/')
def index():

    xbmcplugin.addDirectoryItem(handle=plugin.handle, url=plugin.url_for(all), listitem=xbmcgui.ListItem('All games'), isFolder=True)
    xbmcplugin.addDirectoryItem(handle=plugin.handle, url=plugin.url_for(installed), listitem=xbmcgui.ListItem('Installed games'), isFolder=True)
    xbmcplugin.addDirectoryItem(handle=plugin.handle, url=plugin.url_for(recent), listitem=xbmcgui.ListItem('Recently played games'), isFolder=True)
    xbmcplugin.endOfDirectory(plugin.handle, succeeded=True)

@plugin.route('/all')
def all():

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
    xbmcplugin.endOfDirectory(plugin.handle, succeeded=True)

@plugin.route('/installed')
def installed():

    if not all_required_credentials_available():
        return

    if os.path.isdir(__addon__.getSetting('steam-path')) == False:

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

    # TODO : Refactor and/or rename get_registry_values, and perhaps return an array of appids instead of a dictionary.
    #  currently returns a dictionary of string appid as keys, and only values '1'. Uninstalled games in the registry are actually not returned by this function.
    installed_appids_dict = registry.get_registry_values(os.path.join(__addon__.getSetting('steam-path'), 'registry.vdf'))
    # Get an Array of dictionary keys, ie of the installed games appids. TODO return an array directly from the function above.
    installed_appids = installed_appids_dict.keys()

    # filter out any applications not listed as installed
    steam_installed_games = filter(lambda app_entry: str(app_entry['appid']) in installed_appids, steam_games_details)

    directory_items = create_directory_items(steam_installed_games)
    xbmcplugin.addDirectoryItems(plugin.handle, directory_items)

    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(plugin.handle, succeeded=True)

@plugin.route('/recent')
def recent():

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

    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(plugin.handle, succeeded=True)

@plugin.route('/install/<appid>')
def install(appid):

    if os.path.isfile(__addon__.getSetting('steam-exe')) == False:

        # ensure required data is available
        show_error(NameError('steam-exe not found'), 'Unable to find your Steam executable, please check your settings.')
        return

    steam.install(__addon__.getSetting('steam-exe'), appid)

@plugin.route('/run/<appid>')
def run(appid):

    if os.path.isfile(__addon__.getSetting('steam-exe')) == False:

        # ensure required data is available
        show_error(NameError('steam-exe not found'), 'Unable to find your Steam executable, please check your settings.')
        return

    steam.run(__addon__.getSetting('steam-exe'), __addon__.getSetting('steam-args'), appid)


def create_directory_items(app_entries):
    """
    Creates a list item for each game/app entry provided

    :param app_entries: array of game entries, containing at least keys : appid, name, img_icon_url, img_logo_url, playtime_forever
    :returns: an array of list items of the game entries, formatted like so : [(url,listItem,bool),..]
    """
    directory_items = []
    for app_entry in app_entries:
        appid = str(app_entry['appid'])
        name = app_entry['name']

        run_url = plugin.url_for(run, appid=appid)
        item = xbmcgui.ListItem(name)

        item.addContextMenuItems([('Play',
                                   'RunPlugin(' + run_url + ')'),
                                  ('Install', 'RunPlugin(' + plugin.url_for(install, appid=appid) + ')')])

        item.setArt({'thumb': 'http://cdn.akamai.steamstatic.com/steam/apps/' + str(appid) + '/header.jpg',
                     'fanart': 'http://cdn.akamai.steamstatic.com/steam/apps/' + str(appid) + '/page_bg_generated_v6b.jpg'})

        directory_items.append((run_url, item, False))

    return directory_items


def main():

    log('steam-id = ' + __addon__.getSetting('steam-id'))
    log('steam-key = ' + __addon__.getSetting('steam-key'))
    log('steam-exe = ' + __addon__.getSetting('steam-exe'))
    log('steam-path = ' + __addon__.getSetting('steam-path'))

    # backwards compatibility for versions prior to 0.6.0
    if __addon__.getSetting('steam-id') != '' and __addon__.getSetting('steam-key') != '' and __addon__.getSetting('steam-path') != '' and __addon__.getSetting('steam-exe') == '':

        __addon__.setSetting('steam-exe', __addon__.getSetting('steam-path'));

        if sys.platform == "linux" or sys.platform == "linux2":

            __addon__.setSetting('steam-path', os.path.expanduser('~/.steam'));

        elif sys.platform == "win32":

            __addon__.setSetting('steam-path', os.path.expandvars('%ProgramFiles%\\Steam\\Steam.exe'))

        elif sys.platform == "win64":

            __addon__.setSetting('steam-path', os.path.expandvars('%ProgramFiles(x86)%\\Steam\\Steam.exe'))

    # all settings are empty, assume this is the first run
    # best guess at steam executable path
    if __addon__.getSetting('steam-id') == '' and __addon__.getSetting('steam-key') == '' and __addon__.getSetting('steam-exe') == '':

        if sys.platform == "linux" or sys.platform == "linux2":

            __addon__.setSetting('steam-exe', '/usr/bin/steam')
            __addon__.setSetting('steam-path', os.path.expanduser('~/.steam'));

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
        __addon__.setSetting('version', '0.6.0');

    # prompt the user to configure the plugin with their steam details
    if not all_required_credentials_available():
        __addon__.openSettings()

    plugin.run()
