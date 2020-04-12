import xbmc
import xbmcaddon
import xbmcgui

__addon__ = xbmcaddon.Addon()


def log(msg, level=xbmc.LOGDEBUG):
    if __addon__.getSetting('debug') == 'true' or level != xbmc.LOGDEBUG:
        xbmc.log('[%s] %s' % (__addon__.getAddonInfo('id'), msg), level=level)


def show_error(e, message):
    """ Displays an error message to the user and log the cause.

    :type e: Exception
    :param e: An exception object to add to the error log
    :param message: An error message to display to the user
    """
    notify = xbmcgui.Dialog()
    notify.notification('Error', message, xbmcgui.NOTIFICATION_ERROR)
    log(str(e), xbmc.LOGERROR)


def all_required_credentials_available():
    """ Checks if the credentials required to obtain a steam game folder is available

    :returns: A boolean, true if the steam-id and steam-key add-on settings were set.
    """
    return __addon__.getSetting('steam-id') != '' or __addon__.getSetting('steam-key') != ''