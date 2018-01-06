
import os
import sys
import xbmc
import xbmcaddon

from datetime import datetime, timedelta

__addon__ = xbmcaddon.Addon('plugin.program.steam.library')
__profile__ = xbmc.translatePath(__addon__.getAddonInfo('profile')).decode("utf-8")

if __name__ == '__main__':

    monitor = xbmc.Monitor()

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

    while not monitor.abortRequested():

        try:

            now = datetime.now()
            scan = datetime.strptime(__addon__.getSetting('scan-time'), '%H:%M')

            # is it time to scan yet?
            if scan.hour == now.hour and scan.minute == now.minute:

                xbmc.executebuiltin('RunPlugin(plugin://plugin.program.steam.library/scan)')

        except ValueError:

            pass

        if monitor.waitForAbort(60):
            break
