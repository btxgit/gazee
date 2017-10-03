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
from gazee.comic_db import comic_db
from cherrypy.process.plugins import SimplePlugin
import threading
import time

log = logging.getLogger(__name__)


class ScanDirs(SimplePlugin):
    _thread = None
    _running = None
    _busy = None
    _request_scan = None
    _sleep = None

    _comic_path = None
    _temp_path = None
    _interval = None
    _next_time = None
    _scan_start = None

    def __init__(self, bus, interval = 300, comic_path=None, temp_path=None, sleep = 1):
        SimplePlugin.__init__(self, bus)

        self._cdb = comic_db()
        self._sleep = sleep
        self._interval = interval
        self._comic_path = comic_path
        self._temp_path = temp_path
        self._request_scan = 0

    def start(self):
        self.bus.subscribe('db-scanner-scan', self._do_scan)
        self.bus.subscribe('db-scan-time-get', self._get_scantime)
        self._running = True
        if not self._thread:
            self._thread = threading.Thread(target=self._loop)
            self._thread.start()
    start.priority = 70

    def stop(self):
        self.bus.log("Freeing scanDirs plugin...")
        self.bus.unsubscribe('db-scanner-scan', self._do_scan)
        self.bus.unsubscribe('db-scan-time-get', self._get_scantime)
        self._running = False

        if self._thread:
            self._thread.join()
            self._thread = None

    def exit(self):
        self.unsubscribe()

    def _loop(self):
        while self._running:
            try:
                self._scan_start = time.time()
                self._request_scan = time.time() + self._interval
                self.bus.log("Scheduled %d seconds from now." % self._interval)
                self._busy = True
                self.bus.log("Starting dir tree scanning...")
                self._cdb.scan_directory_tree(self._comic_path, 0)
                self.bus.log("Ended dir scanning...")
                self.bus.log("Starting thumb job...")
                self._cdb.do_thumb_job()
                self.bus.log("Ended thumb job...")
                bpath = os.path.join(self._temp_path, 'Books')
                for username in os.listdir(bpath):
                    self.bus.log("Beginning tempdir clean of user: %s..." % username)
                    opath = os.path.join(bpath, username)
                    self._cdb.clean_out_tempspace(opath, 10)
                    self.bus.log("Tempdir clean for user %s is complete." % username)
                self.bus.log("Completed with tasks.")
            except:
                self.bus.log("Error in dir tree scan plugin.", level = logging.ERROR, traceback = True)

            self._busy = False
            self._scan_start = None

            while self._running and time.time() < self._request_scan:
                time.sleep(self._sleep)

    def _do_scan(self, arg):
        self._comic_path, self._temp_path, self._interval = arg
        self.bus.log("Got request to rescanDB: %s" % str(arg))
        if self._busy:
            self.bus.log("Already busy.")
        else:
            self._request_scan = time.time()

    def _get_scantime(self, arg):
        if self._busy:
            tv = time.time() - self._scan_start
        else:
            tv = -1

        pend, nrec, pct = self._cdb.get_stats()

        rv = (tv, pend, nrec, pct)

        self.bus.log("Returning scantime of %s" % str(rv))

        self.bus.publish('db-scan-time-put', rv)
