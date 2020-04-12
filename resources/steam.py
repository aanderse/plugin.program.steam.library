import shlex
import subprocess
from util import log


def install(steam_exe_path, appid):
    """
    Calls Steam to install a game/app. This will display Steam's game install prompt, which displays install configurations and asks for confirmation.

    :param steam_exe_path: path to the steam executable
    :param appid: appid of the game/app to install
    """
    log('executing ' + steam_exe_path + ' steam://install/' + appid)
    # https://developer.valvesoftware.com/wiki/Steam_browser_protocol
    subprocess.call([steam_exe_path, 'steam://install/' + appid])


def run(steam_exe_path, steam_launch_args, appid):
    """
    Calls Steam to run a game/app. This will run it, or in not installed display Steam install prompt

    :param steam_exe_path: path to the steam executable
    :param steam_launch_args: A string of Steam launch arguments (format "-arg1 -arg2 ...")
    :param appid: appid of the game/app to run
    """
    user_args = shlex.split(steam_launch_args)
    log('executing ' + steam_exe_path + ' ' + steam_launch_args + ' steam://rungameid/' + appid)

    # https://developer.valvesoftware.com/wiki/Steam_browser_protocol
    subprocess.call([steam_exe_path, user_args, 'steam://rungameid/' + appid])
