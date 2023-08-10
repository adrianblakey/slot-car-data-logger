import os
import adafruit_logging as logging


log_dict = {"DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL}

loglevel = os.getenv("LOGLEVEL", "ERROR")   # Nothing set - then error log
logger = logging.getLogger(__file__)
logger.setLevel(log_dict[loglevel])
is_debug: bool = False
is_info: bool = False
is_warning: bool = False
is_error: bool = False
is_error: bool = False
is_critical: bool = False

_level = logger.getEffectiveLevel()
if 10 == _level < 20:
    is_debug = True
elif 20 == _level < 30:
    is_info = True
elif 30 == _level < 40:
    is_warning = True
elif 40 == _level < 50:
    is_error = True
elif 50 == _level < 60:
    is_critical = True

