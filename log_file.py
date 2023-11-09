# Copyright @ 2023, Adrian Blakey. All rights reserved
# Write a log of values as comma delim string
# Checks every 1000 writes if the fs is too full and stops writing
import os
import logging
import time

log = logging.getLogger("log_file")

class Log_File():
    
    def __init__(self, fname: str):
        self._prevent_write: bool = False
        self._ct: int = 0
        if fname is None:
            (year, month, mday, hour, minute, second, weekday, yearday) = time.localtime()
            self._fname = str(year) + '_' + str(month) + '_' + str(mday) + '_' + str(hour) + '_' + str(minute) + '_' + str(second) + '.log'
        else:
            self._fname = fname
        log.debug('Fname: %s', self._fname)
        self._file = open(self._fname, 'a')
        if self._fs_full():
            self._file.write('fs full')
            self._file.close()
            
    def _fs_full(self) -> bool:
        info = os.statvfs(".")
        if info[3] <= 1:
            self._prevent_write = True
        else:
            self._prevent_write = False
        return self._prevent_write
    
    def _str(self, info):
        log.debug("written:          %s", self._ct)
        log.debug("fs block size:    %s", info[0])
        log.debug("fs fragment size: %s", info[1])
        log.debug("fs blocks:        %s", info[2])
        log.debug("free blocks:      %s", info[3])
        
    def name(self) -> str:
        return self._fname
    
    def log(self, rec):
        self._file.write(rec + '\n')
        self._ct += 1
        if self._ct % 1000 == 0:
            if self._fs_full():
                self._file.close()

    def close(self):
        self._file.close()


if __name__ == "__main__":
    lfile = Log_File()
    for _ in range(2000):   # 10 secs
        lfile.log('12.00001, 12.00001, 12.00002')
    lfile.close()

