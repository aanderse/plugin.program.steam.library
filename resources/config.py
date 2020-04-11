import xbmc
import xbmcaddon

__addon__ = xbmcaddon.Addon()

def log(msg, level=xbmc.LOGDEBUG):
    if __addon__.getSetting('debug') == 'true' or level != xbmc.LOGDEBUG:

        xbmc.log('[%s] %s' % (__addon__.getAddonInfo('id'), msg), level=level)


def all_required_credentials_available():
    """ Checks if the credentials required to obtain a steam game folder is available

    :returns: A boolean, true if the steam-id and steam-key add-on settings were set.
    """
    return __addon__.getSetting('steam-id') != '' or __addon__.getSetting('steam-key') != ''
