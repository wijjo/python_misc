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

"""
Disk-related utilities for Unix-like systems.

Some functions deal with MacOS differences.
"""

import sys
import os
import re
import subprocess
from glob import glob

from . import command
from . import console
from . import shell


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


class Volume:
    """Data for a disk volume."""
    def __init__(self, disk_dev, volume_dev, filesystem, size, name, uuid, mountpoint):
        self.disk_dev = disk_dev
        self.raw_disk_dev = '/dev/r{}'.format(self.disk_dev)
        self.volume_dev = volume_dev
        self.filesystem = filesystem
        self.size = int(size)
        self.name = name
        self.uuid = uuid
        self.mountpoint = mountpoint


def volumes_list():
    """Provide data for currently visible volumes."""
    if sys.platform != 'darwin':
        console.abort('Currently, volumes_list() is only implemented for MacOS')
    import plistlib
    volumes = []
    proc = subprocess.run(['diskutil', 'list', '-plist'],
                          capture_output=True, check=True)
    for disk_or_partition in plistlib.loads(
            proc.stdout)['AllDisksAndPartitions']:
        for volume in disk_or_partition.get('Partitions', []):
            volumes.append(Volume(
                disk_or_partition['DeviceIdentifier'],
                volume.get('DeviceIdentifier'),
                volume.get('Content'),
                volume.get('Size'),
                volume.get('VolumeName'),
                volume.get('VolumeUUID'),
                volume.get('MountPoint'),
            ))
    return volumes


def volume_unmount(volume):
    """Unmount a volume based on a mountpoint."""
    if sys.platform != 'darwin':
        console.abort('Currently, volume_unmount() is only implemented for MacOS')
    subprocess.run(['diskutil', 'unmount', volume.mountpoint], check=True)


def volumes_for_identifier(identifier):
    """Find volume by volume name, mountpoint, UUID, or device name."""
    return [
        volume
        for volume in volumes_list()
        if identifier in [
            volume.name,
            volume.mountpoint,
            volume.uuid,
            volume.disk_dev,
        ]
    ]


def volume_for_identifier(identifier):
    """Find exactly one volume by identifier (see volumes_for_identifier())."""
    volumes = volumes_for_identifier(identifier)
    if not volumes:
        console.abort('No volume for "{}" was found.'.format(identifier))
    if len(volumes) != 1:
        console.abort('There are {} volumes for "{}".'.format(len(volumes), identifier))
    return volumes[0]


def gzip_device(device_path, output_path):
    """Write input stream to gzip'ed output file."""
    gzip_cmd = shell.find_executable('pigz') or shell.find_executable('gzip')
    if not gzip_cmd:
        console.abort('No gzip command found.')
    # Otherwise use pigz for faster multi-core compression.
    console.info('Compressing with "pigz". Use CTRL-T for status.')
    cmd = 'sudo dd if={input} bs=1M | {gzip} -c -f - > {output}'.format(
        input=device_path,
        gzip=gzip_cmd,
        output=output_path)
    console.info(cmd)
    retcode = os.system(cmd)
    if retcode != 0:
        console.abort('Output command failed with return code {}.'.format(retcode))
