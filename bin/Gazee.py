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
import threading
import argparse
import logging
import logging.handlers
import cherrypy
from cherrypy.process.plugins import Daemonizer, PIDFile

import gazee


MAIN_COLOR = ""
ARGS=[]
gcfg = gazee.gcfg()


def init_root_logger(log_path):
#    logging.basicConfig(format='[%(asctime)s][%(name)s:%(levelname)s] %(message)s',
#                        datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
    elog = logging.getLogger()

    if not os.path.exists(log_path):
        fd = open(log_path, "w")
        fd.close()

    handler = logging.handlers.RotatingFileHandler(filename=log_path,
                                                   maxBytes=(1024 * 1024),
                                                   backupCount=5)

    formatter = logging.Formatter('[%(asctime)s][%(name)s:%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    elog.addHandler(handler)
    elog.setLevel(logging.WARN)
    log = logging.getLogger(__name__)
    return log


log_path = os.path.join(gazee.config.LOG_DIR, "gazee.log")
log = init_root_logger(log_path)

def daemonize():
    if threading.activeCount() != 1:
        log.warn('There are %r active threads. Daemonizing may cause \
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
            log.debug('Forking once...')
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
            log.debug('Forking twice...')
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
    log.info('Daemonized to PID: %s' % pid)
    log.info("Writing PID %d to %s", pid, PIDFile)
    with open(PIDFile, 'w') as fp:
        fp.write("%s\n" % pid)


def main():
    parser = argparse.ArgumentParser(description='Gazee - Open Comic Book Reader')

    parser.add_argument('-d', '--daemon', action='store_true', help='Run as a daemon')
    parser.add_argument('-c', '--datadir', help='Set data directory')
    parser.add_argument('-v', dest="verbosity", action="count", default=0, help="Every time this flag appears on the cmdline, the verbosity increases.")
    parser.add_argument('--pidfile', type=str, default="/var/run/gazee.pid", help="Specify the PID file to use when daemonizing")
    
    args = parser.parse_args()
    
    if (args.verbosity == 1):
        log.setLevel(logging.INFO)
    elif (args.verbosity > 1):
        log.setLevel(logging.DEBUG)
        
    if args.daemon:
        if sys.platform == 'win32':
            log.info("Daemonize not supported under Windows.")
        else:
            # If the pidfile already exists, Gazee may still
            # be running, so exit
            if os.path.exists(args.pidfile):
                log.error("PIDFile: %s already exists.  Exiting.", args.pidfile)
                sys.exit(1)
            else:
                cherrypy.config.update({'log.screen': False})
                Daemonizer(cherrypy.engine).subscribe()
            PIDFile(cherrypy.engine, args.pidfile).subscribe()

            # The pidfile is only useful in daemon mode, make sure we can write the file properly
            try:
                PIDFile(cherrypy.engine, PIDFile).subscribe()
            except IOError as e:
                raise SystemExit("Unable to write PID file: %s [%d]" % (e.strerror, e.errno))
            
            ARGS=sys.argv
            if gazee.config.DATA_DIR is not 'data':
                ARGS += ["-c", gazee.config.DATA_DIR]
            ARGS += ["-d"]
            Daemonizer(cherrypy.engine).subscribe()
    
    pubdir = os.path.realpath(gazee.__file__ + "/../public")

    if gazee.config.DATA_DIR is not 'data':
        conf = {
            '/': {
                'tools.gzip.on': True,
                'tools.gzip.mime_types': ['text/*', 'application/*', 'image/*'],
                'tools.staticdir.on': False,
                'tools.sessions.on': True,
                'tools.sessions.timeout': 1440,
                'tools.sessions.storage_class': cherrypy.lib.sessions.FileSession,
                'tools.sessions.storage_path': gazee.config.SESSIONS_DIR,
                'tools.basic_auth.on': True,
                'tools.basic_auth.realm': 'Gazee',
                'tools.basic_auth.users': gazee.gazee_settings_db.get_password,
                'tools.basic_auth.encrypt': gazee.gazee_settings_db.hash_pass,
                'request.show_tracebacks': False
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.root': os.path.abspath(os.getcwd()),
                'tools.staticdir.dir': pubdir
            },
            '/favicon.ico': {
                'tools.staticfile.on': True,
                'tools.staticfile.filename': os.path.join(pubdir, "images/favicon.ico")
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
                'tools.sessions.storage_path': gazee.config.SESSIONS_DIR,
                'tools.basic_auth.on': True,
                'tools.basic_auth.realm': 'Gazee',
                'tools.basic_auth.users': gazee.gazee_settings_db.get_password,
                'tools.basic_auth.encrypt': gazee.gazee_settings_db.hash_pass,
                'request.show_tracebacks': False
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': pubdir
            },
            '/favicon.ico': {
                'tools.staticfile.on': True,
                'tools.staticfile.filename': os.path.join(pubdir, "images/favicon.ico")
            }
        }

    if (gazee.config.SSL_KEY == '') and (gazee.config.SSL_CERT == ''):
        options_dict = {
            'server.socket_port': gazee.config.PORT,
            'server.socket_host': gazee.config.BIND_ADDRESS,
            'server.thread_pool': 30,
            'log.screen': False,
            'engine.autoreload.on': False,
        }
    else:
        options_dict = {
            'server.socket_port': gazee.config.PORT,
            'server.socket_host': gazee.config.BIND_ADDRESS,
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

    log.info("Gazee Started")

    cherrypy.engine.start()
    cherrypy.engine.block()

    if (os.path.exists(os.path.join(gazee.config.DATA_DIR, 'db.lock'))):
        os.remove(gazee.config.DATA_DIR, 'db.lock')
    return


if __name__ == '__main__':
    gazee.config.FULL_PATH = os.path.dirname(os.path.realpath(__file__))
    os.chdir(gazee.config.FULL_PATH)
    gazee.config.DATA_DIR = os.path.join(gazee.config.FULL_PATH, "data")
    gazee.ScanDirs(cherrypy.engine, interval=300, comic_path=gazee.config.COMIC_PATH, temp_path=gazee.config.TEMP_DIR).subscribe()

    if (sys.platform == 'win32' and
            sys.executable.split('\\')[-1] == 'pythonw.exe'):
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")
    main()
