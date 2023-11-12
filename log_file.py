# Copyright @ 2023, Adrian Blakey. All rights reserved
# Read/Write a log of values as comma delim string
# Checks every 1000 writes if the fs is too full and stops writing
import os
import logging
import time

log = logging.getLogger("log_file")

class Log_File():
    
    def __init__(self):
        self._prevent_write: bool = False # stops filling fs
        self._ct: int = 0
        self._fname = None
        self._file = False
        self._eof = False

    def _fs_full(self) -> bool:
        log.debug('Checking fs full')
        if not self._prevent_write:
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
             
    def new_for_append(self, fname: str = None) -> str:
        # Start a new log file for appeding - if fs not full
        if self._prevent_write:
            log.info("Fs full")
            self._fname = None
        else:
            if fname is None:
                (year, month, mday, hour, minute, second, weekday, yearday) = time.localtime()
                m = "%02d" % month
                md = "%02d" % mday
                h = "%02d" % hour
                min = "%02d" % minute
                s = "%02d" % second
                self._fname = str(year) + '_' + m + '_' + md + '_' + h + '_' + min + '_' + s + '.log'
            else:
                self._fname = fname
            log.debug('Fname: %s', self._fname)
        return self._fname
    
    def new_for_read(self, n: int = 0) -> str:
        # Get the latest (or latest - n) log file for reading
        # Get the file prefix from config - usibg context?
        log_config = [l for l in os.listdir(self._config.prfx()) if l.endswith('log')]
        log_config.sort(reverse=True)
        self._fname = log_config[n]
        return self._fname
    
    def read_next(self) -> str:
        # Read next record in file
        rec = None
        if not self._eof:
            try:
                if not self._file:
                    log.debug('open for read %s %s', self._fname, self._ct)
                    self._file = open(self._fname, "r")     
                rec = self._file.readline()
                if len(rec) == 0:
                   self._eof = True
                else:
                    self._ct += 1
            except OSError as ex:
                self._eof = True
                log.info('File open/read issue %s %s', self._fname , ex)
        return rec
    
    def name(self) -> str:
        return self._fname
    
    def set_name(self, fname) -> None:
        self._fname = fname
    
    def eof(self):
        return self._eof
        
    def log(self, rec) -> bool:
        rc = False
        if not self._prevent_write:
            try:
                with open(self._fname, "a") as log_file:
                    log.debug('write %s', rec)
                    log_file.write(rec + '\n')
                    rc = True
                    self._ct += 1
                    if self._ct % 100 == 0:
                        self._fs_full()
            except OSError as e:
                log.error('Unable to open/write %s %s', self._fname, e)
                self._fname = None
        else:
            log.info('fs full - logging stopped')
        
    def close(self):
        pass


if __name__ == "__main__":
    lfile = Log_File()
    log.debug('New for append write 2000')
    lfile.new_for_append()
    for _ in range(2000):   # 10 secs
        lfile.log('12.00001, 12.00001, 12.00002')
    lfile.close()
    rfile = Log_File()
    fn = rfile.new_for_read()
    log.debug('Reading %s', fn)
    r = rfile.read_next()
    while not rfile.eof():
        r = rfile.read_next()



