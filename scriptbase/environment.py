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

#===============================================================================
#===============================================================================
# environment
#
# environment variable utilities
#
# 12/16/10 - Steve Cooper - author
#===============================================================================
#===============================================================================

import sys, os, re
from . import logger

class Environment(object):
    @staticmethod
    def from_os_environ():
        return Environment(**dict(os.environ))
    @staticmethod
    def is_ignored(name):
        return not name or name == 'SHLVL' or not name[0].isalpha()
    @staticmethod
    def strip_path(name, path, *todel):
        todel = [t for t in todel if t is not None]
        if todel:
            logger.info('Stripping from path (%s):\n   %s' % (name, '\n   '.join(todel)))
        return ':'.join([dir for dir in path.split(':')
                            if not [item for item in todel if dir.startswith(item)]])
    @staticmethod
    def prepend_path(path, *toadd):
        old = path.split(':')
        new = [dir for dir in toadd if dir not in old]
        return ':'.join(new + old)
    @staticmethod
    def append_path(path, *toadd):
        old = path.split(':')
        new = [dir for dir in toadd if dir not in old]
        return ':'.join(old + new)
    def __init__(self, **kwargs):
        self.vars = {}
        for name in kwargs:
            if not Environment.is_ignored(name):
                self.vars[name] = kwargs[name]
    def __getitem__(self, name):
        return self.vars.get(name, None)
    def __setitem__(self, name, value):
        if not Environment.is_ignored(name):
            self.vars[name] = value
    def __getattr__(self, name):
        if name != 'vars':
            return self.vars.get(name, None)
    def __setattr__(self, name, value):
        if name == 'vars':
            object.__setattr__(self, name, value)
        elif not Environment.is_ignored(name):
            self.vars[name] = value
    def __iter__(self):
        names = self.vars.keys()
        names.sort()
        for name in names:
            yield (name, self.vars[name])
    def clone(self):
        return Environment(**self.vars)
    def to_os_environ(self, verbose = False):
        for name in self.vars:
            if name not in os.environ or self.vars[name] != os.environ[name]:
                if verbose:
                    logger.info('ENV: %s=%s' % (name, self.vars[name]))
                os.environ[name] = self.vars[name]
    def diff(self, other):
        tomod = []
        toadd = []
        todel = []
        names = self.vars.keys()
        names.sort()
        for name in names:
            if name not in other.vars:
                toadd.append((name, self.vars[name]))
            elif self.vars[name] != other.vars[name]:
                tomod.append((name, self.vars[name]))
        names = other.vars.keys()
        names.sort()
        for name in names:
            if name not in self.vars:
                todel.append(name)
        return (tomod, toadd, todel)
    def strip_path_var(self, name, *todel):
        if name in self.vars:
            self.vars[name] = Environment.strip_path(name, self.vars[name], *todel)
    def prepend_path_var(self, name, *toadd):
        if name in self.vars:
            self.vars[name] = Environment.prepend_path(self.vars[name], *toadd)
        else:
            self.vars[name] = ':'.join(toadd)
    def append_path_var(self, name, *toadd):
        if name in self.vars:
            self.vars[name] = Environment.append_path(self.vars[name], *toadd)
        else:
            self.vars[name] = ':'.join(toadd)
    def substitute_var(self, name, pattern, replacement, count = 0):
        if name in self.vars:
            self.vars[name] = re.sub(pattern, replacement, self.vars[name], count)

class EnvironmentDiffGenerator(object):
    def __init__(self, env1, env2, unset = False):
        self.env1  = env1
        self.env2  = env2
        self.unset = unset
    def __iter__(self):
        (tomod, toadd, todel) = self.env2.diff(self.env1)
        togen = tomod + toadd
        togen.sort()
        for (name, value) in togen:
            yield('export %s="%s"' % (name, value))
        if self.unset:
            for name in todel:
                yield('unset %s' % name)

def find_in_path(path, name, executable = False):
    '''Return path to name if found in path, or None if not found.  Require
    executable if executable is True.'''
    for dir in path.split(':'):
        chk_path = os.path.join(dir, name)
        if executable:
            if sys.platform in ('cygwin', 'windows'):
                for ext in ('', '.exe', '.bat', '.cmd', '.com'):
                    if os.path.exists(chk_path + ext):
                        return chk_path
            elif (os.stat(chk_path)[0] & 0111) != 0:
                return chk_path
        elif os.path.exists(chk_path):
            return chk_path
    return None
