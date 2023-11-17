# Copyright @ 2023, Adrian Blakey. All rights reserved
# Yellow button callback to toggle file logging on/off
# Black button - toggle playback of latest file/reatime data

import os
from button import Button
from log_file import Log_File
from led import Led, yellow_led, red_led
import logging
from config import Config

log = logging.getLogger("logging_state")

class Logging_State():
    
    def __init__(self, config: Config):
        self._config: Config = config
        log.debug('Config %s', self._config)
        self._collect: bool = False   # Not collecting data to log file
        self._log_file = None         # Log file name
        self._playback = False        # Not playing back data - realtime
                
    def on(self) -> bool:
        # Writing to file = True
        return self._collect
             
    def playback(self) -> bool:
        # Playing back file  = True
        return self._playback
    
    def playback_off(self) -> None:
        self._playback = False
        red_led.off()
    
    def yellow_callback(self, button, event):
        # Toggle on/off save data to log file
        log.debug(f'yellow button {button} has been {event}')
        if event == Button.PRESSED:
            log.debug('logging state Button pressed, state: %s', self._collect)
        elif event == Button.RELEASED:
            log.debug('Button released, state: %s', self._collect)
            self._collect = not self._collect
            if self._collect:
                if self._playback:
                    log.info('Turn off playback while we collect')
                    self._playback = False
                    red_led.off()
                log.debug('Start a new log file')
                self._log_file = Log_File()
                fn = self._log_file.new_for_append(None)
                yellow_led.on()
            else:
                log.debug('Stop logging to %s', self._log_file.name())
                yellow_led.off()
        else:
            raise RuntimeError("Can't happen - unrecognized event %s", event)
        
    def black_callback(self, button, event):
        # Toggle playback/realtime data
        log.debug(f'black button {button} has been {event}')
        if event == Button.PRESSED:
            log.debug('logging playback button pressed, state: %s', self._playback)
        elif event == Button.RELEASED:
            log.debug('logging playback button released, state: %s', self._playback)
            self._playback = not self._playback
            if self._playback:
                log.debug('Red led on for playback')
                red_led.on()
                if self._collect:
                    # TODO Pend this and turn back on after replay?
                    log.info('Turn off logging to disk while we replay')
                    self._collect = False
                    yellow_led.off()
                self._log_file = Log_File()
                self._log_file.set_name(self.__get_latest_file())
            else:
                log.debug('Revert to realtime')
                red_led.off()
        else:
            raise RuntimeError("Can't happen - unrecognized event %s", event)
            
    def get_file(self) -> Log_File:
        return self._log_file
    
    def __get_latest_file(self) -> str:
        log_config = [l for l in os.listdir(self._config.prfx()) if l.endswith('log')]
        log_config.sort(reverse=True)
        return log_config[0]
        

