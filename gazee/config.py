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

class gcfg(object):
    datapath = None
    cfgpath = None
    defaults = {'data_dir': 'data',
                'port': '4242',
                'comic_path': '',
                'temp_path': '',
                'comic_scan_interval': '60',
                'comics_per_page': '15',
                'thumb_maxwidth': '300',
                'thumb_maxheight': '400',
                'mylar_db': '',
                'ssl_key': '',
                'ssl_cert': '',
                'web_text_color': 'ffffff',
                'main_color': '757575',
                'accent_color': 'bdbdbd'}

    def __init__(self):
        self.cfg = configparser.ConfigParser()

        if not self.find_config():
            print("Failed to find_config()")
            sys.exit(1)

        self.configRead()
        print("Initialized configation... in %s" % __name__)

    def find_config(self):
        dirfound = None
        firstdir = None
        cfgfound = None
        dirs = ['data', '../data', '~/.gazee']
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
            print("Data directory not found!")
            return False

        dirfound = firstdir
        self.datapath = dirfound

        if cfgfound is not None:
            print('cfgfound=%s' % cfgfound)
            self.cfgpath = cfgfound
        else:
            cfile = os.path.join(self.datapath, 'app.ini')
            self.cfg['GLOBAL'] = {}
            self.cfg['DEFAULT'] = self.defaults
            self.cfg.set('default', 'data_dir', self.datapath)
            cfgfound = cfile
            self.cfgpath = cfgfound
            self.configWrite()

            self.cfg.set('GLOBAL', 'data_dir', self.datapath)
        return True

    def configWrite(self):
        with open(self.cfgpath, 'w') as configfile:
            self.cfg.write(configfile)
        return True

    def globalize(self):
        mod = sys.modules[__name__]

        for vn in self.cfg['GLOBAL']:
            vn = vn.upper()
            v = self.cfg.get('GLOBAL', vn)

            if vn in ['PORT', 'COMIC_SCAN_INTERVAL',
                      'COMICS_PER_PAGE', 'THUMB_MAXWIDTH', 'THUMB_MAXHEIGHT']:
                if v == '':
                    v = self.cfg.get('DEFAULT', vn)
                v = int(v, 10)

            setattr(mod, vn, v)

    def configRead(self):
        self.cfg.read(self.cfgpath)
        if 'GLOBAL' not in self.cfg:
            print("Resetting GLOBAL cfg...")
            self.cfg['GLOBAL'] = {}
        self.cfg.set('GLOBAL', 'data_dir', self.datapath)
        self.globalize()
        return True

    def updateCfg(self, newvals):
        print(newvals)
        for k in newvals['GLOBAL'].keys():
            if not isinstance(newvals['GLOBAL'][k], str):
                if newvals['GLOBAL'][k] is None:
                    newvals['GLOBAL'][k] = ''
                else:
                    print("newvals['GLOBAL'][%s] is type %s" % (k, str(type(newvals['GLOBAL'][k]))))
            self.cfg.set('GLOBAL', k, newvals['GLOBAL'][k])
        self.configWrite()
        self.globalize()
        return True
