#  .oooooooo  .oooo.     oooooooo  .ooooo.   .ooooo.
# 888' `88b  `P  )88b   d'""7d8P  d88' `88b d88' `88b
# 888   888   .oP"888     .d8P'   888ooo888 888ooo888
# `88bod8P'  d8(  888   .d8P'  .P 888    .o 888    .o
# `8oooooo.  `Y888""8o d8888888P  `Y8bod8P' `Y8bod8P'
# d"     YD
# "Y88888P'
#
# database base class - btx

import os
import logging
import sqlite3
import gazee.config

log = logging.getLogger(__name__)

class gazee_db(object):
    SCHEMA_VERSION = 1

    def __init__(self):
        pass
    
    def init_db(self):
        if os.path.exists(self.dbpath) and os.path.getsize(self.dbpath) < (4 * 1024):
            os.unlink(self.dbpath)

        if not os.path.exists(self.dbpath):
            log.info("Creating new database: %s", self.dbpath)
            self.create_db()

        self.check_migrate_db()

    def get_db_name(self):
        raise Exception('Called get_db_name() on the base class!')

    def get_dbpath(self):
        return os.path.join(gazee.config.DB_DIR, self.get_db_name())

    def create_db(self):
        log.error("Calling base gazee_db.get_db_name() method!")
        return

    def check_migrate_db(self):
        log.warn("Called check_migrate_db() on base method!")
        return

    def get_schema_version(self):
        conn = sqlite3.connect(self.dbpath)
        userver = None

        for row in conn.execute('PRAGMA user_version'):
            userver = row[0]
            break

        conn.close()

        if userver is None:
            raise Exception("Missing user_version in database")

        return userver

    def set_schema_version(self, version):
        '''
        Sets the user_version PRAGMA variable to the parameter <version>,
        which is assumed to be an Integer.an
        NOTE: yes, I am creating a SQL statement with string functions.  This
        is how it has to be done for pragma vars.
        '''

        if type(version) != int:
            raise Exception('Param version passed to set_schema_version was not an integer')

        conn = sqlite3.connect(self.dbpath)

        stmt = 'PRAGMA user_version = %d' % version

        conn.execute(stmt)
        conn.commit()
        conn.close()

        return


if __name__ == '__main__':
    db = gazee_db()
    print(db.get_db_name())
    res = db.get_dirid_by_path('/Volumes/6TB/Comics/Sep 9, 2009')
    print(res)
