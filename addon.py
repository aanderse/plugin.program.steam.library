
import bs4
import os
import re
import requests
import routing
import sqlite3
import sys
import time
import urlparse
import xbmcaddon
import xbmcgui
import xbmcplugin

__addon__ = xbmcaddon.Addon()
__profile__ = xbmc.translatePath(__addon__.getAddonInfo('profile')).decode("utf-8")

plugin = routing.Plugin()

def log(msg, level=xbmc.LOGDEBUG):

    if __addon__.getSetting('debug') == 'true' or level != xbmc.LOGDEBUG:

        xbmc.log('[%s] %s' % (__addon__.getAddonInfo('id'), msg), level=level)

@plugin.route('/')
def index():

    handle = int(sys.argv[1])

    if __addon__.getSetting('steam-id') == '' or __addon__.getSetting('steam-key') == '':

        __addon__.openSettings()

        xbmcplugin.addDirectoryItem(handle=handle, url=plugin.url_for(scan), listitem=xbmcgui.ListItem('Scan your Steam library'))
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)

        # ensure required data is available
        return

    conn = sqlite3.connect(os.path.join(__profile__, __addon__.getSetting('steam-id') + '.db'))

    try:

        cursor = conn.execute('SELECT steam_appid, name, header_image, background FROM steam WHERE type is not NULL')

        for row in cursor.fetchall():

            log('generating ListItem for ' + str(row))

            id = row[0]
            name = row[1]
            header_image = row[2]
            background = row[3]

            item = xbmcgui.ListItem(name)
            item.setArt({ 'thumb': header_image, 'fanart': background })

            xbmcplugin.addDirectoryItem(handle=handle, url=plugin.url_for(run, id=str(id)), listitem=item)

        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.endOfDirectory(handle, succeeded=True)

        cursor.close()

    except sqlite3.OperationalError as e:

        # likely just that the steam table does not exist
        log('an exception was thrown during a sqlite select operation: ' + str(e))

    finally:

        conn.close()

@plugin.route('/run/<id>')
def run(id):

    if os.path.isfile(__addon__.getSetting('steam-path')) == False:

        # ensure required data is available
        notify = xbmcgui.Dialog()
        notify.notification('Error', 'Unable to find your Steam executable, please check your settings.', xbmcgui.NOTIFICATION_ERROR)

        return

    log('executing ' + __addon__.getSetting('steam-path') + ' steam://rungameid/' + id)

    # https://developer.valvesoftware.com/wiki/Steam_browser_protocol
    os.system(__addon__.getSetting('steam-path') + ' steam://rungameid/' + id)

@plugin.route('/scan')
def scan():

    if __addon__.getSetting('steam-id') == '' or __addon__.getSetting('steam-key') == '':

        # ensure required data is available
        return

    dialog = xbmcgui.DialogProgressBG()
    dialog.create('Scanning Steam library')

    try:

        # query the steam web api for a full list of steam applications/games that belong to the user
        response = requests.get('https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key=' + __addon__.getSetting('steam-key') + '&steamid=' + __addon__.getSetting('steam-id') + '&format=json', timeout=1)
        response.raise_for_status()

        data = response.json()

    except requests.exceptions.RequestException as e:

        # something went wrong, can't scan the steam library
        notify = xbmcgui.Dialog()
        notify.notification('Error', 'An unexpected error has occurred while contacting Steam. Please ensure your Steam credentials are correct and then try again. If this problem persists please contact support.', xbmcgui.NOTIFICATION_ERROR)

        # don't leave the dialog hanging
        dialog.close()

        return

    # grab a list of each appid belonging to the steam account
    appids = [entry['appid'] for entry in data['response']['games']]

    try:

        conn = sqlite3.connect(os.path.join(__profile__, __addon__.getSetting('steam-id') + '.db'))
        cursor = conn.cursor()

        # ensure the table actually exists
        cursor.execute('CREATE TABLE IF NOT EXISTS steam (steam_appid INTEGER PRIMARY KEY NOT NULL, type TEXT, name TEXT, about_the_game TEXT, header_image TEXT, developers TEXT, publishers TEXT, genres TEXT, release_date TEXT, background TEXT);');

        # query every steam appid that has previously been cached
        cursor.execute('SELECT steam_appid FROM steam ORDER BY steam_appid')

        # convert the above query into a python list
        ignore = [row[0] for row in cursor.fetchall()]

        # take the list of every appid belonging to the steam account and remove appids which have already been cached
        diff = set(appids).difference(ignore)

        index = 0
        count = len(diff)

        # https://steamdb.info/forum/296/steam-api-game-informations/
        # Just FYI, appdetails API is rate limited to 200 requests per 5 minutes and multi-appid support has been removed. - Timmy the Duck Thief
        rate = 1.5 if count >= 200 else 0.5

        for id in diff:

            index += 1

            # TODO: json error handling
            response = requests.get('http://store.steampowered.com/api/appdetails?appids=' + str(id), timeout=1)
            response.raise_for_status()

            data = response.json()
            data = data[str(id)]

            log('data dump for ' + str(id) + ': ' + str(data))

            if data['success']:

                data = data['data']

                type = data['type']
                name = data['name']
                about_the_game = data['about_the_game']
                header_image = data['header_image']
                developers = ', '.join([entry for entry in data['developers']]) if 'developers' in data else ''
                publishers = ', '.join([entry for entry in data['publishers']]) if 'publishers' in data else ''
                genres = ', '.join([entry['description'] for entry in data['genres']]) if 'genres' in data else ''
                release_date = data['release_date']['date']
                background = data['background']

                # cache the steam web api details of this application in our database for quick read access later
                cursor.execute('INSERT INTO steam (steam_appid, type, name, about_the_game, header_image, developers, publishers, genres, release_date, background) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (id, type, name, about_the_game, header_image, developers, publishers, genres, release_date, background))

                dialog.update(percent=int(index * 100 / count), message='scanning ' + name)

            else:

                # record that the steam web api has no details for this application
                cursor.execute('INSERT INTO steam (steam_appid) VALUES (?)', (id, ))

                dialog.update(percent=int(index * 100 / count), message='scanning ' + str(id))

            # don't throttle the steam web api
            time.sleep(rate)

        conn.commit()

    except sqlite3.OperationalError as e:

        log('an exception was thrown during a sqlite insert or create operation: ' + str(e))

        return

    finally:

        cursor.close()
        conn.close()

    dialog.close()

if __name__ == '__main__':

    log('steam-id = ' + __addon__.getSetting('steam-id'))
    log('steam-key = ' + __addon__.getSetting('steam-key'))
    log('steam-path = ' + __addon__.getSetting('steam-path'))

    plugin.run()

