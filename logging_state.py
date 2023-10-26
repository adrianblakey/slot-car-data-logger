from button import Button
from log_file import Log_File
from led import Led, yellow_led, red_led
import logging

log = logging.getLogger("logging_state")

# Yellow button callback sets this on/off
# on - creates a new log file
# off - closes
class Logging_State():
    
    def __init__(self):
        self._collect: bool = False
        self._log_file = None
                
    def on(self) -> bool:
        return self._collect
    
    def callback(self, button, event):
        log.debug(f'button {button} has been {event}')
        if event == Button.PRESSED:
            log.debug('logging state Button pressed, state: %s', self._collect)
        if event == Button.RELEASED:
            log.debug('Button released, state: %s', self._collect)
            self._collect = not self._collect
            if self._collect:
                log.debug('Start a new log file')
                self._log_file = Log_File()
                yellow_led.on()
            else:
                log.debug('Close log file %s', self._log_file.name())
                self._log_file.close()
                yellow_led.off()

    def get_file(self) -> Log_File:
        return self._log_file