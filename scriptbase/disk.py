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
from decimal import Decimal

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


class DiskVolume:
    """Data for a disk volume."""

    unit_labels = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB']

    def __init__(self, disk_dev, volume_dev, filesystem, size, name, uuid, mountpoint):
        self.disk_dev = disk_dev
        self.raw_disk_dev = '/dev/r{}'.format(self.disk_dev)
        self.volume_dev = volume_dev
        self.filesystem = filesystem
        self.size = int(size)
        self.name = name
        self.uuid = uuid
        self.mountpoint = mountpoint

    @classmethod
    def format_disk_size(cls, size, places=2):
        """Return adjusted size string with unit."""
        threshold = 1000 ** (len(cls.unit_labels) - 1)
        for i in range(len(cls.unit_labels) - 1, 0, -1):
            if size >= threshold:
                value_str = str(Decimal(size) / threshold)
                dec_pos = value_str.find('.')
                if dec_pos == -1:
                    return '{}.00 {}'.format(value_str, cls.unit_labels[i])
                value_places = len(value_str) - dec_pos - 1
                if value_places < places:
                    zeros = '0' * (places - value_places)
                    return '{}{} {}'.format(value_str, zeros, cls.unit_labels[i])
                if value_places > places:
                    return '{} {}'.format(value_str[:(places - value_places)], cls.unit_labels[i])
                return (value_str, cls.unit_labels[i])
            threshold //= 1000
        return '{} {}'.format(size, cls.unit_labels[0])

    def short_summary(self):
        """Short summary string to for user consumption."""
        return 'label: {label}, disk: {disk}, volume: {volume}, size: {size}'.format(
            label=self.name,
            disk=self.disk_dev,
            volume=self.volume_dev,
            size=self.format_disk_size(self.size),
        )


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
            volumes.append(DiskVolume(
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


def create_device_image(device_path, output_path, compression=None):
    """
    Copy input device to gzip-compressed output file.

    "compression" can only be "gzip" for now.
    """
    if compression:
        if compression != 'gzip':
            console.abort('Bad create_device_image() compression type: {}'.format(compression))
        for compressor in ['pigz', 'gzip']:
            if shell.find_executable(compressor):
                break
        else:
            console.abort('No gzip compressor program (pigz or gzip) was found.')
        cmd = 'sudo dd if={} bs=1M | {} -c -f - > "{}"'.format(
            device_path, compressor, output_path)
        info_text = 'Reading, compressing, and writing image with dd and {}.'.format(compressor)
    else:
        cmd = 'sudo dd if={} of="{}" bs=1M'.format(device_path, output_path)
        info_text = 'Reading device and writing image with dd.'
    console.info([info_text, 'Press CTRL-T for dd write status.'])
    console.info(cmd)
    retcode = os.system(cmd)
    if retcode != 0:
        console.abort('Device image creation command failed with return code {}.'.format(retcode))


def restore_device_image(device_path, input_path, compression=None):
    """
    Uncompress input file and copy to output device.

    "compression" can only be "gzip" for now.
    """
    if compression:
        if compression != 'gzip':
            console.abort('Bad create_device_image() compression type: {}'.format(compression))
        gzcat_cmd = shell.find_executable('gzcat')
        if not gzcat_cmd:
            console.abort('No gzcat command found.')
        info_text = 'Using gzcat to uncompress image file and dd to write to device.'
        # 64K buffer seemed to maximize throughput.
        cmd = '{} "{}" | sudo dd of={} bs=64K'.format(gzcat_cmd, input_path, device_path)
    else:
        info_text = 'Using gzcat to uncompress image file and dd to write to device.'
        # Need to test buffer size.
        cmd = 'sudo dd if="{}" of={} bs=1M'.format(input_path, device_path)
    console.info([info_text, 'Press CTRL-T for dd read status.'])
    console.info(cmd)
    retcode = os.system(cmd)
    if retcode != 0:
        console.abort('Image restore command failed with return code {}.'.format(retcode))
