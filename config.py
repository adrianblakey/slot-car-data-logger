# Configuration - environment variables
import machine
import ubinascii
import logging
import json
import sys

global DEBUG_LEVEL
global SSID
global PASSWORD
global DEBUG
global MY_ID
global TRACK
global PROFILE
global LANE
global MODES

log = logging.getLogger("config")

MODES: str = 'disk' # disk,web
PROFILE: int = 0
TRACK: str = ''
LANE: str = ''
DEBUG_LEVEL: str = 'DEBUG'
SSID: str = "FRITZ!Box 7530 YM"
PASSWORD: str = "73119816833371417369"
DEBUG: bool = True

MY_ID: str = ubinascii.hexlify(machine.unique_id()).decode()

if DEBUG_LEVEL == 'DEBUG':
    logging.basicConfig(level=logging.DEBUG)
elif DEBUG_LEVEL == 'INFO':
    logging.basicConfig(level=logging.INFO)
elif DEBUG_LEVEL == 'WARNING':
    logging.basicConfig(level=logging.WARNING)
elif DEBUG_LEVEL == 'ERROR':
    logging.basicConfig(level=logging.ERROR)
elif DEBUG_LEVEL == 'CRITICAL':
    logging.basicConfig(level=logging.CRITICAL)
    

def __read_conf(file: str) -> dict:
    config = {}
    with open(file, 'r') as f:
        config = json.load(f)
    return config


def __write_conf(file: str, config: dict) -> None:
    with open(file, 'w') as f:
        json.dump(config, f, separators=(',', ':'))    


def read_conn() -> None:
    if log.getEffectiveLevel() == logging.DEBUG:
        log.debug('Read connections')
    global SSID
    global PASSWORD
    wifi = __read_conf('wifi.json')
    SSID = wifi['ssid']
    PASSWORD = wifi['password']
    

# Instead of a track database - we just have profiles
# at is the current profile.
# Profile ids are sequential integer numbers.
# a profile is a track name, track lane, therefore there could be
# 4 profiles for Fylde and 5 for Castle
def put_id(id: int) -> None:
    if log.getEffectiveLevel() == logging.DEBUG:
        log.debug('Write the updated profile id back to the config file')
    global PROFILE
    config = __read_conf('config.json')
    if id <= len(config['profiles']):
        config['at'] = id
        PROFILE = id
        __write_conf('config.json', config)
    else:
        raise ValueError('No corresponding profile for id:', id) 
        

def put_profile(track: str, lane: str, id: int = 0,) -> int:
    # If id is not set or 0 - append, else merge
    # TODO Validate it against the track
    if log.getEffectiveLevel() == logging.DEBUG:
        log.debug('Updating profiles in config.json')
    global TRACK
    global LANE
    global PROFILE
    profile = {"id": id, "track": track, "lane": lane}
    config = __read_conf('config.json')
    # Add
    count = len(config['profiles'])
    if id == 0 or id > count:
        # append
        id = count + 1
        profile['id'] = id
        config['profiles'].append(profile)
    else:
        # replace
        config['profiles'][id - 1] = profile
    PROFILE = id
    TRACK = track
    LANE = lane
    __write_conf('config.json', config)
    return id
    

def read_config():
    log.getEffectiveLevel()
    global MODES
    if log.getEffectiveLevel() == logging.DEBUG:
        log.debug('Reading config')
    config = __read_conf('config.json')
    MODES = config['modes']
    read_profiles()
    

def read_profiles():
    log.getEffectiveLevel()
    global TRACK
    global LANE
    global PROFILE
    PROFILE = 0
    if log.getEffectiveLevel() == logging.DEBUG:
        log.debug('Reading profiles')
    config = __read_conf('profiles.json')
    me = config['at']
    if len(config['profiles']) > me - 1:
        profile = config['profiles'][me - 1]
        PROFILE = profile['id']
        TRACK = profile['track']
        LANE = profile['lane']
    else:
        raise ValueError('No corresponding profile for id:', me) 
                   
                
def to_string():
    print("Id:", PROFILE,"Track:", TRACK, "Lane:", LANE)


read_config()
read_profiles()
read_conn()
"""
to_string()
put_id(5)
put_profile('Fyle', 'orange')
to_string()
"""
