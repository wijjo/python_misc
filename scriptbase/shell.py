# Copyright 2016 Steven Cooper
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import os

from .utility import shlex_quote


def quote_arguments(*args):
    """
    Quote arguments as needed for proper shell parsing.
    Return quoted and joined string.
    """
    return (' '.join([shlex_quote(str(arg)) for arg in args]))


def run(cmd, *args):
    """
    Quote arguments as needed and run command using os.system().
    Return the received return code.
    """
    cmd_args = [cmd] + list(args)
    return os.system(quote_arguments(*cmd_args))


def find_executable(*names):
    """
    Return path to first name found in PATH.
    """
    env_path = os.environ['PATH']
    for name in names:
        path = find_in_path(env_path, name, executable=True)
        if path:
            return os.path.realpath(path)
    return None


def find_in_path(path, name, executable=False):
    """
    Return path to name if found in path, or None if not found.  Require
    executable if executable is True.
    """
    for dir in path.split(os.pathsep):
        chk_path = os.path.join(dir, name)
        if executable:
            if sys.platform in ('cygwin', 'windows'):
                for ext in ('', '.exe', '.bat', '.cmd', '.com'):
                    if os.path.exists(chk_path + ext):
                        return chk_path
            elif os.path.exists(chk_path) and (os.stat(chk_path)[0] & 0o111) != 0:
                return chk_path
        elif os.path.exists(chk_path):
            return chk_path
    return None
