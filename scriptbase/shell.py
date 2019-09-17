# Copyright 2016-19 Steven Cooper
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

"""Shell-related utilities."""

import sys
import os

from .utility import shlex_quote, is_string


def quote_argument(arg):
    """Quote argument or convert to string as needed for shell command compatibility."""
    return shlex_quote(arg) if is_string(arg) else str(arg)


def quote_argument_sequence(arg_seq):
    """Shell-quote an input sequence."""
    return (quote_argument(str(arg)) for arg in arg_seq)


def quote_arguments(*args):
    """
    Quote arguments as needed for proper shell parsing.

    Return quoted and joined string.
    """
    return ' '.join(quote_argument_sequence(args))


def run(cmd, *args):
    """
    Quote arguments as needed and run command using os.system().

    Return the received return code.
    """
    cmd_args = [cmd] + list(args)
    return os.system(quote_arguments(*cmd_args))


def find_executable(*names):
    """
    Find an executable program in the shell PATH.

    If multiple names are specified return the first one found in the path.

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
    Find a file in a shell-compatible path string.

    Return path to name if found in path, or None if not found.  Require
    executable if executable is True.
    """
    for directory in path.split(os.pathsep):
        chk_path = os.path.join(directory, name)
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


def relative_path(from_path, to_path):
    """
    Build a relative path between two input paths.

    If possible, it builds a path between from_path to to_path without
    consulting the physical filesystem.

    It returns to_path unchanged if the paths are not in the same hierarchy.
    """
    if from_path and to_path and from_path != to_path:
        if to_path.startswith(''.join([from_path, os.path.sep])):
            return to_path[len(from_path) + 1:]
        if from_path.startswith(''.join([to_path, os.path.sep])):
            return os.path.sep.join(('..',) * (from_path[len(to_path):].count(os.path.sep)))
    return to_path
