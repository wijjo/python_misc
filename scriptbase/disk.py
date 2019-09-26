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

"""
Disk-related utilities for Unix-like systems.

Some functions deal with MacOS differences.

Some are only implemented for MacOS for now.
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
from . import utility


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


class DiskVolume(utility.DumpableObject):
    """Data for a disk volume."""

    unit_labels = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB']

    def __init__(
            self,
            volume_dev,
            disk_dev,
            raw_disk_dev,
            filesystem,
            size,
            name,
            uuid,
            mountpoint):
        self.volume_dev = volume_dev
        self.disk_dev = disk_dev
        self.raw_disk_dev = raw_disk_dev
        self.filesystem = filesystem
        self.size = int(size)
        self.name = name
        self.uuid = uuid
        self.mountpoint = mountpoint
        utility.DumpableObject.__init__(self)

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


FILESYSTEM_NAME_TRANSLATIONS_1 = {
    'Apple_APFS': 'APFS',
    'Apple_HFS': 'HFS',
    'EFI': 'EFI',
    'Windows_FAT_32': 'FAT32',
}

FILESYSTEM_NAME_TRANSLATIONS_2 = {
    'Windows_NTFS': 'NTFS',
    'UFSD_NTFS': 'NTFS',
    'Journaled HFS+': 'HFS+',
}


def volumes_list():
    """Provide data for currently visible volumes."""
    if sys.platform != 'darwin':
        console.abort('Currently, volumes_list() is only implemented for MacOS')
    import plistlib
    volumes = []
    proc = subprocess.run(['diskutil', 'list', '-plist', 'physical'],
                          capture_output=True, check=True)
    list_data = plistlib.loads(proc.stdout)
    for disk_or_partition in list_data['AllDisksAndPartitions']:
        for volume in disk_or_partition.get('Partitions', []):
            # Assume that "useful" user volumes have UUIDs.
            uuid = volume.get('VolumeUUID')
            if uuid:
                filesystem = FILESYSTEM_NAME_TRANSLATIONS_1.get(volume.get('Content'))
                if not filesystem:
                    proc2 = subprocess.run(['diskutil', 'info', '-plist', uuid],
                                           capture_output=True, check=True)
                    info_data = plistlib.loads(proc2.stdout)
                    filesystem = info_data['FilesystemName']
                    if filesystem in FILESYSTEM_NAME_TRANSLATIONS_2:
                        filesystem = FILESYSTEM_NAME_TRANSLATIONS_2[filesystem]
                volumes.append(DiskVolume(
                    '/dev/{}'.format(volume.get('DeviceIdentifier')),
                    '/dev/{}'.format(disk_or_partition['DeviceIdentifier']),
                    '/dev/r{}'.format(disk_or_partition['DeviceIdentifier']),
                    filesystem,
                    volume.get('Size'),
                    volume.get('VolumeName', '(unnamed)'),
                    uuid,
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
        console.abort('No volume "{}" was found.'.format(identifier))
    if len(volumes) != 1:
        console.abort('There are {} volumes for "{}".'.format(len(volumes), identifier))
    return volumes[0]


class Compressor:
    """Compressor data."""

    def __init__(self, name, uncompress_cmd, *compress_cmds):
        self.name = name
        self.uncompress_cmd = uncompress_cmd
        self.compress_cmds = compress_cmds

    def get_compress_command(self):
        """Check for and return compress command."""
        progs = []
        cmd = None
        for compress_cmd in self.compress_cmds:
            prog = compress_cmd.split()[0]
            if shell.find_executable(prog):
                cmd = compress_cmd
                break
            progs.append(prog)
        else:
            console.abort('Unable to find {} compression program: {}'
                          .format(self.name, ' '.join(progs)))
        return cmd

    def get_expand_command(self):
        """Check for and return expansion command."""
        prog = self.uncompress_cmd.split()[0]
        if not shell.find_executable(prog):
            console.abort('Unable to find {} expansion program: {}'.format(self.name, prog))
        return self.uncompress_cmd


class Compressors:
    """Access compression/expansion commands."""

    compressors = [
        Compressor('gzip', 'gzcat', 'pigz -c -f -', 'gzip -c -f -'),
        Compressor('xz', 'xzcat', 'xz -c -T0 -f -'),
    ]

    @classmethod
    def get_compressor(cls, name):
        """Return an appropriate compressor, if available."""
        compressor = None
        for check_compressor in cls.compressors:
            if check_compressor.name == name:
                compressor = check_compressor
                break
        else:
            console.abort('No {} compressor found.'.format(name))
        return compressor

    @classmethod
    def get_compress_command(cls, name):
        """Return compression command, if available."""
        compressor = cls.get_compressor(name)
        return compressor.get_compress_command()

    @classmethod
    def get_expand_command(cls, name):
        """Return expansion command, if available."""
        compressor = cls.get_compressor(name)
        return compressor.get_expand_command()


def backup_device(device_path, output_path, compression=None):  #pylint: disable=unused-argument
    """Copy input device to gzip-compressed output file."""
    ctx = utility.DictObject(**locals())
    if compression:
        ctx.compress_cmd = Compressors.get_compress_command(compression)
        ctx.compress_prog = ctx.compress_cmd.split()[0]
        cmd = 'sudo dd if={device_path} bs=1M | {compress_cmd} > "{output_path}"'
        msg = 'Reading device with dd and writing image with {compress_prog}.'
    else:
        cmd = 'sudo dd if={device_path} of="{output_path}" bs=1M'
        msg = 'Reading device and writing image with dd.'
    console.info([ctx.format(msg), 'Press CTRL-T for status.'])
    cmd = ctx.format(cmd)
    console.info(cmd)
    ctx.retcode = os.system(cmd)
    if ctx.retcode != 0:
        console.abort(ctx.format('Image restore command failed with return code {retcode}.'))


def restore_device(device_path, input_path, compression=None):  #pylint: disable=unused-argument
    """Uncompress input file and copy to output device."""
    ctx = utility.DictObject(**locals())
    if compression:
        ctx.expand_cmd = Compressors.get_expand_command(compression)
        msg = ('Uncompressing image file with {} and writing to device with dd.'
               .format(ctx.expand_cmd))
        cmd = ctx.format('{expand_cmd} "{input_path}" | sudo dd of={device_path} bs=64K')
    else:
        msg = 'Reading from image file and writing to device with dd.'
        cmd = ctx.format('sudo dd if="{input_path}" of={device_path} bs=1M')
    console.info([msg, 'Press CTRL-T for status.'])
    console.info(cmd)
    ctx.retcode = os.system(cmd)
    if ctx.retcode != 0:
        console.abort(ctx.format('Image restore command failed with return code {retcode}.'))
