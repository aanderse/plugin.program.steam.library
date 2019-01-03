import xbmc
import xbmcaddon

__addon__ = xbmcaddon.Addon()

def log(msg, level=xbmc.LOGDEBUG):
    if __addon__.getSetting('debug') == 'true' or level != xbmc.LOGDEBUG:

        xbmc.log('[%s] %s' % (__addon__.getAddonInfo('id'), msg), level=level)
