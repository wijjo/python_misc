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
import shutil
import re
import inspect

from . import console
from . import command


class G:
    re_range = re.compile('\[([^\]-])-([^\]-])')
    re_mount = re.compile('^(/[a-z0-9_/]+) on (/[a-z0-9_/ ]+)( [(][^)]*[)])?', re.IGNORECASE)
    re_yes_no = re.compile('[yn]?', re.IGNORECASE)


# https://gist.github.com/techtonik/2151727/raw/4169b8cccbb0350b709e43d464031616e1b89252/caller_name.py
# Public Domain, i.e. feel free to copy/paste
# Considered a hack in Python 2
def caller_name(skip=2):
    """Get a name of a caller in the format module.class.method

       `skip` specifies how many levels of stack to skip while getting caller
       name. skip=1 means "who calls me", skip=2 "who calls my caller" etc.

       An empty string is returned if skipped levels exceed stack height
    """
    stack = inspect.stack()
    start = 0 + skip
    if len(stack) < start + 1:
      return ''
    parentframe = stack[start][0]

    name = []
    module = inspect.getmodule(parentframe)
    # `modname` can be None when frame is executed directly in console
    # TODO(techtonik): consider using __main__
    if module:
        name.append(module.__name__)
    # detect classname
    if 'self' in parentframe.f_locals:
        # I don't know any way to detect call from the object method
        # XXX: there seems to be no way to detect static method call - it will
        #      be just a function call
        name.append(parentframe.f_locals['self'].__class__.__name__)
    codename = parentframe.f_code.co_name
    if codename != '<module>':  # top level usually
        name.append( codename ) # function or a method
    del parentframe
    return ".".join(name)


def find_executable(*names):
    '''Return path to first name found in PATH.'''
    env_path = os.environ['PATH']
    for name in names:
        path = find_in_path(env_path, name, executable=True)
        if path:
            return path
    return None


def find_in_path(path, name, executable=False):
    '''Return path to name if found in path, or None if not found.  Require
    executable if executable is True.'''
    for dir in path.split(os.pathsep):
        chk_path = os.path.join(dir, name)
        if executable:
            if sys.platform in ('cygwin', 'windows'):
                for ext in ('', '.exe', '.bat', '.cmd', '.com'):
                    if os.path.exists(chk_path + ext):
                        return chk_path
            elif os.path.exists(chk_path) and (os.stat(chk_path)[0] & 0111) != 0:
                return chk_path
        elif os.path.exists(chk_path):
            return chk_path
    return None


class FileTool(object):

    def __init__(self, lstrip=False, rstrip=False, expandvars=False, dryrun=False):
        self.lstrip = lstrip
        self.rstrip = rstrip
        self.expandvars = expandvars
        self.dryrun = dryrun

    def readlines(self, path):
        try:
            f = open(path)
            try:
                try:
                    for line in f:
                        if self.lstrip:
                            line = line.lstrip()
                        if self.rstrip:
                            line = line.rstrip()
                        yield line
                except (IOError, OSError) as e:
                    console.abort('Unable to read from "%s".' % path, e)
            finally:
                f.close()
        except (IOError, OSError) as e:
            console.abort('Unable to open "%s".' % path, e)

    def save(self, path, *sources):
        """
        Save to file. "sources" can be scalars or iterables.
        """
        if not self.dryrun:
            try:
                try:
                    f = open(path, 'w')
                    self._write(f, sources)
                except (IOError, OSError) as e:
                    console.abort('Unable to write to "%s".' % path, e)
            finally:
                f.close()

    def newer(self, path1, path2):
        return os.stat(path1).st_mtime > os.stat(path2).st_mtime

    def copy(self, source, target, optional=False, update=False):
        if source and os.path.isfile(source):
            if update and os.path.isfile(target) and not self.newer(source, target):
                console.info('Skip copying older "%s" to "%s"...' % (source, target))
            else:
                console.info('Copying "%s" to "%s"...' % (source, target))
                if not self.dryrun:
                    shutil.copy(source, target)
        elif not optional:
            console.abort('Source file for copy "%s" does not exist.' % source)

    ### Private.

    def _write(self, f, source):
        if hasattr(source, '__iter__'):
            for item in source:
                self._write(f, item)
        else:
            if self.expandvars:
                f.write(os.path.expandvars(str(source)))
            else:
                f.write(str(source))
            f.write('\n')


def is_string(s):
    try:
        '' + s
        return True
    except TypeError:
        return False


def is_iterable(o):
    for i in o:
        return True
    return False


def is_non_string_sequence(o):
    return is_iterable(o) and not is_string(o)


def expand_ranges(*args):
    """
    Generate the cross-product of strings with embedded ranges written as [x-y].
    If y > x they are traversed in reverse order.
    """
    for a in args:
        m = G.re_range.search(a)
        if m:
            o1 = ord(m.group(1))
            o2 = ord(m.group(2))
            expanded = [''.join([a[:m.start(1)-1], chr(o), a[m.end(2)+1:]]) for o in range(o1, o2+1)]
            for s in expand_ranges(*expanded):
                yield s
        else:
            yield a


class DictObject(dict):
    def __getattr__(self, name):
        return self.get(name, None)
    def __setattr__(self, name, value):
        self[name] = value


def pluralize(word, quantity, suffix=None, replacement=None):
    if quantity == 1:
        return word
    if replacement:
        return replacement
    if suffix:
        return '%s%s' % (word, suffix)
    return '%ss' % word


def get_keywords(*names, **kwargs):
    d = DictObject()
    bad = []
    for keyword in kwargs:
        if keyword in names:
            d[keyword] = kwargs[keyword]
        else:
            bad.append(keyword)
    if bad:
        console.error('%s was called with %d bad keyword %s:'
                            % (caller_name(), len(bad), pluralize('argument', len(bad))),
                        ['Caller: %s' % caller_name(3)],
                        ['Bad %s: %s' % (pluralize('keyword', len(bad)), ' '.join(bad))])
    return d


def get_listener(port):
    with command.Command('lsof', '-i:%d' % port, '-sTCP:LISTEN', '-t') as cmd:
        for line in cmd:
            return int(line)


def iter_mounted_volumes():
    with command.Command('mount') as cmd:
        for line in cmd:
            m = G.re_mount.match(line)
            if m:
                yield m.group(2), m.group(1)


def mounts_check(*mountpoints):
    mounted = dict(iter_mounted_volumes())
    for mountpoint in mountpoints:
        if mountpoint not in mounted:
            return False
    return True


def ssh_tunnel_connect(remote_host, remote_port, local_port, ssh_port=22, dryrun=False):
    lpid = get_listener(local_port)
    if lpid is None:
        console.info('Connecting tunnel from %(remote_host)s:%(remote_port)d '
                     'to localhost:%(local_port)d...' % locals())
        autossh_cmd = ('autossh -M 0 -f -N -o '
                       '"ServerAliveInterval 60" -o "ServerAliveCountMax 3" '
                       '-p %(ssh_port)d '
                       '-L %(local_port)d:localhost:%(remote_port)d '
                       '%(remote_host)s' % locals())
        if dryrun:
            console.info(autossh_cmd)
        else:
            if os.system(autossh_cmd) == 0:
                console.info('Tunnel from %(remote_host)s:%(remote_port)d '
                             'to localhost:%(local_port)d is active.' % locals())
            else:
                console.abort('Failed to connect tunnel from %(remote_host)s:%(remote_port)d '
                              'to localhost:%(local_port)d.' % locals())
    else:
        console.info('Port %(local_port)d is already handled by process %(lpid)d.' % locals())


def ssh_tunnel_disconnect(local_port, dryrun=False):
    lpid = get_listener(local_port)
    if lpid:
        console.info('Killing port %(local_port)d listener process %(lpid)d...' % locals())
        kill_cmd = 'kill %(lpid)d' % locals()
        if dryrun:
            console.info(kill_cmd)
        else:
            if os.system(kill_cmd) == 0:
                console.info('Port listener process %(lpid)d was killed and '
                             'port %(local_port)d was disconnected.' % locals())
            else:
                console.abort('Failed to kill listener process %(lpid)d.' % locals())
    else:
        console.info('Port %(port)d does not hav an active listener.' % locals())


def sshfs_mount(mountpoint, remote_host, ssh_port=22, dryrun=False):
    if mounts_check(mountpoint):
        console.info('%(mountpoint)s was already mounted.')
    else:
        if not os.path.exists(mountpoint):
            if dryrun:
                console.info('mkdir %(mountpoint)s' % locals())
            else:
                os.mkdir(mountpoint)
        sshfs_cmd = ('sshfs -p %(ssh_port)d '
                     '-o idmap=user '
                     '-o defer_permissions '
                     '%(remote_host)s:/ %(mountpoint)s' % locals())
        if dryrun:
            console.info(sshfs_cmd)
        else:
            if os.system(sshfs_cmd) == 0:
                console.info('%(mountpoint)s is mounted.' % locals())
            else:
                console.abort('%(mountpoint)s failed to mount.' % locals())


def run_applescript(*lines):
    args = ['osascript']
    for line in lines:
        for subline in line.split('\n'):
            if subline.strip():
                args.extend(['-e', subline.strip()])
    with command.Command(*args) as cmd:
        cmd.run()
    return cmd.rc


def run_application_applescript(app, *lines):
    lines2 = ['tell application "%s"' % app] + list(lines) + ['end tell']
    return run_applescript(*lines2)


def choose(prompt, *choices):
    """
    Prompt the user for multiple choice input. Keep prompting until a valid
    choice is received. Choice shortcuts require unique first letters. The user
    can either respond with a single letter or an entire word.
    """
    letters = set()
    choice_list = []
    for choice in choices:
        if not choice:
            console.abort('Empty choice passed to choose().')
        if choice[0] in letters:
            console.abort('Non-unique choices %s passed to choose().' % str(choices))
        letters.add(choice[0])
        choice_list.append('[%s]%s' % (choice[0], choice[1:]))
    while True:
        sys.stdout.write('%s (%s) ' % (prompt, '/'.join(choice_list)))
        sys.stdout.flush()
        response = sys.stdin.readline().strip()
        if response in letters or response in choices:
            return response[0]


def prompt_re(msg, re, default):
    while True:
        sys.stdout.write('%s: ' % msg)
        try:
            s  = sys.stdin.readline().strip()
            if re.match(s):
                if not s:
                    return default
                return s
            console.error('bad input - try again')
        except KeyboardInterrupt:
            console.abort('', 'Keyboard interrupt')


def prompt_yes_no(msg, default=False):
    if default:
        yn = 'Y/n'
        sdef = 'y'
    else:
        yn = 'y/N'
        sdef = 'n'
    return (prompt_re('%s (%s)' % (msg, yn), G.re_yes_no, sdef).lower() == 'y')


class Properties(object):

    def __init__(self, dryrun=False, **kwargs):
        self._p = kwargs
        self._filetool = FileTool(lstrip=True, rstrip=True, expandvars=True, dryrun=dryrun)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError()
        return self._p.get(name, '')

    def __setattr__(self, name, value):
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            if value is None:
                if name in self._p:
                    del self._p[name]
            else:
                self._p[name] = value

    def __getitem__(self, name):
        return self._p.get(name, '')

    def __setitem__(self, name, value):
        self._p[name] = value

    def __iter__(self):
        for key in sorted(self._p.keys()):
            yield key

    def load(self, path, optional=False):
        """
        Load properties from a property file.
        """
        if os.path.isfile(path):
            console.info('Loading property file "%s"...' % path)
            for line in self._filetool.readlines(path):
                if not line.startswith('#'):
                    try:
                        name, value = line.split('=')
                        if (   (value.startswith('"') and value.endswith('"'))
                            or (value.startswith("'") and value.endswith("'"))):
                            value = value[1:-1]
                        self._p[name] = value
                    except ValueError:
                        console.warning('Ignoring bad line in "%s".' % path)
        elif not optional:
            console.abort('Missing property file "%s".' % path)

    def save(self, path):
        """
        Save properties in file.
        """
        lines = []
        console.info('Saving properties to file "%s"...' % path)
        for key in sorted(self._p.keys()):
            lines.append('%s="%s"' % (key, self._p[key]))
        self._filetool.save(path, *lines)

    def dump(self):
        """
        Dump properties to stdout.
        """
        for key in sorted(self._p.keys()):
            sys.stdout.write('%s=%s\n' % (key, self._p[key]))

    def has(self, *names):
        """
        Return True if all of the named properties are present.
        """
        for name in names:
            if not name in self._p:
                return False
        return True

    def clear(self, *names):
        """
        Delete properties.
        """
        for name in names:
            if name in self._p:
                del self._p[name]

def parse_version_string(version_string):
    return [int(s) for s in version_string.split(' ')[-1].split('.')]

def version_compare(version_string_1, version_string_2):
    """
    Compare two dot-separated version strings
    return 0 if version_string_1 = version_string_2
          -1 if version_string_1 < version_string_2
          +1 if version_string_1 > version_string_2
    """
    if version_string_1 is None:
        if version_string_2 is None:
            return 0
        return -1
    if version_string_2 is None:
        return 1
    version1 = parse_version_string(version_string_1)
    version2 = parse_version_string(version_string_2)
    for i in xrange(len(version2)):
        if len(version1) < i + 1 or version1[i] < version2[i]:
            return -1
        if version1[i] > version2[i]:
            return +1
    if len(version1) > len(version2):
        return +1
    return 0

def _get_version(path):
    try:
        return int(os.path.splitext(path)[0].split('-')[-1])
    except ValueError:
        return -1

def get_versioned_path(path, suffix):
    '''Convert path to versioned path by adding suffix and counter when
    necessary.'''
    (base, ext) = os.path.splitext(path)
    reStripVersion = re.compile('(.*)-%s(-[0-9]*)?' % suffix)
    m = reStripVersion.match(base)
    if m:
        base = m.group(1)
    path = '%s-%s%s' % (base, suffix, ext)
    if not os.path.exists(path):
        return path
    n = 1
    for chk in glob('%s-%s-[0-9]*%s' % (base, suffix, ext)):
        i = _get_version(chk)
        if i > n:
            n = i
    suffix2 = '%s-%d' % (suffix, n+1)
    return '%s-%s%s' % (base, suffix2, ext)

def purge_versions(path, suffix, nKeep, reverse = False):
    '''Purge file versions created by get_versioned_path.  Purge specified
    quantity in normal or reverse sequence.'''
    (base, ext) = os.path.splitext(path)
    reStripVersion = re.compile('(.*)-%s(-[0-9]*)?' % suffix)
    m = reStripVersion.match(base)
    if m:
        base = m.group(1)
    versions = [version for version in glob('%s-%s*%s' % (base, suffix, ext))]
    if reverse:
        versions.sort(cmp = lambda v1, v2: cmp(_get_version(v2), _get_version(v1)))
    else:
        versions.sort(cmp = lambda v1, v2: cmp(_get_version(v1), _get_version(v2)))
    nPurge = len(versions) - nKeep
    if nPurge > len(versions):
        nPurge = 0
    if nPurge > 0:
        for path in versions[:nPurge]:
            os.remove(path)
    return nPurge

