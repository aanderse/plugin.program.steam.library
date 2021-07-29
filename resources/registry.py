'''
get registry values for steam games
'''

import os
import xbmc
from .util import *

if os.name == 'nt':
    import winreg


# https://github.com/lutris/lutris/blob/master/lutris/util/steam.py
def vdf_parse(steam_config_file, config):
    """Parse a Steam config file and return the contents as a dict with lowercase keys.
    The motivation behind returning lowercase keys is that the case is not consistent between environments it seems.
    """
    line = " "
    while line:
        try:
            line = steam_config_file.readline()
        except UnicodeDecodeError:
            log("Error while reading Steam VDF file {}. Returning {}".format(steam_config_file, config), xbmc.LOGERROR)
            return config
        if not line or line.strip() == "}":
            return config
        while not line.strip().endswith("\""):
            nextline = steam_config_file.readline()
            if not nextline:
                break
            line = line[:-1] + nextline

        line_elements = line.strip().split("\"")
        if len(line_elements) == 3:
            key = line_elements[1].lower()
            steam_config_file.readline()  # skip '{'
            config[key] = vdf_parse(steam_config_file, {})
        else:
            try:
                config[line_elements[1].lower()] = line_elements[3]
            except IndexError:
                log('Malformed config file: {}'.format(line), xbmc.LOGERROR)
    return config


def is_installed_win(app_id):
    """
    Gets whether an app with the given app id is installed, on Windows
    :param app_id: app_id to check
    :return: True if the app is installed, false otherwise
    """
    try:
        app = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Valve\\Steam\\Apps\\" + app_id)
        print(winreg.QueryInfoKey(app)[1])
        for i in range(winreg.QueryInfoKey(app)[1]):
            name, value, type = winreg.EnumValue(app, i)
            if name == "Installed":
                return value == 1

    except WindowsError:
        pass
    # Sometimes the key "Installed" does not exist, and we get out of the loop without returning anything,so we return False at the end of the function
    return False


def get_installed_steam_apps(registry_path):
    """
    Obtains the steam games/apps installed on the computer.
    :param registry_path: Path to the registry.vdf file
    :return: an array of appids that are installed.
    """
    installed_apps = []

    if os.name == 'nt':
        try:
            apps = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Valve\\Steam\\Apps")
            print(winreg.QueryInfoKey(apps)[0])
            for i in range(winreg.QueryInfoKey(apps)[0]):
                app_id = winreg.EnumKey(apps, i)
                if is_installed_win(app_id):
                    installed_apps.append(app_id)

        except WindowsError as e:
            show_error(e, "Error while reading Windows registry")
            pass
    else:
        with open(registry_path, 'r') as file:
            try:
                vdf = vdf_parse(file, {})
                apps = vdf['registry']['hkcu']['software']['valve']['steam']['apps']

                # apparently case of 'installed' differs depending on ... ?
                # We create a list of the apps that have a "installed" key equal to "1".
                installed_apps = [appid for (appid, information) in apps.items() if (information.get('installed', '0') == '1')]
            except KeyError as e:
                show_error(e, "Error finding the values from registry.vdf")
                pass

    return installed_apps
