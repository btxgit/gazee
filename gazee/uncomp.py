# .oooooooo  .oooo.     oooooooo  .ooooo.   .ooooo.
# 888' `88b  `P  )88b   d'""7d8P  d88' `88b d88' `88b
# 888   888   .oP"888     .d8P'   888ooo888 888ooo888
# `88bod8P'  d8(  888   .d8P'  .P 888    .o 888    .o
# `8oooooo.  `Y888""8o d8888888P  `Y8bod8P' `Y8bod8P'
# d"     YD
# "Y88888P'
#
# comic database class - btx
#

import os
import logging
try:
    import Queue as queue
except ImportError:
    import queue
    
import threading
from cherrypy.process.plugins import SimplePlugin
from gazee.archive import get_archfiles

log = logging.getLogger(__name__)


class UncompressThread(SimplePlugin):
    _thread = None
    _running = None
    _queue = queue.Queue()
    
    def __init__(self, bus):
        SimplePlugin.__init__(self, bus)
    
    def start(self):
        self.bus.subscribe('files-uncompress', self._do_uncompress)
        self._running = True
        if not self._thread:
            self._thread = threading.Thread(target=self._loop)
            self._thread.start()
    start.priority = 70
        
    def stop(self):
        self.bus.log("Freeing UncompressThread plugin...")
        self.bus.unsubscribe('files-uncompress', self._do_uncompress)
        self._running = False

        if self._thread:
            self._thread.join()
            self._thread = None
    
    def exit(self):
        try:
            self.unsubscribe()
        except:
            self.bus.log("Failed to unsubscribe.")
            
    def _loop(self):
        while self._running:
            arg = self._queue.get()
            self.buf.log("Got an arg: %s" % str(arg))
            arch, outdir, pfx, extract_first = arg

            num = 0
            ao, fnl = get_archfiles(arch)
            
            for fi in fnl:
                num += 1
                bfn, ext = os.path.splitex(ao.filename)
                
                ofn = u'{0}-{1:04d}.{2}'.format(pfx, num, ext.lower())
                opath = os.path.join(outdir, ofn)
                
                with ao.open(bfn, 'r') as archread:
                    with open(opath, 'wb') as fd:
                        fd.write(archread.read())
                    
                    if ((extract_first is not None) and (extract_first >= num)):
                        break
            self._queue.put(fnl)
            
    def _do_uncompress(self, arg):
        self.bus.log("Got a signal in do_uncompress...")
        self._queue.put(arg)
        
        fnl = self._queue.get()
        return fnl
