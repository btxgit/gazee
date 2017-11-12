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
import sqlite3
import shutil
import math
import glob
import time
import logging
from multiprocessing import Pool
from gazee.archive import extract_thumb, extract_archive
from gazee.db import gazee_db
from gazee.filenameparser import FileNameParser
import gazee.config

log = logging.getLogger(__name__)

def sizestr(num, dplaces=2, minunit=False):
    """ Handy class for outputting bytes into kilo/mega/giga/etc
    """
    units = ['B', 'kiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']
    unit = None

    if num == 0:
        return "0B"
    exponent = min(int(math.log(num) / math.log(1024)), len(units) - 1)
    n = (float(num) / pow(1024, exponent))
    unit = units[exponent]
    if minunit:
        unit = unit[0]
    fmtstr = '%c.%df%s%s' % ('%', dplaces, '' if minunit else ' ', unit)
    return fmtstr % n


class comic_db(gazee_db):
    SCHEMA_VERSION = 2
    dir_cache = {}
    fn_cache = {}
    last_thumb_time = None

    c = None

    def __init__(self):
        self.dbpath = comic_db.get_dbpath(self)
        self.init_db()
        self.fnp = FileNameParser()
        self.reset_unprocessed_thumbs()

        self._pending = 0
        self._numrecs = 0
        self._pct = None
        print("gazee_comics.db is: %s" % self.dbpath)

    def get_stats(self):
        return (self._pending, self._numrecs, self._pct)

    def get_db_name(self):
        return 'gazee_comics.db'
        
    def create_db(self):
        conn = sqlite3.connect(self.dbpath)
        sql = '''CREATE TABLE IF NOT EXISTS all_directories(dirid INTEGER PRIMARY KEY AUTOINCREMENT, parentid INTEGER NOT NULL, full_dir_path TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dir_names(dirid INTEGER PRIMARY KEY, nice_name TEXT NOT NULL, dir_image TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS all_comics(comicid INTEGER PRIMARY KEY AUTOINCREMENT, dirid INTEGER NOT NULL, filename TEXT NOT NULL COLLATE NOCASE, filesize INTEGER DEFAULT 0, pages integer DEFAULT 0, image TEXT, seriesid integer NOT NULL, issue INTEGER, publisher integer, volume INTEGER, summary TEXT, width integer, height integer, ratio real, adddate datetime DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS comic_series(seriesid INTEGER PRIMARY KEY AUTOINCREMENT, collname TEXT NOT NULL, name TEXT NOT NULL);
INSERT INTO comic_series(seriesid, collname, name) VALUES (1, "unknown", "Unknown");
CREATE TABLE IF NOT EXISTS publishers (pubid integer primary key autoincrement, name);
CREATE VIEW IF NOT EXISTS comicdirs AS SELECT d.dirid as dirid, c.comicid AS comicid, d.full_dir_path || '/' || c.filename as fullpath, c.image as image FROM all_directories d INNER JOIN all_comics c ON (d.dirid=c.dirid);
CREATE INDEX IF NOT EXISTS fnindex ON all_comics(filename ASC);
CREATE INDEX IF NOT EXISTS dirindex ON all_directories(full_dir_path);
CREATE INDEX IF NOT EXISTS comicdir ON all_comics(dirid, filename ASC);
CREATE INDEX IF NOT EXISTS thumbproc ON all_comics(image ASC);
CREATE INDEX IF NOT EXISTS seriesnum on all_comics(seriesid ASC);
CREATE INDEX IF NOT EXISTS seriesord on comic_series(name ASC);
CREATE INDEX IF NOT EXISTS seriescollord on comic_series(collname ASC);'''
        log.debug("Executing creation of SQL database: %s with SQL: %s",
                  self.dbpath, sql)
        conn.executescript(sql)
        conn.commit()
        log.debug("FInished committing the new %s", self.dbpath)
        conn.close()

        self.set_schema_version(self.SCHEMA_VERSION)

    def check_migrate_db(self):
        curver = self.get_schema_version()
        with sqlite3.connect(self.dbpath) as conn:
            while curver < self.SCHEMA_VERSION:
                curver += 1
                if 2 == curver:
                    q = ''''''
                    conn.execute(q)
                    conn.commit()

        self.set_schema_version(self.SCHEMA_VERSION)

    def get_dirid_by_path(self, p):
        param = (os.path.normpath(p), )
        sql = '''SELECT dirid FROM all_directories WHERE full_dir_path=?'''
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as conn:
            curs = conn.cursor()

            row = curs.execute(sql, param).fetchone()
            if row is None:
                return None
            
        return row[0]

    def add_dir_entry(self, parentid, p):
        param = (parentid, os.path.normpath(p))
        sql = '''INSERT INTO all_directories(parentid, full_dir_path) VALUES (?, ?)'''
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as conn:
            curs = conn.cursor()

            curs.execute(sql, param)
            conn.commit()
        
        did = curs.lastrowid
        return did

    def get_all_books_in_dirid(self, dirid):
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as conn:
            curs = conn.cursor()
            sql = '''SELECT comicid FROM all_comics WHERE dirid=?'''
            param = (dirid, )

            books = curs.execute(sql, param).fetchall()
            
        return books

    def clean_out_tempspace(self, cdir, maxkeep):
        dl = []

        for dn in os.listdir(cdir):
            fp = os.path.join(cdir, dn)
            if not os.path.isdir(fp):
                continue

            dl.append((fp, os.stat(fp)))

        dl.sort(key=lambda x: x[1].st_ctime, reverse=True)

        dellist = dl[maxkeep:]

        log.debug("Delete list is: %s", dellist)

        for dpt in dellist:
            dp = dpt[0]
            log.info("Deleting %s", dp)
            shutil.rmtree(dp)

    def delete_stale_directory_entries(self):
        self.fn_cache = {}
        self.dir_cache = {}

        sql = '''SELECT * FROM comicdirs ORDER BY dirid ASC, comicid ASC;'''

        deldl = []
        delcl = []

        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as conn:
            curs = conn.cursor()

            dn = None
            for row in curs.execute(sql):
                did, cid, fp, image = row

                fdp, fn = os.path.split(fp)

                if not os.path.exists(fp):
                    delcl.append((did, ))

                if dn != did:
                    dn = did
                    if not os.path.exists(fdp) or not os.path.isdir(fdp):
                        log.info('The pathname %s (dirid: %d) no longer exists.',
                                 fdp, did)
                        deldl.append((did, ))
                        delcl.append((did, ))
                    else:
                        self.dir_cache[fdp] = did

                if did not in self.fn_cache:
                    self.fn_cache[did] = {fn: cid}
                else:
                    self.fn_cache[did][fn] = cid

            delthumbcl = []

            if len(delcl) > 0:
                numdel = 0
                for did in deldl:
                    sql = '''SELECT comicid FROM all_comics WHERE dirid=?'''
                    for row in conn.execute(sql, (did, )):
                        cid = row[0]
                        delthumbcl.append((cid))
                        cachepath = self.get_cache_path(cid)
                        for cp in glob.glob(cachepath + "/%d-*.jpg" % cid):
                            if os.path.exists(cp):
                                os.unlink(cp)
                                numdel += 1

                log.info("Deleted %d covers." % numdel)
                sql = '''DELETE FROM all_directories WHERE (dirid=?)'''
                conn.executemany(sql, deldl)
                sql = '''DELETE FROM all_comics WHERE (dirid=?)'''
                conn.executemany(sql, delcl)
                conn.commit()

        return

    def get_cache_path(self, cid, twid=-1, tht=-1, forceproc=0):
        CACHE_PER_DIR = 512
        part = (cid // CACHE_PER_DIR)
        resext = "%dx%d" % (twid, tht) if twid > 0 else "native"

        cachepath = os.path.join(gazee.config.TEMP_DIR, 'cache', str(part))
#        log.debug("Cache directory is: %s", cachepath)
        if twid == -1:
            return cachepath

        if not os.path.exists(cachepath):
            os.makedirs(cachepath, mode=0o755)

        cfn1 = 'p%d-%s.jpg' % (cid, resext)
        cp1 = os.path.join(cachepath, cfn1)
        if forceproc == 1:
            return cp1
        cfn2 = '%d-%s.jpg' % (cid, resext)
        cp2 = os.path.join(cachepath, cfn2)
        if forceproc == 2:
            return cp2
        elif forceproc == 3:
            return (cp1, cp2)

        if os.path.exists(cp1):
            return cp1

        return cp2

    def reset_missing_covers(self, wid, ht):
        timenow = time.time()

        if ((self.last_thumb_time is not None) and
           ((self.last_thumb_time + 120) > timenow)):
            log.debug("Too soon after a thumb to reset_missing_covers()")
            return

        resetids = []
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            sql = '''SELECT comicid FROM all_comics WHERE image is not null;'''
            for row in con.execute(sql):
                cid = row[0]
                tpt = self.get_cache_path(cid, wid, ht, 3)
                if not os.path.exists(tpt[0]) and not os.path.exists(tpt[1]):
                    resetids.append((cid, ))

        log.info("Resetting %d image fields to add in support"
                 "for thumbs that are %dx%d.", len(resetids), wid, ht)

        sql = '''UPDATE all_comics SET image=null WHERE comicid=?'''

        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            con.executemany(sql, resetids)
            con.commit()
            
    def scan_directory_tree(self, curdir, parentid):
        log.debug("Scanning comic dir: %s" % curdir)
        self.delete_stale_directory_entries()
        num_fn_added = 0
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            for dirpath, dirnames, filenames in os.walk(curdir, topdown=False, followlinks=True):
                addfns = []
                p = os.path.normpath(dirpath)
                if p not in self.dir_cache:
                    curdirid = self.add_dir_entry(parentid, p)
                    self.dir_cache[p] = curdirid
                else:
                    curdirid = self.dir_cache[p]

                for ttfn in filenames:
                    if not isinstance(ttfn, str):
                        ttfn = str(ttfn, 'utf-8')
                    tmpfn, tmpext = os.path.splitext(ttfn)
                    if not tmpext.lower() in ['.cbr','.cbz']:
                        continue

                    if curdirid not in self.fn_cache:
                        self.fn_cache[curdirid] = {}
                    if ttfn not in self.fn_cache[curdirid]:
                        cfn = os.path.normpath(os.path.join(p, ttfn))
                        filebytes = os.path.getsize(cfn)
                        addfns.append((curdirid, ttfn, filebytes))

                if len(addfns) > 0:
                    num_fn_added += len(addfns)
                    sql = '''INSERT INTO all_comics(seriesid, dirid, filename, filesize) VALUES (1, ?, ?, ?)'''
                    con.executemany(sql, addfns)
                    con.commit()
                    log.info("Added %d new comic files.", len(addfns))

                parentid = curdirid

            if (num_fn_added > 0):
                log.info("Added %d comics" % num_fn_added)
                

    def update_comic_image(self, cid, val, width, height):

        ratio = (1.0) * width / height if (height != 0) else 0.0

        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:

            sql = '''UPDATE all_comics SET image=?, width=?, height=?, ratio=? WHERE comicid=?;'''
            param = (val, width, height, ratio, cid)
            con.execute(sql, param)
            con.commit()
    
    def collate_series(self, series):
        newseries = ''
        
        for c in series:
            if not c.isalnum():
                continue
            c = c.lower()
            newseries += c
        
        return newseries
        
    def find_or_add_series(self, name):
        newseries = self.collate_series(name)
        
        sql = '''SELECT seriesid FROM comic_series WHERE collname=?'''
        param = (newseries, )

        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            for row in con.execute(sql, param):
                return row[0]

            sql = '''INSERT INTO comic_series(collname, name) VALUES (?, ?)'''
            curs = con.cursor()
            param = (newseries, name)
            curs.execute(sql, param)
            sid = curs.lastrowid
            con.commit()
            return sid

    def update_comic_meta(self, cid, num_pages, series, issue):
        sid = self.find_or_add_series(series)
        
        sql = '''UPDATE all_comics SET seriesid=?,issue=?,pages=? WHERE comicid=?;'''
        param = (sid, issue, num_pages, cid)
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            con.execute(sql, param)
            con.commit()

    def get_comic_path(self, cid):
        sql = '''SELECT comicid, d.full_dir_path || '/' || c.filename as fullpath FROM all_comics c INNER JOIN all_Directories d ON (c.dirid=d.dirid) WHERE (c.comicid=?)'''
        params = (cid, )

        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            tpath = None

            for row in con.execute(sql, params):
                comicid, tpath = row

        if tpath is None:
            log.error("Got back no results for CID: %d", cid)
        else:
            log.debug("CID: %d returned path: %s", comicid, tpath)
        return tpath

    def get_thumb_to_process(self, batchsize=1):
        sql = '''SELECT c.comicid, d.full_dir_path || '/' || c.filename as fullpath FROM all_comics c INNER JOIN all_Directories d ON (c.dirid=d.dirid) WHERE (c.image is null) LIMIT ?'''
        cid = fullpath = None

        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            curs = con.cursor()

            rv = []

            for row in curs.execute(sql, (batchsize, )):
                cid, fullpath = row
                rv.append((cid, fullpath))
#        if cid is not None:
#            self.update_comic_image(cid, '', 0, 0)

        return rv

    def reset_unprocessed_thumbs(self):
        sql = '''UPDATE all_comics SET image=null WHERE image=''; '''
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            con.execute(sql)
            con.commit()

    def do_thumb_job(self):
        created = 0
        self._numrecs = self.get_all_comics_count()
        self._pending = self.get_unprocessed_comics_count()
        if self._numrecs == 0:
            self._pct = 0.0
        else:
            self._pct = ((self._numrecs - self._pending) / self._numrecs)
            
        if self._pending == 0:
            return True

        jobs_pending = 0

        pool = Pool(processes=4)

        while True:
            rv = self.get_thumb_to_process(20)
            self.last_thumb_time = time.time()
            params = []

            if rv is None or len(rv) == 0:
                log.debug("No additional thumbs to process...")
                break

            for cid, comicpath in rv:
                if cid is None:
                    break

                tl = []
                iproc = os.path.join(os.path.dirname(gazee.__file__), 'imgproc')
                iprocscr = os.path.join(iproc, "imageborder")
                thumbsize = (gazee.config.THUMB_MAXWIDTH,
                             gazee.config.THUMB_MAXHEIGHT)

                for res in [(0, 0), thumbsize]:
                    rx, ry = res
                    fprc = 2 if rx == 0 else 1
                    opath = self.get_cache_path(cid, rx, ry, fprc)
                    tl.append((rx, ry, opath))

                param = (comicpath, cid, tl, 1, iprocscr)
                params.append(param)

            jobs_pending = len(params)
            log.debug("There are %d jobs pending.", jobs_pending)
            results = pool.map(extract_thumb, params)
            self._pending -= jobs_pending
            jobs_pending = 0

            for edict in results:
                if edict is None:
                    log.error("Task returned error.");
                    continue

                cid = edict['cid']
                if 'error' in edict and edict['error']:
                    log.error("CID: %s returned the error: %s.", cid, edict['error'])
                    self.update_comic_image(cid, edict['error'], -1, -1)
                    continue

                num_pages = edict['num_pages']
                owidth = edict['owidth']
                oheight = edict['oheight']
                thumbpath = edict['tpath']
                comicpath = edict['path']

                self.update_comic_image(cid, thumbpath, owidth, oheight)
                log.debug("Created thumbnail: %s", thumbpath)
                created += 1

                log.debug("%d/%d: path: %s", created, self._numrecs, comicpath)

                ndict = self.fnp.parseFilename(comicpath)

                if ndict is None:
                    log.warn("Unable to parse filename: %s", comicpath)
                    series = None
                else:
                    series = ndict['series']
                    issue = ndict['issue']

                if series is None:
                    tser = os.path.basename(comicpath)
                    series = ''
                    for c in tser:
                        if c in ['(', '[']:
                            break
                        series = series + c

                    series = series.rstrip(' ')
                    issue = ''

                self.update_comic_meta(cid, num_pages, series, issue)
            if self._numrecs == 0:
                self._pct = 0.0
            else:
                self._pct = ((self._numrecs - self._pending) / self._numrecs)
        log.info("Created %d thumbnails...", created)
        self.last_thumb_time = None
        return True

    def do_extract_book(self, cid, username):
        ifiles = []
        if not isinstance(cid, int):
            cid = int(cid, 10)

        opath = "%s/Books/%s/%d" % (gazee.config.TEMP_DIR, username, cid)

        archname = self.get_comic_path(cid)

        if os.path.exists(opath):
            ifiles = [ os.path.join(opath, fn) for fn in sorted(os.listdir(opath)) ]
            log.debug("Images are: %s" % ifiles)

        if len(ifiles) == 0:
            if not os.path.exists(opath):
                os.makedirs(opath, 0o755)
            log.debug("Extracting archive: %s" % archname)
            pagepfx = '%d-' % cid
            ifiles = extract_archive(archname, opath, pagepfx)
            log.debug("extract_archive() returned: %s" % str(ifiles))

        return ifiles

    def get_nextprev_cids(self, cid, recentonly):
        if (recentonly):
            sql = '''SELECT max(comicid) FROM all_comics WHERE comicid < ?'''
            sql2 = '''SELECT min(comicid) FROM all_comics WHERE comicid > ?'''
        else:
            sql = '''SELECT ac.comicid FROM all_comics ac WHERE ac.filename = (select max(ac2.filename) FROM all_comics ac2 WHERE ac2.filename < (SELECT ac3.filename FROM all_comics ac3 WHERE ac3.comicid=?));'''
            sql2 = '''SELECT ac.comicid FROM all_comics ac WHERE ac.filename = (select min(ac2.filename) FROM all_comics ac2 WHERE ac2.filename > (SELECT ac3.filename FROM all_comics ac3 WHERE ac3.comicid=?));'''

        with sqlite3.connect(self.dbpath) as con:
            r = con.execute(sql, (cid, )).fetchone()
            r2 = con.execute(sql2, (cid, )).fetchone()
            r3 = con.execute('''SELECT s.name, c.issue, c.pages FROM all_comics c INNER JOIN comic_series s ON (c.seriesid=s.seriesid) WHERE comicid = ?''', (cid, )).fetchone()

            name, issue, pages = r3

            if isinstance(issue, int):
                titlestr = "%s #%d" % (name, issue)
            else:
                titlestr = "%s %s" % (name, issue)

            if r is None or r[0] is None:
                res1 = 0
            else:
                res1 = r[0]

            if r2 is None or r2[0] is None:
                res2 = 0
            else:
                res2 = r2[0]

            if (res1 != 0) or (res2 != 0):
                return (res1, res2, titlestr, pages)

        return (None, None, None, None)
    
    def get_comics_onepage(self, days, perpage, pagenum, series_id, recentonly=False):
        limit = perpage
        baseoff = ((pagenum - 1) * perpage)
        if baseoff < 0:
            skipquery = True
        else:
            skipquery = False
    
        retl = [ ]
        tnum = 10;
        
            
        if recentonly:
            if series_id > 0:
                sstr = " AND c.seriesid=%d" % series_id
            else:
                sstr = ""
            sql = '''SELECT c.comicid, s.name, c.image, c.issue, c.volume, c.summary, d.full_dir_path || '/' || c.filename as fullpath, c.adddate, c.filesize, c.pages, p.name FROM all_comics c INNER JOIN comic_series s ON (c.seriesid=s.seriesid) INNER JOIN all_Directories d ON (c.dirid=d.dirid) left JOIN publishers p ON (c.publisher=p.pubid) WHERE date('now', '-%d days') <= c.adddate%s ORDER BY adddate DESC LIMIT ? OFFSET ?''' % (days, sstr)
        else:
            if series_id > 0:
                sql = '''SELECT c.comicid, s.name, c.image, c.issue, c.volume, c.summary, d.full_dir_path || '/' || c.filename as fullpath, c.adddate, c.filesize, c.pages, p.name FROM all_comics c INNER JOIN comic_series s ON (c.seriesid=s.seriesid) INNER JOIN all_Directories d ON (c.dirid=d.dirid) left JOIN publishers p ON (c.publisher=p.pubid) WHERE c.seriesid=%d ORDER BY c.issue ASC, c.volume ASC LIMIT ? OFFSET ?''' % series_id
            else:
                sql = '''SELECT c.comicid, s.name, c.image, c.issue, c.volume, c.summary, d.full_dir_path || '/' || c.filename as fullpath, c.adddate, c.filesize, c.pages, p.name FROM all_comics c INNER JOIN comic_series s ON (c.seriesid=s.seriesid) INNER JOIN all_Directories d ON (c.dirid=d.dirid) left JOIN publishers p ON (c.publisher=p.pubid) ORDER BY c.filename ASC LIMIT ? OFFSET ?'''

        t = (limit, baseoff)
        cpath = gazee.config.COMIC_PATH

        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            if not skipquery:
                log.info("Executing SQL: %s  with t: %s", sql, str(t))
                rows = con.execute(sql, t).fetchall()
            else:
                rows = []
            nrows = len(rows)
            addrecs = limit - nrows
            for ti in range(addrecs):
                cid = "99999" + str(tnum)
                rv = (cid, "", "", "", "", "", "", "", "", "", "")
                rows.append(rv)
            for row in rows:
                cid, name, img, issue, vol, summary, fullpath, adddate, filesize, pages, pubname = row
                dstyle = "display: none;" if filesize == "" else ""
                relpath = os.path.relpath(fullpath, cpath) if fullpath != "" else ""
                if issue is not None and issue != '':
                    if isinstance(issue, int) or isinstance(issue, float) or issue[0].isdigit():
                        issue = '#%s' % issue
                else:
                    issue = ''
                
                tsize = sizestr(filesize, 2) if filesize != '' else ''

                if pubname is None:
                    pubname = "?"
                
                ComicTitle = name
                
                if vol is not None and vol != '':
                    ComicTitle = u'{0} v{1:02d}'.format(name, vol)
                    
                if issue is not None and issue != '':
                    if isinstance(issue, str):
                        log.info("Converting issue (%s) into an int.", issue)
                        if issue.isdigit():
                            issue = int(issue, 10)
                            isstr = '{0:03d}'.format(issue)
                        else:
                            issue = issue.strip('#')
                            isstr = '{0}'.format(issue)
                    
                    ComicTitle = u'{0} #{1}'.format(ComicTitle, isstr)

                retl.append({'Key': cid, 'ComicName': name,
                             'ComicTitle': ComicTitle,
                             'ComicImage': img,
                             'ComicIssue': issue,
                             'ComicVolume': vol,
                             'ComicSummary': summary,
                             'ComicPath': fullpath,
                             'RelPath': relpath,
                             'DateAdded': adddate,
                             'Size': tsize,
                             'Pages': pages,
                             'DispStyle': dstyle,
                             'PubName': pubname})
        return retl

    def get_series_onepage(self, perpage, pagenum):
        limit = perpage
        baseoff = ((pagenum - 1) * perpage)
        if baseoff < 0:
            skipquery = True
        else:
            skipquery = False
    
        retl = [ ]
        tnum = 10;
        
        sql = '''SELECT s.seriesid, s.name, c.comicid, count(c.comicid), sum(c.filesize) FROM comic_series s inner join all_comics c ON (s.seriesid = c.seriesid) WHERE (s.name <> '') GROUP BY s.seriesid ORDER BY s.name ASC LIMIT ? OFFSET ?;'''
        
        t = (limit, baseoff)
        cpath = gazee.config.COMIC_PATH

        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            if not skipquery:
                log.info("Executing SQL: %s  with t: %s", sql, str(t))
                rows = con.execute(sql, t).fetchall()
            else:
                rows = []
            nrows = len(rows)
            addrecs = limit - nrows
            for ti in range(addrecs):
                cid = "99999" + str(tnum)
                rv = (cid, "", "", "", 0)
                rows.append(rv)
            for row in rows:
                sid, name, cid, num_comics, total_size = row
                dispstyle = "display: none;" if name == '' else ""
                retl.append({'Key': sid, 
                             'SeriesName': name,
                             'ComicID': cid,
                             'NumComics': num_comics,
                             'TotalSize': sizestr(total_size),
                             'DispStyle': dispstyle})
        return retl
        
    def get_series(self, perpage, pagenum):
        startpage = 2
        endpage = 3
        comicsretl = [ [], [], [] ]
        tnum = 10;
        
        if (pagenum > 1):
            limit = (perpage * 3)
            baseoff = ((pagenum - 2) * perpage)
            if baseoff < 0:
                limit += baseoff
                baseoff = 0
            startpage = 1
        else:
            baseoff = 0
            limit = (perpage * 2)
        
#        baseoff = ((pagenum - 1) * perpage) - 1

        sql = '''SELECT s.seriesid, s.name, c.comicid, count(c.comicid), sum(c.filesize) FROM comic_series s inner join all_comics c ON (s.seriesid = c.seriesid) WHERE (s.name <> '') GROUP BY s.seriesid ORDER BY s.name ASC LIMIT ? OFFSET ?;'''

        t = (limit, baseoff)
        minpgadd = 0
        if (startpage > 1):
            minpgadd = 1
            for i in range(perpage):
                tnum += 1
                comicsretl[0].append({'Key': "99999" + str(tnum), 
                                           'SeriesName': "",
                                           'ComicID': "",
                                           'NumComics': "",
                                           'TotalSize': 0,
                                           'DispStyle': "display: none;"})
                
            
        
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            rnum = 0
            log.info("Executing SQL: %s  with t: %s", sql, str(t))
            rows = con.execute(sql, t).fetchall()
            nrows = len(rows)
            addrecs = limit - nrows
            for ti in range(addrecs):
                cid = "99999" + str(tnum)
                rv = (cid, "", "", "", 0)
                rows.append(rv)
            for row in rows:
                rnum += 1
                rowind = ((rnum - 1) // perpage)
                rowind += minpgadd;
                sid, name, cid, num_comics, total_size = row
                dispstyle = "display: none;" if name == "" else ""
                    
                comicsretl[rowind].append({'Key': sid, 
                                           'SeriesName': name,
                                           'ComicID': cid,
                                           'NumComics': num_comics,
                                           'TotalSize': sizestr(total_size),
                                           'DispStyle': dispstyle})
        log.debug(comicsretl)
        return comicsretl
        
    
    def get_comics(self, days, perpage, pagenum, series_id=-1, recentonly=False):
        startpage = 2
        endpage = 3
        comicsretl = [ [], [], [] ]
        tnum = 10;
        
        if (pagenum > 1):
            limit = (perpage * 3)
            baseoff = ((pagenum - 2) * perpage)
            if baseoff < 0:
                limit += baseoff
                baseoff = 0
            startpage = 1
        else:
            baseoff = 0
            limit = (perpage * 2)
        
#        baseoff = ((pagenum - 1) * perpage) - 1

        if recentonly:
            if series_id > 0:
                sstr = " AND c.seriesid=%d" % series_id
            else:
                sstr = ""
            sql = '''SELECT c.comicid, s.name, c.image, c.issue, c.volume, c.summary, d.full_dir_path || '/' || c.filename as fullpath, c.adddate, c.filesize, c.pages, p.name FROM all_comics c INNER JOIN comic_series s ON (c.seriesid=s.seriesid) INNER JOIN all_Directories d ON (c.dirid=d.dirid) left JOIN publishers p ON (c.publisher=p.pubid) WHERE date('now', '-%d days') <= c.adddate%s ORDER BY adddate DESC LIMIT ? OFFSET ?''' % (days, sstr)
        else:
            if series_id > 0:
                sql = '''SELECT c.comicid, s.name, c.image, c.issue, c.volume, c.summary, d.full_dir_path || '/' || c.filename as fullpath, c.adddate, c.filesize, c.pages, p.name FROM all_comics c INNER JOIN comic_series s ON (c.seriesid=s.seriesid) INNER JOIN all_Directories d ON (c.dirid=d.dirid) left JOIN publishers p ON (c.publisher=p.pubid) WHERE c.seriesid=%d ORDER BY c.issue ASC, c.volume ASC LIMIT ? OFFSET ?''' % series_id
            else:
                sql = '''SELECT c.comicid, s.name, c.image, c.issue, c.volume, c.summary, d.full_dir_path || '/' || c.filename as fullpath, c.adddate, c.filesize, c.pages, p.name FROM all_comics c INNER JOIN comic_series s ON (c.seriesid=s.seriesid) INNER JOIN all_Directories d ON (c.dirid=d.dirid) left JOIN publishers p ON (c.publisher=p.pubid) ORDER BY c.filename ASC LIMIT ? OFFSET ?'''

        t = (limit, baseoff)
        cpath = gazee.config.COMIC_PATH
        minpgadd = 0
        if (startpage > 1):
            minpgadd = 1
            for i in range(perpage):
                tnum += 1
                comicsretl[0].append({'Key': "99999" + str(tnum), 
                                           'ComicName': "",
                                           'ComicTitle': "",
                                           'ComicImage': "",
                                           'ComicIssue': "",
                                           'ComicVolume': "",
                                           'ComicSummary': "",
                                           'ComicPath': "",
                                           'RelPath': "",
                                           'DateAdded':"",
                                           'Size': "",
                                           'Pages': "",
                                           'PubName': "",
                                           'DispStyle': 'display: none;',
                                           'IndexPage': 0})
                
            
        
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            rnum = 0
            log.info("Executing SQL: %s  with t: %s", sql, str(t))
            rows = con.execute(sql, t).fetchall()
            nrows = len(rows)
            addrecs = limit - nrows
            for ti in range(addrecs):
                cid = "99999" + str(tnum)
                rv = (cid, "", "", "", "", "", "", "", "", "", "")
                rows.append(rv)
            for row in rows:
                rnum += 1
                rowind = ((rnum - 1) // perpage)
                rowind += minpgadd;
                cid, name, img, issue, vol, summary, fullpath, adddate, filesize, pages, pubname = row
                dstyle = "display: none;" if filesize == "" else ""
                relpath = os.path.relpath(fullpath, cpath) if fullpath != "" else ""
                if issue is not None and issue != '':
                    if isinstance(issue, int) or isinstance(issue, float) or issue[0].isdigit():
                        issue = '#%s' % issue
                else:
                    issue = ''

                tsize = sizestr(filesize, 2) if filesize != '' else ''

                if pubname is None:
                    pubname = "?"
                    
                ComicTitle = name
                
                if vol is not None and vol != '':
                    ComicTitle = u'{0} v{1:02d}'.format(name, vol)
                    
                if issue is not None and issue != '':
                    if isinstance(issue, str):
                        log.info("Converting issue (%s) into an int.", issue)
                        if issue.isdigit():
                            issue = int(issue, 10)
                            isstr = '{0:03d}'.format(issue)
                        else:
                            issue = issue.strip('#')
                            isstr = '{0}'.format(issue)
                    
                    ComicTitle = u'{0} #{1}'.format(ComicTitle, isstr)
                    
                comicsretl[rowind].append({'Key': cid, 
                                           'ComicName': name,
                                           'ComicTitle': ComicTitle,
                                           'ComicImage': img,
                                           'ComicIssue': issue,
                                           'ComicVolume': vol,
                                           'ComicSummary': summary,
                                           'ComicPath': fullpath,
                                           'RelPath': relpath,
                                           'DateAdded': adddate,
                                           'Size': tsize,
                                           'Pages': pages,
                                           'PubName': pubname,
                                           'DispStyle': dstyle,
                                           'IndexPage': rowind})
        log.debug(comicsretl)
        return comicsretl

    def get_series_count(self):
        sql = '''SELECT COUNT(DISTINCT s.seriesid) FROM comic_series s INNER JOIN all_comics c ON (s.seriesid=c.seriesid)'''
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            row = con.execute(sql).fetchone()
            return row[0]
            
        return None

    def get_recent_comics_count(self, days, series_id=-1):
        if not isinstance(series_id, int):
            series_id = int(series_id, 10)
        
        if series_id > 0:
            param = (series_id, )
            sql = '''SELECT COUNT(*) FROM all_comics WHERE seriesid=? AND adddate >= date('now', '-%d days')''' % days
        else:
            param = None
            sql = '''SELECT COUNT(*) FROM all_comics WHERE adddate >= date('now', '-%d days')''' % days
            
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            if param is None:
                row = con.execute(sql).fetchone()
            else:
                row = con.execute(sql, param).fetchone()
            return row[0]
        return None

    def get_all_comics_count(self, series_id=-1):
        if not isinstance(series_id, int):
            series_id = int(series_id, 10)
        
        if series_id > 0:
            sql = '''SELECT COUNT(*) FROM all_comics WHERE seriesid=?'''
            param = (series_id, )
        else:
            sql = '''SELECT COUNT(*) FROM all_comics;'''
            param = None
            
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            if param is None:
                row = con.execute(sql).fetchone()
            else:
                row = con.execute(sql, param).fetchone()
            return row[0]
        return None

    def get_unprocessed_comics_count(self):
        sql = '''SELECT COUNT(*) FROM all_comics WHERE image is null;'''

        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            row = con.execute(sql).fetchone()
        return row[0]

    def get_comics_stats(self, days=7):
        sql = '''SELECT COUNT(*), SUM(filesize) FROM all_comics'''
        
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            num_comics, sizeval = con.execute(sql).fetchone()
            if not isinstance(num_comics, int):
                num_comics = int(num_comics, 10)
            num_comics = '{:,d}'.format(num_comics)
            sql = '''SELECT COUNT(*), SUM(filesize) FROM all_comics WHERE image is null'''
            num_unprocessed, unprocsize = con.execute(sql).fetchone()
            if not isinstance(num_unprocessed, int):
                num_unprocessed = int(num_unprocessed, 10)
            num_unprocessed = '{:,d}'.format(num_unprocessed)
            sql = '''SELECT COUNT(*) FROM all_comics WHERE adddate >= date('now', '-%d days')''' % days
            row = con.execute(sql).fetchone()
            num_recent = row[0]
            
            if not isinstance(num_recent, int):
                num_recent = int(num_recent, 10)
            num_recent = '{:,d}'.format(num_recent)
            
            if unprocsize is None:
                unprocsize = 0
            total_size_str = sizestr(sizeval)
            total_unprocsize = sizestr(unprocsize)
        
        return num_comics, num_recent, total_size_str, num_unprocessed, total_unprocsize
        
    def reset_series(self):
        sql = '''UPDATE all_comics SET seriesid=1, issue=null, summary=null, publisher=null;'''
        with sqlite3.connect(self.dbpath, isolation_level='DEFERRED') as con:
            con.execute(sql)
            sql = '''DROP TABLE comic_series;
CREATE TABLE IF NOT EXISTS comic_series(seriesid INTEGER PRIMARY KEY AUTOINCREMENT, collname TEXT NOT NULL, name TEXT NOT NULL);
INSERT INTO comic_series(seriesid, collname, name) VALUES (1, "unknown", "Unknown");
CREATE INDEX IF NOT EXISTS seriesord on comic_series(name ASC);
CREATE INDEX IF NOT EXISTS seriescollord on comic_series(collname ASC);'''
            con.executescript(sql)
            con.commit()
        
        return


if __name__ == '__main__':
    db = comic_db()
    db.scan_directory_tree('/Volumes/6TB/Comics', 0)
    db.do_thumb_job()
