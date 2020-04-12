import os
import requests
import routing
import shlex
import subprocess
import sys
import time
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import registry

from config import *

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

    handle = int(sys.argv[1])

    try:

        # query the steam web api for a full list of steam applications/games that belong to the user
        response = requests.get('https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key=' + __addon__.getSetting('steam-key') + '&steamid=' + __addon__.getSetting('steam-id') + '&include_appinfo=1&format=json', timeout=10)
        response.raise_for_status()

    except requests.exceptions.RequestException as e:

        # something went wrong, can't scan the steam library
        show_error(e, 'An unexpected error has occurred while contacting Steam. Please ensure your Steam credentials are correct and then try again. '
                      'If this problem persists please contact support.')
        return

    data = response.json()
    totalItems = data['response']['game_count']

    for entry in data['response']['games']:

        appid = entry['appid']
        name = entry['name']

        item = xbmcgui.ListItem(name)

        item.addContextMenuItems([('Play', 'RunPlugin(plugin://plugin.program.steam.library/run/' + str(appid) + ')'), ('Install', 'RunPlugin(plugin://plugin.program.steam.library/install/' + str(appid) + ')')])
        item.setArt({ 'thumb': 'http://cdn.akamai.steamstatic.com/steam/apps/' + str(appid) + '/header.jpg', 'fanart': 'http://cdn.akamai.steamstatic.com/steam/apps/' + str(appid) + '/page_bg_generated_v6b.jpg' })

        if not xbmcplugin.addDirectoryItem(handle=handle, url=plugin.url_for(run, id=str(appid)), listitem=item, totalItems=totalItems): break

    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(handle, succeeded=True)

@plugin.route('/installed')
def installed():

    if not all_required_credentials_available():
        return

    if os.path.isdir(__addon__.getSetting('steam-path')) == False:

        # ensure required data is available
        show_error(NameError("steam-path not found"), 'Unable to find your Steam path, please check your settings.')
        return

    handle = int(sys.argv[1])

    try:

        # query the steam web api for a full list of steam applications/games that belong to the user
        response = requests.get('https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key=' + __addon__.getSetting('steam-key') + '&steamid=' + __addon__.getSetting('steam-id') + '&include_appinfo=1&format=json', timeout=10)
        response.raise_for_status()

    except requests.exceptions.RequestException as e:

        # something went wrong, can't scan the steam library
        show_error(e, 'An unexpected error has occurred while contacting Steam. Please ensure your Steam credentials are correct and then try again. '
                      'If this problem persists please contact support.')
        return

    apps = registry.get_registry_values(os.path.join(__addon__.getSetting('steam-path'), 'registry.vdf'))
    data = response.json()

    for entry in data['response']['games']:

        appid = entry['appid']
        name = entry['name']

        # filter out any applications not listed as installed
        if str(appid) not in apps: continue

        item = xbmcgui.ListItem(name)

        item.addContextMenuItems([('Play', 'RunPlugin(plugin://plugin.program.steam.library/run/' + str(appid) + ')'), ('Install', 'RunPlugin(plugin://plugin.program.steam.library/install/' + str(appid) + ')')])
        item.setArt({ 'thumb': 'http://cdn.akamai.steamstatic.com/steam/apps/' + str(appid) + '/header.jpg', 'fanart': 'http://cdn.akamai.steamstatic.com/steam/apps/' + str(appid) + '/page_bg_generated_v6b.jpg' })

        if not xbmcplugin.addDirectoryItem(handle=handle, url=plugin.url_for(run, id=str(appid)), listitem=item): break

    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(handle, succeeded=True)

@plugin.route('/recent')
def recent():

    if not all_required_credentials_available():
        return

    handle = int(sys.argv[1])

    try:

        # query the steam web api for a full list of steam applications/games that belong to the user
        response = requests.get('https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/?key=' + __addon__.getSetting('steam-key') + '&steamid=' + __addon__.getSetting('steam-id') + '&include_appinfo=1&format=json', timeout=10)
        response.raise_for_status()

    except requests.exceptions.RequestException as e:

        # something went wrong, can't scan the steam library
        show_error(e, 'An unexpected error has occurred while contacting Steam. Please ensure your Steam credentials are correct and then try again. '
                      'If this problem persists please contact support.')
        return

    data = response.json()
    totalItems = data['response']['total_count']

    for entry in data['response']['games']:

        appid = entry['appid']
        name = entry['name']

        item = xbmcgui.ListItem(name)
        item.setArt({ 'thumb': 'http://cdn.akamai.steamstatic.com/steam/apps/' + str(appid) + '/header.jpg', 'fanart': 'http://cdn.akamai.steamstatic.com/steam/apps/' + str(appid) + '/page_bg_generated_v6b.jpg' })

        if not xbmcplugin.addDirectoryItem(handle=handle, url=plugin.url_for(run, id=str(appid)), listitem=item, totalItems=totalItems): break

    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(handle, succeeded=True)

@plugin.route('/install/<id>')
def install(id):

    if os.path.isfile(__addon__.getSetting('steam-exe')) == False:

        # ensure required data is available
        show_error(NameError('steam-exe not found'), 'Unable to find your Steam executable, please check your settings.')
        return

    log('executing ' + __addon__.getSetting('steam-exe') + ' steam://install/' + id)

    # https://developer.valvesoftware.com/wiki/Steam_browser_protocol
    subprocess.call([__addon__.getSetting('steam-exe'), 'steam://install/' + id])

@plugin.route('/run/<id>')
def run(id):

    if os.path.isfile(__addon__.getSetting('steam-exe')) == False:

        # ensure required data is available
        show_error(NameError('steam-exe not found'), 'Unable to find your Steam executable, please check your settings.')
        return

    userArgs = shlex.split(__addon__.getSetting('steam-args'))

    log('executing ' + __addon__.getSetting('steam-exe') + ' ' + __addon__.getSetting('steam-args') + ' steam://rungameid/' + id)

    # https://developer.valvesoftware.com/wiki/Steam_browser_protocol
    subprocess.call([__addon__.getSetting('steam-exe')] + userArgs + ['steam://rungameid/' + id])

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
