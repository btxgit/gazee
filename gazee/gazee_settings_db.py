import sys
import os
import logging
import sqlite3

import getpass

from hashlib import sha256

from gazee.db import gazee_db
import gazee.config

def get_db_name():
    return 'gazee_settings.db'

def hash_pass(password):
    return sha256(bytes(password, encoding='utf-8')).hexdigest()

def get_password(username):
    dbpath = os.path.join(gazee.config.DATA_DIR, get_db_name())
    sql = '''SELECT pwhash FROM users WHERE username=?'''
    params = (username, )

    pw = None
    dbapth = os.path.join(gazee.config.DATA_DIR, "gazee_settings.db")

    with sqlite3.connect(dbpath) as conn:
        for row in conn.execute(sql, params):
            pw = row[0]

    return pw

def get_dbpath():
    return os.path.join(gazee.config.DATA_DIR, get_db_name())

class gazee_settings(gazee_db):
    SCHEMA_VERSION = 1

    def __init__(self):
        super(gazee_settings, self).__init__()
        if not self.have_admin_account():
            self.logger.error("got error back from have_admin_account()!")
        logging.basicConfig(level=logging.DEBUG, filename=os.path.join(gazee.config.DATA_DIR, 'gazee.log'))
        self.logger = logging.getLogger(__name__)

    def get_db_name(self):
        return 'gazee_settings.db'

    def create_db(self):
        sql = '''
            CREATE TABLE IF NOT EXISTS users(username TEXT NOT NULL, pwhash TEXT NOT NULL, account_type TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS unidx ON users (username COLLATE NOCASE);
        '''
        self.logger.debug("Executing creation of SQL database: %s with SQL: %s", self.dbpath, sql)
        conn = sqlite3.connect(self.dbpath)
        conn.executescript(sql)
        conn.commit()
        conn.close()

        self.set_schema_version(self.SCHEMA_VERSION)

    def check_migrate_db(self):
        curver = self.get_schema_version()
        conn = sqlite3.connect(self.dbpath)

        while curver < self.SCHEMA_VERSION:
            curver += 1
            if 1 == curver:
                q = ''''''
                conn.execute(q)
                conn.commit()

        conn.close()

        self.set_schema_version(self.SCHEMA_VERSION)

    def verify_account_type(self, account_type):
        return account_type.lower() in ['admin', 'user']

    def change_pass(self, username, password):
        pwhash = hash_pass(password)

        with sqlite3.connect(get_dbpath(), isolation_level='DEFERRED') as conn:
            sql = '''UPDATE users SET pwhash=? WHERE username=?'''
            param = (pwhash, username)

            conn.execute(sql, param)
            conn.commit()

    def get_password(self, username):
        sql = '''SELECT pwhash FROM users WHERE username=?'''
        params = (username, )
        pw = None

        with sqlite3.connect(get_dbpath(), isolation_level='DEFERRED') as conn:
            for row in conn.execute(sql, params):
                pw = row[0]

        return pw

    def get_user_level(self, username):
        sql = '''SELECT account_type FROM users WHERE username=?'''
        params = (username, )
        atype = None

        with sqlite3.connect(get_dbpath(), isolation_level='DEFERRED') as conn:
            for row in conn.execute(sql, params):
                atype = row[0]

        return atype

    def add_user(self, username, password, account_type):
        '''
        Accepts username, password, and the account_type - all strings.
        username must be unique, even when case is ignored
        password should be the password you want to enter, not the SHA256 hash
        account_type should be a valid account_type ... the only I know of is admin.

        Returns: a tuple (Success, Reason)
        Where Success is True for success else False, and Reason is "Success." on success, and a userful
        explanation for the failure.
        '''
        if not self.verify_account_type(account_type):
            return (False, 'An invalid account_type was specified.')

        pwhash = hash_pass(password)
        sql = '''INSERT INTO users VALUES(?, ?, ?);'''
        arg = (username, pwhash, account_type.lower())
        with sqlite3.connect(get_dbpath(), isolation_level='DEFERRED') as conn:
            try:
                conn.execute(sql, arg)
                conn.commit()
            except IntegrityError as ie:
                return (False, 'That user already exists in the database (maybe with a different case).')

        return (True, 'Success.')

    def del_user(self, username):
        sql = '''DELETE FROM users where username COLLATE NOCASE = ?'''
        with sqlite3.connect(get_dbpath(), isolation_level='DEFERRED') as conn:
            conn.execute(sql, (username, ))
            conn.commit()

    def validate_user(self, username, password):
        pwhash = hash_pass(password)
        sql = '''SELECT account_type FROM users WHERE username=? COLLATE NOCASE AND password=?;'''
        arg = (username, pwhash)
        account_type = None
        with sqlite3.connect(get_dbpath(), isolation_level='DEFERRED') as conn:
            for row in conn.execute(sql, arg):
                account_type = row[0]
        success = account_type is not None
        retstr = 'Invalid username and/or password' if not success else 'Success.'
        return (success, retstr)

    def get_userlist(self):
        sql = '''SELECT * FROM users'''
        users = []

        with sqlite3.connect(get_dbpath(), isolation_level='DEFERRED') as conn:
            for row in conn.execute(sql):
                un, pw, accttype = row
                users.append({'User': un, 'Type': accttype})

        return users

    def num_account_type(self, account_type='admin'):
        param = (account_type, )
        with sqlite3.connect(get_dbpath(), isolation_level='DEFERRED') as conn:
            for row in conn.execute('''SELECT COUNT(*) FROM users WHERE account_type=?''', param):
                return row[0]

    def prompt_account_details(self, account_type='admin'):
        while True:
            un = input("Enter the username for your default Gazee account: ")
            if un is None or un == '':
                continue
            break

        while True:
            pw = getpass.getpass(prompt='Enter your default Gazee account\'s password: ')
            if pw is None or pw == '':
                continue
            break

        rv = self.add_user(un, pw, account_type)
        if (not rv[0]):
            self.logger.error("Got error from add_user: %s", rv[1])
            return False

        return True

    def have_admin_account(self):
        if self.num_account_type(account_type='admin') > 0:
            return True

        self.logger.warn("Gazee has no admin account_type account created.  Going to try to create one.")

        if not os.isatty(sys.stdout.fileno()):
            self.logger.warn("Unable to ask for the admin user\'s account credentials because the script is being started in a term with notty.")
            return False

        if not self.prompt_account_details(account_type='admin'):
            self.logger.error("Failed to run prompt_account_details.")
            return False

if __name__ == '__main__':
    d = gazee_settings()
    print("Working on database: %s" % get_db_name())
