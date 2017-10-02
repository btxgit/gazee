#  This file is part of Gazee.
#
#  Gazee is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Gazee is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Gazee.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import cherrypy
from cherrypy.process.plugins import SimplePlugin
import logging
import subprocess
import threading
import json
import time

from mako.lookup import TemplateLookup
from mako import exceptions

import gazee.config
from gazee.comic_db import comic_db
from gazee.gazee_settings_db import gazee_settings
from gazee.versioning import current_version, latest_version
from gazee.dbscan import ScanDirs

"""
This initializes our mako template serving directory and allows us to return it's compiled embeded html pages rather than the default return of a static html page.
"""

def serve_template(templatename, **kwargs):
    html_dir = 'public/html/'
    _hplookup = TemplateLookup(directories=[html_dir])
    try:
        template = _hplookup.get_template(templatename)
        return template.render(**kwargs)
    except:
        return exceptions.html_error_template().render()

"""
Web Pages/Views methods that are exposed for API like url calling.
"""

class Gazeesrv(object):
    def __init__(self):
        """ Initialize the class, kick off a rescan thread.
        """
        self.cdb = comic_db()
        self.gset = gazee_settings()
        self.gcfg = gazee.gcfg()
        logging.basicConfig(level=logging.DEBUG, filename=os.path.join(gazee.config.DATA_DIR, 'gazee.log'))
        self.logger = logging.getLogger(__name__)
        self.bus = cherrypy.engine
        self._scan_time = None
        self._pending = None
        self._numrecs = None
        self._pct = None
        self.bus.subscribe('db-scan-time-put', self._get_scan_time)

    def _get_scan_time(self, arg):
        self._scan_time, self._pending, self._numrecs, self._pct = arg
        self.logger.debug("Got scan time of: %s" % self._scan_time)
        self.logger.debug("Pending: %d  nrec: %d   pct: %.2f%%", self._pending, self._numrecs, self._pct * 100.0)
        
    def _request_scan_time(self):
        self.logger.debug("Requesting scan time.")
        self.bus.publish('db-scan-time-get', 0)

    def pag(self, cur, last):
        """ Work out pagination based on the current (cur) and last pages.
        """
        delta = 5

        left = cur - delta
        right = cur + delta + 1
        trl = []
        rangeWithDots = []
        l = None

        trl.append(1)
        for i in range(cur-delta, (cur + delta + 1)):
            if (i < last and i > 1):
                trl.append(i)

        if (last != 1):
            trl.append(last)

        for i in trl:
            if l is not None:
                if (i - l == 2):
                    rangeWithDots.append(l + 1)
                elif (i - l != 1):
                    rangeWithDots.append("...")
            rangeWithDots.append(i)
            l = i
        return rangeWithDots

    """
    Index Page
    This returns the html template for the recents div.
    The recents div is by default the the last twenty comics added to the DB in the last 7 days.
    """
    @cherrypy.expose
    def index(self, page_num=1, recent=False):
        if not isinstance(page_num, int):
            page_num = int(page_num, 10)

        self.logger.info("Index Requested")

        comics_per_page = int(gazee.config.COMICS_PER_PAGE)

        if recent:
            num_of_comics = self.cdb.get_recent_comics_count(7)
            print("Recent comics count: %d" % num_of_comics)
        else:
            num_of_comics = self.cdb.get_all_comics_count()
            print("All comics count: %d" % num_of_comics)

        num_of_pages = (num_of_comics // comics_per_page)
        if num_of_comics % comics_per_page > 0:
            num_of_pages += 1

        if  (page_num > num_of_pages):
            page_num = 1

        if page_num == 1:
            PAGE_OFFSET = comics_per_page * (page_num - 1)

        comics = self.cdb.get_comics(7, comics_per_page, page_num, recentonly=recent)

        user = cherrypy.request.login
        user_level = self.gset.get_user_level(user)

        num_comics, num_recent, bytes_str = self.cdb.get_comics_stats()

        pages = self.pag(page_num, num_of_pages)
        self.logger.info("Pages: %s", pages)
        return serve_template(templatename="index.html", comics=comics, num_of_pages=num_of_pages, current_page=int(page_num), pages=pages, user_level=user_level, maxwid=gazee.config.THUMB_MAXWIDTH, maxht=gazee.config.THUMB_MAXHEIGHT, num_comics=num_comics, num_recent=num_recent, total_bytes=bytes_str)

    @cherrypy.expose
    def aindex(self, page_num=1, recent=False):
        """ Ajax Index Page
        This returns the html template that just has the pagination and the comic view
        """
        self.logger.info("Index Requested")
        if not isinstance(page_num, int):
            page_num = int(page_num, 10)

        comics_per_page = int(gazee.config.COMICS_PER_PAGE)

        if not recent:
            num_of_comics = self.cdb.get_recent_comics_count(7)
        else:
            num_of_comics = self.cdb.get_all_comics_count()

        num_of_pages = 0

        num_of_pages = (num_of_comics // comics_per_page)
        if num_of_comics % comics_per_page > 0:
            num_of_pages += 1

        if page_num == 1:
            PAGE_OFFSET = 0
        else:
            PAGE_OFFSET = comics_per_page * (page_num - 1)

        param = (comics_per_page, PAGE_OFFSET)

        comics = self.cdb.get_comics(7, comics_per_page, page_num, recent)
        user = cherrypy.request.login
        user_level = self.gset.get_user_level(user)

        self.logger.info("Index Served")

        pages = self.pag(page_num, num_of_pages)
        self.logger.info("Pages: %s", pages)
        return serve_template(templatename="aindex.html", comics=comics, num_of_pages=num_of_pages, current_page=int(page_num), pages=pages, user_level=user_level, maxht=gazee.config.THUMB_MAXHEIGHT, maxwid=gazee.config.THUMB_MAXWIDTH)

    @cherrypy.expose
    def cidnav(self, cid=-1):
        """ Returns JSON string with the previous and next title's comicIds as well as the title and # of pages of the current book
        """
        if not isinstance(cid, int):
            cid = int(cid, 10)
            
        ctup = self.cdb.get_nextprev_cids(cid, True)
        d = {'PrevCID': ctup[0], 'NextCID': ctup[1], 'Title': ctup[2], 'Pages': ctup[3]}
        self.logger.debug(d)
        return json.dumps(d)

    @cherrypy.expose
    def search(self, page_num=1, search_string=''):
        """
        """
        if not cherrypy.session.loaded:
            cherrypy.session.load()
        if 'sizepref' not in cherrypy.session:
            cherrypy.session['sizepref'] = 'wide'
        if 'dblpagepref' not in cherrypy.session:
            cherrypy.session['dblpagepref'] = '2'
        self.logger.info("Search Requested")

        user = cherrypy.request.login
        user_level = self.gset.get_user_level(user)

        self.logger.info("Search Served")

        return serve_template(templatename="search.html", comics=comics, num_of_pages=num_of_pages, current_page=int(page_num), user_level=user_level, search_string=search_string)

    """
    This returns the library view starting with the root library directory.
    """
    # Library Page
    @cherrypy.expose
    def library(self, parent, directory, page_num=1):
        if not cherrypy.session.loaded:
            cherrypy.session.load()
        if 'sizepref' not in cherrypy.session:
            cherrypy.session['sizepref'] = 'wide'
        self.logger.info("Library Requested")
        comics=[]
        user = cherrypy.request.login
        user_level = self.gset.get_user_level(user)

        return serve_template(templatename="library.html", directories=directories, comics=comics, parent_dir=prd, num_of_pages=num_of_pages, current_page=int(page_num), current_dir=directory, user_level=user_level)

    @cherrypy.expose
    def cover(self, id=-1):
        """ Returns the cover thumbnail for comicid <id>
        """
        if not isinstance(id, int):
            id = int(id, 10)
        self.logger.debug("In /cover for id=%d", id)

        cpath = self.cdb.get_cache_path(id, gazee.config.THUMB_MAXWIDTH, gazee.config.THUMB_MAXHEIGHT)
        self.logger.info("Looking for the cover %d in directory: %s" % (id, cpath))
        if os.path.exists(cpath):
            cherrypy.response.headers['Content-Type'] = 'image/jpeg'
            fsize = os.path.getsize(cpath)
            self.logger.debug("Cover file #%d is %d bytes.", id, fsize)
            with open(cpath, 'rb') as imgfd:
                return imgfd.read()
        else:
            self.logger.warning("Cover %d is missing!", id)

    @cherrypy.expose
    def read_comic(self, cid=-1, ncid=-1, pcid=-1, page_num=-1):
        self.logger.info("Reader Requested")

#        print(cherrypy.session)

        if not cherrypy.session.loaded:
            cherrypy.session.load()
        username = cherrypy.request.login

        if not isinstance(cid, int):
            cid = int(cid, 10)
        if not isinstance(page_num, int):
            page_num = int(page_num, 10)

        pcid, ncid, title, pages = self.cdb.get_nextprev_cids(cid, True)

        opath = "%s/Books/%s/%d" % (gazee.config.TEMP_PATH, username, cid)

        image_list = self.cdb.do_extract_book(cid, username)
        num_pages = len(image_list)

        if not os.path.exists(opath):
            os.makedirs(opath, 0o755)
            image_list = []
        if num_pages == 0:
            image_list = ['static/images/imgnotfound.png']
            num_pages = len(image_list)

        next_page = page_num + 1 if (page_num + 1) <= num_pages else num_pages

        cookie_comic = "comicbook%d" % cid
        cookie_check = cherrypy.request.cookie

        if cookie_comic not in cookie_check:
            self.logger.debug("Cookie Creation")
            cookie_set = cherrypy.response.cookie
            page_num = 1 if (page_num == -1) else page_num
            cookie_set[cookie_comic] = page_num
            cookie_set[cookie_comic]['path'] = '/'
            cookie_set[cookie_comic]['max-age'] = 2419200
            next_page = 2
        else:
            self.logger.debug("Cookie Read")
            if (page_num == -1):
                page_num = int(cookie_check[cookie_comic].value)
            self.logger.debug("Cookie Set To %d" % page_num)
            next_page = page_num + 1

        now_page = "read_page?cid=%d&page_num=%d" % (cid, page_num)
        self.logger.debug("now_page is: %s" % now_page)
        userSizePref = "norm";
        dblpagepref = cherrypy.session['dblpagepref']
        return serve_template(templatename="read.html", pages=image_list, current_page=page_num, np=next_page, nop=num_pages, size=userSizePref, dblpage=dblpagepref, now_page=now_page, cid=cid, prevcid=pcid, nextcid=ncid, cc=cookie_comic, title=title)

    @cherrypy.expose
    def read_page(self, cid=-1, page_num=1):
        """ This page returns the image corresponding to <page_num> in comicid=cid
        """
        self.logger.info("read_page requested cid: %s  page_num: %s" % (cid, page_num))

        if not cherrypy.session.loaded:
            cherrypy.session.load()
        username = cherrypy.request.login

        if not isinstance(cid, int):
#            print(cid)
            cid = int(cid, 10)

        if not isinstance(page_num, int):
            page_num = int(page_num, 10)

        opath = "%s/Books/%s/%d" % (gazee.config.TEMP_PATH, username, cid)

        if not os.path.exists(opath):
            return "fail"

        image_list = [ os.path.join(opath, fn) for fn in sorted(os.listdir(opath)) ]
        num_pages = len(image_list)

        if (num_pages == 0):
            self.logger.error("cid %d doesn't exist at path: %s" % (cid, opath))
            return "fail"

        if page_num > num_pages:
            page_num = num_pages
        elif page_num < 1:
            page_num = 1

        gfile = image_list[page_num - 1]

        imgt = ""
        if gfile.endswith('.jpg'):
            imgt = "jpeg"
        elif gfile.endswith('.png'):
            imgt = "png"
        elif (gfile.endswith('.gif')):
            imgt = "gif"

        cherrypy.response.headers['Content-Type'] = 'image/%s' % imgt
        with open(gfile, 'rb') as imgfd:
            return imgfd.read()

    @cherrypy.expose
    def dlbook(self, id=-1):
        """ Download comicid=<id> as disposition attachment in the browser.
        """
        p = self.cdb.get_comic_path(id)

        if p is None:
            return
        bnp = os.path.basename(p)
        self.logger.info("Downloading path: %s  name: %s", p, bnp)

        return cherrypy.lib.static.serve_file(p, content_type='application/octet-stream', disposition='attachment')

    """
    Returns the current settings in JSON
    """
    @cherrypy.expose
    def load_settings(self):
        res = "%sx%s" % (gazee.config.THUMB_MAXWIDTH, gazee.config.THUMB_MAXHEIGHT)

        d = {'comicPath': gazee.config.COMIC_PATH, 'scanInterval': gazee.config.COMIC_SCAN_INTERVAL, 'perPage': gazee.config.COMICS_PER_PAGE, 'thumbRes': res, 'scanInterval': gazee.config.COMIC_SCAN_INTERVAL}
        return json.dumps(d)

    @cherrypy.expose
    @cherrypy.tools.accept(media='text/plain')
    def save_settings(self, cpinput=None, nppinput=None, csiinput=None, thumbsel=None, ssslKey=None, ssslCert=None, smylarPath=None, postproc=0, sport=4242):
        # Set these here as they'll be used to assign the default values of the method arguments to the current values if they aren't updated when the method is called.
        self.gcfg.configRead()

        wid, ht = thumbsel.split('x')

        newvals = {'GLOBAL': {'port': str(sport), 'comic_path': cpinput, 'comics_per_page': nppinput, 'comic_scan_interval': csiinput, 'thumb_maxwidth': wid, 'thumb_maxheight': ht, 'mylar_db': smylarPath, 'ssl_key': ssslKey, 'ssl_cert': ssslCert}}

        self.gcfg.updateCfg(newvals)
        self.logger.info("Settings Saved")
        return self.load_settings()
#        self.restart()
#        return

    @cherrypy.expose
    def changePassword(self, password):
        user = cherrypy.request.login
        self.gset.change_pass(user, password)
        self.logger.info("Password Changed")
        return

    @cherrypy.expose
    def newUser(self, username, password, usertype):
        self.gset.add_user(username, password, usertype)
        self.logger.info("New User Added")
        return

    @cherrypy.expose
    def delUser(self, username):
        self.gset.del_user(username)
        self.logger.info("User Deleted")
        return

    @cherrypy.expose
    def shutdown(self):
        cherrypy.engine.exit()
        threading.Timer(1, lambda: os._exit(0)).start()
        self.logger.info('Gazee is shutting down...')
        return

    @cherrypy.expose
    def restart(self):
        cherrypy.engine.exit()
        popen_list = [sys.executable, gazee.FULL_PATH]
        popen_list += gazee.ARGS
        self.logger.info('Restarting Gazee with ' + str(popen_list))
        subprocess.Popen(popen_list, cwd=os.getcwd())
        os._exit(0)
        self.logger.info('Gazee is restarting...')
        return

    @cherrypy.expose
    def updateGazee(self):
        self.logger.info('Gazee is restarting to apply update.')
        self.restart()
        return

    @cherrypy.expose
    def get_scantime(self):
       self._request_scan_time()
       time.sleep(0.2)
       d = {'scan_time': self._scan_time, 'pending': self._pending, 'numrecs': self._numrecs, 'pct': self._pct}
       return json.dumps(d)
        
    @cherrypy.expose
    def do_rescan(self):
        a = (gazee.config.COMIC_PATH, gazee.config.TEMP_PATH, (gazee.config.COMIC_SCAN_INTERVAL * 60))
        self.bus.publish('db-scanner-scan', a)
        self._request_scan_time()
        return '''<html><head><meta http-equiv="refresh" content="1;URL='/get_scantime'" /></head></html>'''

