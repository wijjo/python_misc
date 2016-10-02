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

import os
import re
from glob import glob

from . import command
from . import console


RE_MOUNT = re.compile('^(/[a-z0-9_/]+) on (/[a-z0-9_/ ]+)( [(][^)]*[)])?', re.IGNORECASE)


def iter_mounted_volumes():
    """
    Iterate mounted volume paths.
    """
    with command.Command('mount') as cmd:
        for line in cmd:
            m = RE_MOUNT.match(line)
            if m:
                yield m.group(2), m.group(1)


def mounts_check(*mountpoints):
    """
    Return True if all passed mount points have mounted volumes.
    """
    mounted = dict(iter_mounted_volumes())
    for mountpoint in mountpoints:
        if mountpoint not in mounted:
            return False
    return True


def _get_version(path):
    try:
        return int(os.path.splitext(path)[0].split('-')[-1])
    except ValueError:
        return -1


def get_versioned_path(path, suffix):
    """
    Convert path to versioned path by adding suffix and counter when necessary.
    """
    (base, ext) = os.path.splitext(path)
    re_strip_version = re.compile('(.*)-%s(-[0-9]*)?' % suffix)
    m = re_strip_version.match(base)
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
    """
    Purge file versions created by get_versioned_path.  Purge specified
    quantity in normal or reverse sequence.
    """
    (base, ext) = os.path.splitext(path)
    re_strip_version = re.compile('(.*)-%s(-[0-9]*)?' % suffix)
    m = re_strip_version.match(base)
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
