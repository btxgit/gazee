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

__version__ = '0.1.6'

from gazee.config import gcfg
from gazee.gazee_settings_db import gazee_settings
from gazee.gazeemod import Gazeesrv
from gazee.archive import extract_archive, extract_thumb, extract_all_images
from gazee.versioning import current_version, latest_version
from gazee.uncomp import UncompressThread
from gazee.dbscan import ScanDirs

FULL_PATH = ""
DB_NAME = 'gazee.db'
DATA_DIR = 'data'
TEMP_DIR = 'tmp'
PIDFILE = '/var/run/gazee.pid'

PORT = 4242
COMIC_PATH = ''
COMIC_SCAN_INTERVAL = 60
COMICS_PER_PAGE = 15
MYLAR_DB = ''
SSL_KEY = ''
SSL_CERT = ''
WEB_TEXT_COLOR = 'FFFFFF'
ACCENT_COLOR = 'BDBDBD'
ARGS = []
THUMB_SIZE = 400, 300

# Declare DB variables, such as table names and field names
# This is mostly so the names are in a central area for later reference.

# Directories table, holds all actual directories full paths. We iterate
# over these in comicscan for their contents and add those to the below
# Directory Names table with the associated key.
ALL_DIRS = "all_directories"
FULL_DIR_PATH = "full_dir_path"
KEY = "key"

# Directory Names. This will hold the actual names of directories and their
# associated parent keys.
DIR_NAMES = "dir_names"
NICE_NAME = "nice_name"
DIR_IMAGE = "dir_image"
PARENT_KEY = "parent_key"

# Comics table and various attributes we associate with them.
ALL_COMICS = "all_comics"
COMIC_IMAGE = "image"
COMIC_NAME = "name"
COMIC_NUMBER = "issue"
COMIC_VOLUME = "volume"
COMIC_SUMMARY = "summary"
COMIC_FULL_PATH = "path"
INSERT_DATE = "date"

# Users Table and various attributes.
USERS = "USERS"
USERNAME = "username"
PASSWORD = "password"
TYPE = "type"
