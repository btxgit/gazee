#  This file is part of Gazee.
#
#  Gazee is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Gazee is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Gazee.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import threading
import argparse
import logging

import cherrypy
from cherrypy.process.plugins import Daemonizer, PIDFile

import gazee
#from gazee.config import gcfg
#from gazee.gazeemod import Gazeesrv

MAIN_COLOR=""


def daemonize():

    logging.basicConfig(level=logging.DEBUG, filename=os.path.join(DATA_DIR, 'gazee.log'))
    logger = logging.getLogger(__name__)

    if threading.activeCount() != 1:
        logger.warn('There are %r active threads. Daemonizing may cause \
                        strange behavior.' % threading.enumerate())

    sys.stdout.flush()
    sys.stderr.flush()

    # Do first fork
    try:
        pid = os.fork()
        if pid == 0:
            pass
        else:
            # Exit the parent process
            logger.debug('Forking once...')
            os._exit(0)
    except OSError as e:
        sys.exit("1st fork failed: %s [%d]" % (e.strerror, e.errno))

    os.setsid()

    # Make sure I can read my own files and shut out others
    prev = os.umask(0)  # @UndefinedVariable - only available in UNIX
    os.umask(prev and int('077', 8))

    # Do second fork
    try:
        pid = os.fork()
        if pid > 0:
            logger.debug('Forking twice...')
            os._exit(0)  # Exit second parent process
    except OSError as e:
        sys.exit("2nd fork failed: %s [%d]" % (e.strerror, e.errno))

    with open('/dev/null', 'r') as dev_null:
        os.dup2(dev_null.fileno(), sys.stdin.fileno())

    si = open('/dev/null', "r")
    so = open('/dev/null', "a+")
    se = open('/dev/null', "a+")

    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    pid = os.getpid()
    logger.info('Daemonized to PID: %s' % pid)
    logger.info("Writing PID %d to %s", pid, PIDFILE)
    with open(PIDFILE, 'w') as fp:
        fp.write("%s\n" % pid)


def main():

    parser = argparse.ArgumentParser(description='Gazee - Open Comic Book Reader')

    parser.add_argument('-d', '--daemon', action='store_true', help='Run as a daemon')
    parser.add_argument('-c', '--datadir', help='Set data directory')

    args = parser.parse_args()

    if args.datadir:
        DATA_DIR = args.datadir
        TEMP_DIR = os.path.join(DATA_DIR, 'tmp')

        if not os.path.exists(DATA_DIR):
            os.makedirs(os.path.abspath(DATA_DIR))

    else:
        DATA_DIR = os.path.realpath('./data')

    if os.path.exists(DATA_DIR):
        TEMP_DIR = os.path.join(DATA_DIR, "tmp")
        if not os.path.exists(os.path.join(DATA_DIR, 'sessions')):
            os.makedirs(os.path.abspath(os.path.join(DATA_DIR, 'sessions')))

        if not os.path.exists(TEMP_DIR):
            os.makedirs(os.path.abspath(TEMP_DIR))
    
    gazee.LOG_DIR=os.path.realpath(DATA_DIR)
    
    logging.basicConfig(level=logging.DEBUG, filename=os.path.join(gazee.LOG_DIR, 'gazee.log'))
    logger = logging.getLogger(__name__)

    if args.daemon:
        if sys.platform == 'win32':
            logger.info("Daemonize not supported under Windows, starting normally")
        else:
            # If the pidfile already exists, Gazee may still be running, so exit
            if os.path.exists(PIDFILE):
                sys.exit("PID file '" + PIDFILE + "' already exists. Exiting.")

            # The pidfile is only useful in daemon mode, make sure we can write the file properly
            try:
                PIDFile(cherrypy.engine, PIDFILE).subscribe()
            except IOError as e:
                raise SystemExit("Unable to write PID file: %s [%d]" % (e.strerror, e.errno))
            if DATA_DIR is not 'data':
                ARGS += ["-c", DATA_DIR]
            ARGS += ["-d"]
            Daemonizer(cherrypy.engine).subscribe()

    if os.path.exists('public/css/style.css'):
        with open('public/css/style.css') as f:
            style = f.read()

        with open('public/css/style.css', "w") as f:
            style = style.replace("757575", gazee.config.MAIN_COLOR)
            style = style.replace("BDBDBD", gazee.config.ACCENT_COLOR)
            style = style.replace("FFFFFF", gazee.config.WEB_TEXT_COLOR)
            f.write(style)

    if DATA_DIR is not 'data':
        conf = {
            '/': {
                'tools.gzip.on': True,
                'tools.gzip.mime_types': ['text/*', 'application/*', 'image/*'],
                'tools.staticdir.on': False,
                'tools.sessions.on': True,
                'tools.sessions.timeout': 1440,
                'tools.sessions.storage_class': cherrypy.lib.sessions.FileSession,
                'tools.sessions.storage_path': os.path.join(DATA_DIR, "sessions"),
                'tools.basic_auth.on': True,
                'tools.basic_auth.realm': 'Gazee',
                'tools.basic_auth.users': gazee.gazee_settings_db.get_password,
                'tools.basic_auth.encrypt': gazee.gazee_settings_db.hash_pass,
                'request.show_tracebacks': False
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.root': os.path.abspath(os.getcwd()),
                'tools.staticdir.dir': "public"
            },
            '/data': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': DATA_DIR
            },
            '/tmp': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': TEMP_DIR
            },
            '/favicon.ico': {
                'tools.staticfile.on': True,
                'tools.staticfile.filename': os.path.join(os.getcwd(), "public/images/favicon.ico")
            }
        }
    else:
        conf = {
            '/': {
                'tools.gzip.on': True,
                'tools.gzip.mime_types': ['text/*', 'application/*', 'image/*'],
                'tools.staticdir.on': False,
                'tools.sessions.on': True,
                'tools.sessions.timeout': 1440,
                'tools.sessions.storage_class': cherrypy.lib.sessions.FileSession,
                'tools.sessions.storage_path': os.path.join(DATA_DIR, "sessions"),
                'tools.basic_auth.on': True,
                'tools.basic_auth.realm': 'Gazee',
                'tools.basic_auth.users': gazee.gazee_settings_db.get_password,
                'tools.basic_auth.encrypt': gazee.gazee_settings_db.hash_pass,
                'request.show_tracebacks': False
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': "public"
            },
            '/data': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': DATA_DIR
            },
            '/tmp': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': TEMP_DIR
            },
            '/favicon.ico': {
                'tools.staticfile.on': True,
                'tools.staticfile.filename': os.path.join(os.getcwd(), "public/images/favicon.ico")
            }
        }

    if (gazee.config.SSL_KEY == '') and (gazee.config.SSL_CERT == ''):
        options_dict = {
            'server.socket_port': gazee.config.PORT,
            'server.socket_host': '0.0.0.0',
            'server.thread_pool': 30,
            'log.screen': False,
            'engine.autoreload.on': False,
        }
    else:
        options_dict = {
            'server.socket_port': gazee.config.PORT,
            'server.socket_host': '0.0.0.0',
            'server.thread_pool': 30,
            'server.ssl_module': 'builtin',
            'server.ssl_certificate': gazee.config.SSL_CERT,
            'server.ssl_private_key': gazee.config.SSL_KEY,
            'log.screen': False,
            'engine.autoreload.on': False,
        }

    cherrypy.config.update(options_dict)

    cherrypy.engine.timeout_monitor.on = False
    cherrypy.tree.mount(gazee.Gazeesrv(), '/', config=conf)

    logging.info("Gazee Started")

    cherrypy.engine.start()
    cherrypy.engine.block()

    if (os.path.exists(os.path.join(gazee.config.DATA_DIR, 'db.lock'))):
        os.remove(DATA_DIR, 'db.lock')
    return


if __name__ == '__main__':
    gcfg = gazee.gcfg()
    gcfg.configRead()
    gazee.config.FULL_PATH = os.path.dirname(os.path.realpath(__file__))
    os.chdir(gazee.config.FULL_PATH)
    gazee.config.DATA_DIR = os.path.join(gazee.config.FULL_PATH, "data")
    print("COMIC_PATH=%s" % gazee.config.COMIC_PATH)
    gazee.ScanDirs(cherrypy.engine, interval=300, comic_path=gazee.config.COMIC_PATH, temp_path=gazee.config.TEMP_PATH).subscribe()
    
    if (sys.platform == 'win32' and sys.executable.split('\\')[-1] == 'pythonw.exe'):
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")
    main()
