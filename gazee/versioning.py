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
import logging
import git

import gazee

logging = logging.getLogger(__name__)


def current_version():
    repo = git.Repo(os.path.dirname(gazee.FULL_PATH))
    local_commit = repo.commit()
    return local_commit.hexsha


def latest_version():
    repo = git.Repo(os.path.dirname(gazee.FULL_PATH))
    remote = repo.remotes.origin
    info = remote.fetch()[0]
    remote_commit = info.commit
    return remote_commit.hexsha
