
import os
import requests
import routing
import subprocess
import sys
import time
import xbmcaddon
import xbmcgui
import xbmcplugin

__addon__ = xbmcaddon.Addon()

plugin = routing.Plugin()

def log(msg, level=xbmc.LOGDEBUG):

    if __addon__.getSetting('debug') == 'true' or level != xbmc.LOGDEBUG:

        xbmc.log('[%s] %s' % (__addon__.getAddonInfo('id'), msg), level=level)

@plugin.route('/')
def index():

    handle = int(sys.argv[1])

    xbmcplugin.addDirectoryItem(handle=handle, url=plugin.url_for(all), listitem=xbmcgui.ListItem('All games'), isFolder=True)
    xbmcplugin.addDirectoryItem(handle=handle, url=plugin.url_for(recent), listitem=xbmcgui.ListItem('Recently played games'), isFolder=True)
    xbmcplugin.endOfDirectory(handle, succeeded=True)

@plugin.route('/all')
def all():

    if __addon__.getSetting('steam-id') == '' or __addon__.getSetting('steam-key') == '':

        # ensure required data is available
        return

    handle = int(sys.argv[1])

    try:

        # query the steam web api for a full list of steam applications/games that belong to the user
        response = requests.get('https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key=' + __addon__.getSetting('steam-key') + '&steamid=' + __addon__.getSetting('steam-id') + '&include_appinfo=1&format=json', timeout=10)
        response.raise_for_status()

    except requests.exceptions.RequestException as e:

        # something went wrong, can't scan the steam library
        notify = xbmcgui.Dialog()
        notify.notification('Error', 'An unexpected error has occurred while contacting Steam. Please ensure your Steam credentials are correct and then try again. If this problem persists please contact support.', xbmcgui.NOTIFICATION_ERROR)

        log(str(e), xbmc.LOGERROR)

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

@plugin.route('/recent')
def recent():

    if __addon__.getSetting('steam-id') == '' or __addon__.getSetting('steam-key') == '':

        # ensure required data is available
        return

    handle = int(sys.argv[1])

    try:

        # query the steam web api for a full list of steam applications/games that belong to the user
        response = requests.get('https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/?key=' + __addon__.getSetting('steam-key') + '&steamid=' + __addon__.getSetting('steam-id') + '&include_appinfo=1&format=json', timeout=10)
        response.raise_for_status()

    except requests.exceptions.RequestException as e:

        # something went wrong, can't scan the steam library
        notify = xbmcgui.Dialog()
        notify.notification('Error', 'An unexpected error has occurred while contacting Steam. Please ensure your Steam credentials are correct and then try again. If this problem persists please contact support.', xbmcgui.NOTIFICATION_ERROR)

        log(str(e), xbmc.LOGERROR)

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

    if os.path.isfile(__addon__.getSetting('steam-path')) == False:

        # ensure required data is available
        notify = xbmcgui.Dialog()
        notify.notification('Error', 'Unable to find your Steam executable, please check your settings.', xbmcgui.NOTIFICATION_ERROR)

        return

    log('executing ' + __addon__.getSetting('steam-path') + ' steam://install/' + id)

    # https://developer.valvesoftware.com/wiki/Steam_browser_protocol
    subprocess.call([__addon__.getSetting('steam-path'), 'steam://install/' + id])

@plugin.route('/run/<id>')
def run(id):

    if os.path.isfile(__addon__.getSetting('steam-path')) == False:

        # ensure required data is available
        notify = xbmcgui.Dialog()
        notify.notification('Error', 'Unable to find your Steam executable, please check your settings.', xbmcgui.NOTIFICATION_ERROR)

        return

    log('executing ' + __addon__.getSetting('steam-path') + ' steam://rungameid/' + id)

    # https://developer.valvesoftware.com/wiki/Steam_browser_protocol
    subprocess.call([__addon__.getSetting('steam-path'), 'steam://rungameid/' + id])

def main():

    log('steam-id = ' + __addon__.getSetting('steam-id'))
    log('steam-key = ' + __addon__.getSetting('steam-key'))
    log('steam-path = ' + __addon__.getSetting('steam-path'))

    # all settings are empty, assume this is the first run
    # best guess at steam executable path
    if __addon__.getSetting('steam-id') == '' and __addon__.getSetting('steam-key') == '' and __addon__.getSetting('steam-path') == '':

        if sys.platform == "linux" or sys.platform == "linux2":

            __addon__.setSetting('steam-path', '/usr/bin/steam')

        elif sys.platform == "darwin":

            __addon__.setSetting('steam-path', os.path.expanduser('~/Library/Application Support/Steam/Steam.app/Contents/MacOS/steam_osx'))

        elif sys.platform == "win32":

            __addon__.setSetting('steam-path', os.path.expandvars('%ProgramFiles%\\Steam\\Steam.exe'))

        elif sys.platform == "win64":

            __addon__.setSetting('steam-path', os.path.expandvars('%ProgramFiles(x86)%\\Steam\\Steam.exe'))

    # prompt the user to configure the plugin with their steam details
    if __addon__.getSetting('steam-id') == '' or __addon__.getSetting('steam-key') == '':

        __addon__.openSettings()

    plugin.run()
