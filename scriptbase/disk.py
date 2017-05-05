# Copyright 2016-17 Steven Cooper
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

"""Disk-related utilities for Unix-like systems."""

import os
import re
from glob import glob

from . import command


RE_MOUNT = re.compile('^(/[a-z0-9_/]+) on (/[a-z0-9_/ ]+)( [(][^)]*[)])?', re.IGNORECASE)


def iter_mounted_volumes():
    """Iterate mounted volume paths."""
    with command.Command('mount') as cmd:
        for line in cmd:
            matched = RE_MOUNT.match(line)
            if matched:
                yield matched.group(2), matched.group(1)


def mounts_check(*mountpoints):
    """Return True if all passed mount points have mounted volumes."""
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
    """Convert path to versioned path by adding suffix and counter when necessary."""
    (base, ext) = os.path.splitext(path)
    re_strip_version = re.compile('(.*)-%s(-[0-9]*)?' % suffix)
    matched = re_strip_version.match(base)
    if matched:
        base = matched.group(1)
    path = '%s-%s%s' % (base, suffix, ext)
    if not os.path.exists(path):
        return path
    max_version = 1
    for chk in glob('%s-%s-[0-9]*%s' % (base, suffix, ext)):
        version = _get_version(chk)
        if version > max_version:
            max_version = version
    suffix2 = '%s-%d' % (suffix, max_version + 1)
    return '%s-%s%s' % (base, suffix2, ext)


def purge_versions(path, suffix, num_keep, reverse=False):
    """
    Purge file versions created by get_versioned_path.

    Purge specified quantity in normal or reverse sequence.
    """
    (base, ext) = os.path.splitext(path)
    re_strip_version = re.compile('(.*)-%s(-[0-9]*)?' % suffix)
    matched = re_strip_version.match(base)
    if matched:
        base = matched.group(1)
    versions = [version for version in glob('%s-%s*%s' % (base, suffix, ext))]
    versions.sort(key=_get_version, reverse=reverse)
    num_purge = len(versions) - num_keep
    if num_purge > len(versions):
        num_purge = 0
    if num_purge > 0:
        for version_path in versions[:num_purge]:
            os.remove(version_path)
    return num_purge
