#  .oooooooo  .oooo.     oooooooo  .ooooo.   .ooooo.
# 888' `88b  `P  )88b   d'""7d8P  d88' `88b d88' `88b
# 888   888   .oP"888     .d8P'   888ooo888 888ooo888
# `88bod8P'  d8(  888   .d8P'  .P 888    .o 888    .o
# `8oooooo.  `Y888""8o d8888888P  `Y8bod8P' `Y8bod8P'
# d"     YD
# "Y88888P'
#
# config class - btx
#

import sys
import os
import configparser
import logging

log = logging.getLogger(__name__)


class gcfg(object):
    datapath = None
    cfgpath = None
    defaults = {'bind_address': '127.0.0.1',
                'port': '4242',
                'data_dir': '~/.gazee',
                'temp_dir': '',
                'comic_path': '',
                'comic_scan_interval': '60',
                'comics_per_page': '15',
                'thumb_maxwidth': '300',
                'thumb_maxheight': '400',
                'image_script': '0',
                'mylar_db': '',
                'ssl_key': '',
                'ssl_cert': '',
                'web_text_color': 'ffffff',
                'main_color': '757575',
                'accent_color': 'bdbdbd'}

    def __init__(self, data_override=None):
        self.cfg = configparser.ConfigParser()
        self.datapath = data_override
        self.logpath = None
        self.dbpath = None
        self.sessionspath = None
        print("Created a new gcfg...") 
        
        if self.datapath is not None:
            self.datapath = os.path.realpath(os.path.expanduser(self.datapath))
        if self.datapath is None and data_override is not None:
            log.error("Somehow the datapath is now None.")
        self.configRead()
        log.debug("Initialized configation... in %s", __name__)

    def create_init_dirs(self,  data_dir):
        ''' Sets up the data_dir plus the two paths that aren't
        configurable, and are relative to the data_dir - the
        log_dir and db_dir
        '''
        
        if self.datapath is not None and data_dir is None:
            log.error("data_dir is None while datapath is not.")
            
        self.datapath = data_dir
        self.logpath = os.path.join(self.datapath, "logs")
        self.dbpath = os.path.join(self.datapath, "db")
        self.sessionspath = os.path.join(self.datapath, "sessions")

        if not os.path.exists(self.logpath):
            os.makedirs(self.logpath, 0o700)

        if not os.path.exists(self.dbpath):
            os.makedirs(self.dbpath, 0o700)

        if not os.path.exists(self.sessionspath):
            os.makedirs(self.sessionspath, 0o700)

    def find_config(self):
        ''' Looks for where the data dir is located.
        Once it finds the dir, it calls create_
        '''
        dirfound = None
        firstdir = None
        cfgfound = None
        
#        print("Looking for config in find_config() - datapath: %s" % (self.datapath))
        
        if self.datapath is not None:
            if not os.path.exists(self.datapath):
                msg = 'Path %s does not exist.\n\nDo you wish to create it? [y/n]: ' % self.datapath
                if self.get_yn(msg):
                    try:
                        os.makedirs(self.datapath)
                    except PermissionError:
                        print("You don't have the permissions to create that path.\nExiting.")
                        sys.exit(1)
                else:
                    print("Exiting.")
                    sys.exit(1)
            firstdir = dirfound = self.datapath

            cfile = os.path.join(dirfound, "app.ini")
            if os.path.exists(cfile):
                cfgfound = cfile
            else:
                cfgfound = None
        else:
            dirs = ['data', '~/.gazee', '../data']
            for d in dirs:
                ddir = os.path.realpath(os.path.expanduser(d))
                cfile = os.path.join(ddir, "app.ini")

                if os.path.exists(ddir) and os.path.isdir(ddir):
                    if firstdir is None:
                        firstdir = ddir

                    dirfound = ddir
                    if os.path.exists(cfile):
                        cfgfound = cfile
                        break

        if dirfound is None:
            log.error("Data directory not found!")
            return False

        dirfound = firstdir
        self.datapath = dirfound
        self.create_init_dirs(dirfound)

        if cfgfound is not None:
            log.debug('cfgfound=%s', cfgfound)
            self.cfgpath = cfgfound
        else:
            cfile = os.path.join(self.datapath, 'app.ini')
            self.cfg['GLOBAL'] = {}
            self.cfg['DEFAULT'] = self.defaults
            self.cfg.set('DEFAULT', 'data_dir', self.datapath)
            self.cfg.set('DEFAULT', 'image_script', self.defaults['image_script'])

            cfgfound = cfile
            self.cfgpath = cfgfound
            self.configWrite()
            self.cfg.set('GLOBAL', 'data_dir', self.datapath)
            self.cfg.set('GLOBAL', 'log_dir', self.logpath)
            self.cfg.set('GLOBAL', 'db_dir', self.dbpath)
            self.cfg.set('GLOBAL', 'sessions_dir', self.sessionspath)
        return True

    def configWrite(self):
        ''' Write self.cfg to disk
        '''
        with open(self.cfgpath, 'w') as configfile:
            self.cfg.write(configfile)
        return True

    def globalize(self):
        ''' Place the cfg variables into the self.config
        scope
        '''
        mod = sys.modules[__name__]
        for vn in self.cfg['GLOBAL']:
            vn = vn.upper()
            v = self.cfg.get('GLOBAL', vn)

            if vn in ['PORT', 'COMIC_SCAN_INTERVAL', 'IMAGE_SCRIPT',
                      'COMICS_PER_PAGE', 'THUMB_MAXWIDTH', 'THUMB_MAXHEIGHT']:
                if v == '':
                    v = self.cfg.get('DEFAULT', vn)
                v = int(v, 10)

            setattr(mod, vn, v)
    def get_yn(self, msg):
        while True:
            v = input(msg)
            if v.lower() in ['y', 'n']:
                break

            print("\nInvalid response.  Enter 'y' or 'n'.")

        return v.lower() == 'y'

    def get_path(self, name):
        p = None
        while True:
            prompt = 'Please enter %s: ' % name
            p = input(prompt)

            if not os.path.exists(p):
                msg = 'Path %s does not exist.\n\nDo you wish to create it? [y/n]: ' % p
                if self.get_yn(msg):
                    try:
                        os.makedirs(p)
                    except PermissionError:
                        print("You don't have the permissions to create that path.\n")
                        continue
                else:
                    print("Not creating directory: %s" % p)
                    continue
            break
        return p

    def configRead(self):
        ''' Read the app.ini config file.
        '''
        
        print("configRead() being called...")
        dp = self.find_config()

        if dp is None or self.datapath is None:
            log.error("Failed to find_config()")
            sys.exit(1)

        self.cfgpath = os.path.join(self.datapath, 'app.ini')
        self.cfg.read(self.cfgpath)
        
        for k in self.defaults.keys():
            if k not in self.cfg['DEFAULT']:
                v = self.defaults[k]
                log.info("Setting default[%s] = %s", k, v)
                self.cfg['DEFAULT'][k] = v
        
        if 'GLOBAL' not in self.cfg:
            log.info("Resetting GLOBAL cfg...")
            self.cfg['GLOBAL'] = {}

        self.cfg.set('GLOBAL', 'data_dir', self.datapath)

        if 'comic_path' not in self.cfg['GLOBAL'] or self.cfg.get('GLOBAL', 'comic_path') in [None, '']:
            cpath = self.get_path("your comic share's path")
            if cpath is not None:
                self.cfg.set('GLOBAL', 'comic_path', cpath)

        if 'temp_dir' not in self.cfg['GLOBAL'] or self.cfg.get('GLOBAL', 'temp_dir') in [None, '']:
            tdir = self.get_path('a directory for temporary (large) file storage')
            if tdir is not None:
                self.cfg.set('GLOBAL', 'temp_dir', tdir)

        self.configWrite()
        
        self.cfg.set('GLOBAL', 'log_dir', self.logpath)
        self.cfg.set('GLOBAL', 'db_dir', self.dbpath)
        self.cfg.set('GLOBAL', 'sessions_dir', self.sessionspath)
        self.globalize()
        
        return True

    def updateCfg(self, newvals):
        ''' Update the self.cfg with newvals, which should be
        a dict in the form {'GLOBAL': {'varname': 'varval'}}
        '''

        log.debug(newvals)
        for k in newvals['GLOBAL'].keys():
            if not isinstance(newvals['GLOBAL'][k], str):
                if newvals['GLOBAL'][k] is None:
                    newvals['GLOBAL'][k] = ''
                else:
                    log.debug("newvals['GLOBAL'][%s] is type %s",
                              k, str(type(newvals['GLOBAL'][k])))

            self.cfg.set('GLOBAL', k, newvals['GLOBAL'][k])
        self.configWrite()
        self.globalize()
        return True
