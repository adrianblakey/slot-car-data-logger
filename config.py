# Copyright @ 20023, Adrian Blakey. All rights reserved
# Configuration - environment variables
# Lazy initialization cause it's called from boot and main
import os
import machine
import ubinascii
import logging
import json
import sys
from profile import Profile

global DEBUG_LEVEL
global DEBUG

log = logging.getLogger("config")

# log.debug('Starting config') bug?

PROFILES_FILE: str = 'profiles.json'
WIFI_CONFIG_FILE: str = 'wifi.json'

DEBUG_LEVEL: str = 'DEBUG'

DEBUG: bool = True

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
    
class Config():
    def __init__(self):
        self._wifi = None
        self._prfx: str = None
        self._more_wifi = False
        self._iter_wifi: iter = None
        self._wifi_config: str = None
        self._profile: Profile = None
        self._my_id: str = ubinascii.hexlify(machine.unique_id()).decode()
             
    def __wifi(self) -> (iter, str):
        # Set up a search list of wifi configuration
        #all_files = os.listdir(self._prfx)
        wifi_config = [l for l in os.listdir(self._prfx) if l.startswith('wifi')]
        #log.debug('%s %s', all_files, wifi_config)
        if not wifi_config:
            log.info('No wifi*.json files found - assume no wifi ...')
            return None, None
        wifi_config.remove(WIFI_CONFIG_FILE)
        wifi_config.insert(0, WIFI_CONFIG_FILE)
        log.debug('Wifi search list %s', wifi_config)
        self._iter_wifi = iter(wifi_config)
        try:
            self._wifi_config = str(next(self._iter_wifi))
            self._more_wifi = True
        except StopIteration:
            log.debug('Stop the wifi search list iterator')
            self._more_wifi = False
        log.debug('Returning %s %s', self._iter_wifi, self._wifi_config)
        return self._iter_wifi, self._wifi_config
              
    def __sd_card(self) -> None:
        # sd card attached - if so assume we use that for files
        try:
            with open('/sd/__foo', 'w') as f:
                self._prfx = '/sd/'
                sd = True
                f.close()
                os.remove('/sd/__foo')
        except OSError:
            self._prfx = './'
            log.info('No sd card')
                   
    def __read_conf(self, file: str) -> dict:
        # Read a json file adding prefix
        if self._prfx == None:
            self.__sd_card()
        json_dict: dict = None
        try:
            with open(self._prfx + file, 'r') as f:
                log.debug('Reading configuration from %s', self._prfx + file)
                json_dict = json.load(f)
        except OSError as ex:
            log.error('No file %s %s', self._prfx + file, ex)
            raise RuntimeError(ex)
        return json_dict

    def __write_conf(self, file: str, json_dict: dict) -> None:
        # Write a json file adding prefix
        if self._prfx == None:
            self.__sd_card()
        with open(self._prfx + file, 'w') as f:
            log.debug('write %s', self._prfx + file)
            json.dump(json_dict, f, separators=(',', ':'))
            
    def prfx(self) -> str:
        if self._prfx == None:
            self.__sd_card()
        return self._prfx
   
    def more_wifi(self) -> bool:
        # More wifi configs or not
        return self._more_wifi
     
    def read_conn(self) -> (str, str):
        # Read the current WiFi connection file
        if self._prfx == None:
            self.__sd_card()
        if self._iter_wifi == None:
            log.debug('No wifi iterator yet - start one')
            self.__wifi()
        if not self._more_wifi:
            log.debug('No more wifi configurations to read')
            return None, None
        log.debug('Read connection from %s', self._wifi_config)
        wifi: dict = self.__read_conf(self._wifi_config)
        # Move the iter on
        try:
            self._wifi_config = str(next(self._iter_wifi))
        except StopIteration:
            self._more_wifi = False
        return wifi['ssid'], wifi['password']
    
    # Instead of a track database - we just have profiles
    # 'at' is the current profile.
    # Profile ids are sequential integer numbers.
    # a profile is a track name, track lane, therefore there could be say
    # 4 profiles for Fylde and 5 for Castle etc.
    def use_id(self, id: int) -> None:
        # Update the current profile id
        log.debug('Retrieve and set the working')
        profiles = self.__read_conf(PROFILES_FILE)
        if id <= len(profiles['profiles']):
            profiles['at'] = id
            self.__write_conf(PROFILES_FILE, profiles) # Update the at
            my_profile = profiles['profiles'][id - 1]
            self._profile = Profile(my_profile['track'], my_profile['lane'], my_profile['id'])
        else:
            raise ValueError('No corresponding profile for id:', id) 
        
    def put_profile(self, profile: Profile) -> int:
        # Write back all the profiles
        # If id is not set or 0 - append, else merge
        # TODO Validate it against the track
        log.debug('Create a new profile')
        id: int = profile.id()
        if id == 0:
            log.debug('Create a new profile')
        else:
            log.debug('Update profile %s', id)
        track: str = profile.track()
        lane: str = profile.lane()
        profile_var = {"id": id, "track": track, "lane": lane}
        all_profiles = self.__read_conf(PROFILES_FILE)
        count = len(all_profiles['profiles'])
        if id == 0 or id > count:
            # add/append
            id = count + 1
            profile_var['id'] = id
            all_profiles['profiles'].append(profile_var)
        else:
            # replace
            all_profiles['profiles'][id - 1] = profile_var
        self.__write_conf(PROFILES_FILE, all_profiles)
        return id
    
    def read_profiles(self):
        # Read the profiles, set the profile to the one that's mine
        log.debug('Reading all profiles, and setting to mine')
        all_profiles = self.__read_conf(PROFILES_FILE)
        me = all_profiles['at']
        if len(all_profiles['profiles']) > me - 1:
            my_profile = all_profiles['profiles'][me - 1]
            self._profile = Profile(my_profile['track'], my_profile['lane'], my_profile['id'])
        else:
            raise ValueError('No corresponding profile for id:', me)
          
    def get_profile(self) -> Profile:
        if self._profile == None:
            self.read_profiles()
        return self._profile
     
    def get_sdcard(self) -> (int, int, int, int, int, int):
        return 1, 10, 11, 8, 9, 0x14<<20

    def __str__(self) -> str:
        if self._profile != None:
            buf = str(self._profile) + ' '
        if self._wifi != None:
            buf += 'Wifi: ' + self._wifi + ' '
        if self._prfx != None:
            buf += 'Prefix: ' + self._prfx + ' ' 
        if self._more_wifi != None:
            buf += 'More wifi: ' + str(self._more_wifi) + ' '
        if self._iter_wifi != None:
            buf += 'Iter: ' + str(self._iter_wifi) + ' '
        if self._wifi_config != None:
            buf += 'Wifi config: ' + self._wifi_config 
        return buf
    
    def my_id(self) -> str:
        return self._my_id
            
if __name__ == "__main__":
    try:
        the_config
    except NameError:
        log.info('the_config not yet defined')
        the_config = Config()
    log.debug(the_config.my_id())
    ssid, pwd = the_config.read_conn()
    while True:
        if ssid == None and pwd == None:
            break
        the_connection.set_ids(ssid, pwd)
        the_connection.connect()
        ssid, pwd = the_config.read_conn()
    if the_connection.connected():
        pass
    log.debug('Not connected')
    the_config.read_profiles()
    the_config.read_conn()
    log.info('Current profile')
    print(the_config)
    log.info('Use profile 6')
    the_config.use_id(6)   # Use profile 6
    print(the_config)
    log.info('Add new profile')
    prof = Profile('Castle', 'yellow', 0) # Adds a new one - return id
    newid = the_config.put_profile(prof)
    log.info('Use new profile %s', newid)
    the_config.use_id(newid)
    print(the_config)

