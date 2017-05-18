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

"""Mac diskutil API."""

import sys
import os
import time
try:
    from StringIO import StringIO   #pylint: disable=unused-import
except ImportError:
    from io import StringIO

from .. import command
from .. import console


class DUCommand(command.Command):
    """Diskutil Command object for regular commands."""

    def __init__(self, verb, *args):
        """Constructor takes verb + arguments and prepends ['diskutil']."""
        command.Command.__init__(self, 'diskutil', verb, *args)


class DUCoreStorageCommand(DUCommand):
    """Diskutil Command object for corestorage commands."""

    def __init__(self, verb, *args):
        """Constructor takes verb + arguments and prepends ['diskutil', 'coreStorage']."""
        DUCommand.__init__(self, 'coreStorage', verb, *args)


class DUVolumeManager(object):
    """High level API for managing CoreStorage volumes."""

    def __init__(self, password_provider=None, dry_run=False):
        """
        Constructor accepts an optional password generation function.

        The generation function is called as needed to unlock volume sets.
        """
        self.password_provider = password_provider
        self.dry_run = dry_run

    def get_complete_volume_set(self):
        """Get the complete set of available volumes."""
        with DUCoreStorageCommand('list', '-plist') as cmd:
            pass
        plist = read_property_list(*cmd.output_lines)
        volumes = []
        lvm_groups = plist['CoreStorageLogicalVolumeGroups']
        for lvm_group in lvm_groups:
            log_volume_families = lvm_group['CoreStorageLogicalVolumeFamilies']
            for log_volume_family in log_volume_families:
                log_volumes = log_volume_family['CoreStorageLogicalVolumes']
                for log_volume in log_volumes:
                    volumes.append(self._make_volume(log_volume['CoreStorageUUID']))
        return DUVolumeSet(volumes)

    def get_volume_set(self, volids):
        """Get volume set for volume ids."""
        return self._create_volume_set([self._make_volume(volid) for volid in volids])

    def get_volumes(self, *volids):
        """Generator to provide volume objects for volume ids."""
        for volid in volids:
            yield self._make_volume(volid)

    def mount_volume_set(self, volset):
        """Mount a set of volumes."""
        for volume in volset:
            if os.path.exists(volume.volid):
                if volume.status != 'Mounted':
                    console.info('Mounting: %s' % volume.volid)
                    self._mount_image(volume, volset.password_provider())
            else:
                if volume.status == 'Locked':
                    console.info('Unlocking and mounting: "%s" (%s)'
                                 % (volume.name, volume.volid))
                    self._unlock_volume(volume, volset.password_provider())
                elif not volume.status is None:
                    console.info('Mounting: "%s" (%s)' % (volume.name, volume.volid))
                    self._mount_volume(volume)

    @classmethod
    def _make_volume(cls, volid):
        if os.path.exists(volid):
            name = os.path.splitext(os.path.basename(volid))[0]
            blockcount = 0
            blocksize = 0
            status = None
            with command.Command('hdiutil', 'info') as cmd:
                for line in cmd:
                    fields = line.split(None, 2)
                    if status is None:
                        if fields[0] == 'image-path':
                            if fields[2] == volid:
                                status = 'Mounted'
                    else:
                        if fields[0] == 'image-path':
                            break
                        if fields[0] == 'blockcount':
                            blockcount = int(fields[2])
                        if fields[0] == 'blocksize':
                            blocksize = int(fields[2])
            return DUVolume(volid, name, blockcount * blocksize, status)
        else:
            with DUCoreStorageCommand('information', '-plist', volid) as cmd:
                pass
            if cmd.return_code != 0:
                return DUVolume(volid, None, 0, None)
            plist = read_property_list(*cmd.output_lines)
            return DUVolume(
                volid,
                plist['CoreStorageLogicalVolumeName'],
                int(plist['CoreStorageLogicalVolumeSize']),
                plist['CoreStorageLogicalVolumeStatus']
            )

    def _create_volume_set(self, volumes):
        return DUVolumeSet(volumes, password_provider=self.password_provider)

    def _mount_volume(self, volume):
        with DUCommand('mount', volume.volid).options(dry_run=self.dry_run) as cmd:
            pass
        if not self.dry_run:
            if cmd.return_code != 0:
                console.abort('Mount failed: "%s" (%s)' % (volume.name, volume.volid),
                              cmd.output_lines)
            console.info('Mount succeeded: "%s" (%s)' % (volume.name, volume.volid))

    def _unlock_volume(self, volume, password):
        with DUCoreStorageCommand(
            'unlockVolume',
            volume.volid,
            '-passphrase',
            password).options(
                dry_run=self.dry_run) as cmd:
            pass
        if not self.dry_run:
            if cmd.return_code != 0:
                console.abort('Unlock failed: "%s" (%s)' % (volume.name, volume.volid),
                              cmd.output_lines)
            console.info('Unlock succeeded: "%s" (%s)' % (volume.name, volume.volid))
            time.sleep(10)
        self._mount_volume(volume)

    def _mount_image(self, volume, password):
        with command.Command('hdiutil', 'attach', volume.volid, '-stdinpass').options(
            dry_run=self.dry_run).pipe_in(password) as cmd:
            pass
        if not self.dry_run:
            if cmd.return_code != 0:
                console.abort('Attach failed: %s' % volume.volid, cmd.output_lines)
            console.info('Attach succeeded: %s' % volume.volid)

class DUVolumeSet(object):
    """
    Hold a related set of non-core-storage volumes.

    The volumes require at most one password to unlock any or all of them. The
    password provider supports retrieving the password once and subsequently
    using a cached copy.
    """

    def __init__(self, volumes, password_provider=None):
        """Non-CoreStorage volume set constructor."""
        self.volumes = volumes
        self.password_provider = password_provider

    def __iter__(self):
        """Non-CoreStorage volume set iterator."""
        for volume in self.volumes:
            yield volume


class DUVolume(object):
    """A non-core-storage volume."""

    def __init__(self, volid, name, size, status):
        """Non-core-storage volume constructor."""
        self.volid = volid
        self.name = name
        self.size = size
        self.status = status


class CSVolumeManager(DUVolumeManager):
    """CoreStorage volume."""

    def __init__(self, list_path, password_provider=None, dry_run=False):
        """Core-storage volume constructor."""
        self.list_path = list_path
        DUVolumeManager.__init__(self, password_provider=password_provider, dry_run=dry_run)

    def cs_generate_list_file(self):
        """Generate a list file for available volumes."""
        console.info('"%s" does not exist.' % self.list_path,
                     'Generated a new file with information about all volumes.',
                     'Edit it to specify the volume ID list to use.')
        volset = self.get_complete_volume_set()
        try:
            with open(self.list_path, 'w') as stream:
                for volume in volset:
                    stream.write('# name=%s size=%d id=%s\n# %s\n'
                                 % (volume.name, volume.size, volume.volid, volume.volid))
        except (IOError, OSError) as exc:
            console.abort('Failed to generate volume ID list file "%s".' % self.list_path, exc)

    def cs_volids(self):
        """Get a list of volume ids."""
        if not os.path.exists(self.list_path):
            self.cs_generate_list_file()
            sys.exit(1)
        volids = []
        try:
            with open(self.list_path) as stream:
                for line in stream:
                    stripped_line = line.strip()
                    if not stripped_line.startswith('#'):
                        volids.append(stripped_line)
        except (IOError, OSError) as exc:
            console.abort('Failed to read volume ID list file "%s".' % self.list_path, exc)
        return volids

    def cs_mount(self):
        """Mount all core-storage volumes."""
        volids = self.cs_volids()
        if not volids:
            console.abort('There are no volumes to mount.',
                          'Make sure at least one is specified in "%s".' % self.list_path)
        volset = self.get_volume_set(volids)
        self.mount_volume_set(volset)
        return volset


def read_property_list(*lines):
    """Portable front end to plistlib.readPlistFromString() or loads()."""
    import plistlib
    text = '\n'.join(lines)
    if sys.version_info.major == 2:
        return plistlib.readPlistFromString(text)   #pylint: disable=no-member
    return plistlib.loads(text.encode())
