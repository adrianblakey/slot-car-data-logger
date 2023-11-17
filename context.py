# Copyright @ 2023, Adrian Blakey. All rights reserved
# Carries important objects around
import logging
log = logging.getLogger("context")
global the_context

class Context():
    
    def __init__(self):
        self._context = {}
        
    def put(self, key: str, obj: object):
        self._context[key] = obj
            
    def get(self, key: str) -> object:
        return self._context[key]
        
try:
    the_context
except NameError:
    log.info('the_context not yet defined')
    the_context = Context()
