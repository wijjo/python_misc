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

"""
Mac diskutil API.
"""

import os
import time
import plistlib
import getpass
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from .. import command
from .. import console

LIST_PATH = os.path.expanduser('~/.bcvols')


class DUCommand(command.Command):
    """
    Diskutil Command object for regular commands.
    """

    def __init__(self, verb, *args):
        """
        Constructor takes verb + arguments and prepends ['diskutil'].
        """
        command.Command.__init__(self, 'diskutil', verb, *args)


class DUCoreStorageCommand(DUCommand):
    """
    Diskutil Command object for corestorage commands.
    """

    def __init__(self, verb, *args):
        """
        Constructor takes verb + arguments and prepends ['diskutil', 'coreStorage'].
        """
        DUCommand.__init__(self, 'coreStorage', verb, *args)


class DUPasswordProvider(object):
    """
    Class used internally to receive and cache a password on demand.
    """

    def __init__(self, get_password, message, error_message, dryrun=False):
        """
        Constructor with call-back and messages for display.
        """
        self.get_password = get_password
        self.message = message
        self.password = None
        if dryrun:
            self.password = 'PASSWORD'

    def __call__(self):
        """
        Emulate a function. Get the password once and provide a cached copy
        after the first call.
        """
        if self.password is None and not self.get_password is None:
            if self.message:
                console.info(self.message)
            self.password = self.get_password()
        if self.password is None:
            console.abort(self.error_message)
        return self.password


class DUVolumeManager(object):
    """
    Provides the high level API for managing CoreStorage volumes.
    """

    def __init__(self, get_password=None, dryrun=False):
        """
        Constructor accepts an optional password generation function which will
        be called as needed to unlock volume sets.
        """
        self.get_password = get_password
        self.dryrun = dryrun

    def get_complete_volume_set(self):
        with DUCoreStorageCommand('list', '-plist') as cmd:
            pass
        plist_text = '\n'.join(cmd.output_lines)
        plist = plistlib.readPlistFromString(plist_text)
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
        return self._create_volume_set([self._make_volume(volid) for volid in volids])

    def get_volumes(self, *volids):
        for volid in volids:
            yield self._make_volume(volid)

    def mount_volume_set(self, volset):
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

    def _make_volume(self, volid):
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
            plist_text = '\n'.join(cmd.output_lines)
            if cmd.rc != 0:
                return DUVolume(volid, None, 0, None)
            plist = plistlib.readPlistFromString(plist_text)
            return DUVolume(
                volid,
                plist['CoreStorageLogicalVolumeName'],
                int(plist['CoreStorageLogicalVolumeSize']),
                plist['CoreStorageLogicalVolumeStatus']
            )

    def _create_volume_set(self, volumes):
        password_provider = DUPasswordProvider(self.get_password,
            'A password is required to unlock volume(s).',
            'No get_password call-back was provided and a password is needed.',
            dryrun=self.dryrun)
        return DUVolumeSet(volumes, password_provider=password_provider)

    def _mount_volume(self, volume):
        with DUCommand('mount', volume.volid).options(dryrun=self.dryrun) as cmd:
            pass
        if not self.dryrun:
            if cmd.rc != 0:
                console.abort('Mount failed: "%s" (%s)' % (volume.name, volume.volid), cmd.output_lines)
            console.info('Mount succeeded: "%s" (%s)' % (volume.name, volume.volid))

    def _unlock_volume(self, volume, password):
        with DUCoreStorageCommand('unlockVolume', volume.volid, '-passphrase', password
                ).options(dryrun=self.dryrun) as cmd:
            pass
        if not self.dryrun:
            if cmd.rc != 0:
                console.abort('Unlock failed: "%s" (%s)' % (volume.name, volume.volid), cmd.output_lines)
            console.info('Unlock succeeded: "%s" (%s)' % (volume.name, volume.volid))
            time.sleep(10)
        self._mount_volume(volume)

    def _mount_image(self, volume, password):
        with command.Command('hdiutil', 'attach', volume.volid, '-stdinpass'
                ).options(dryrun=self.dryrun).pipe_in(password) as cmd:
            pass
        if not self.dryrun:
            if cmd.rc != 0:
                console.abort('Attach failed: %s' % volume.volid, cmd.output_lines)
            console.info('Attach succeeded: %s' % volume.volid)

class DUVolumeSet(object):
    """
    Holds a related set of volumes that require at most one password to unlock
    any or all of them. The password provider supports retrieving the password
    once and subsequently using a cached copy.
    """

    def __init__(self, volumes, password_provider=None):
        self.volumes = volumes
        self.password_provider = password_provider

    def __iter__(self):
        for volume in self.volumes:
            yield volume


class DUVolume(object):

    def __init__(self, volid, name, size, status):
        self.volid = volid
        self.name = name
        self.size = size
        self.status = status


class CSVolumeManager(DUVolumeManager):

    def __init__(self, dryrun=False):
        def get_password():
            return getpass.getpass('Password: ')
        DUVolumeManager.__init__(self, get_password=get_password, dryrun=dryrun)

    def cs_generate_list_file(self):
        console.info('"%s" does not exist.' % LIST_PATH,
                     'Generated a new file with information about all volumes.',
                     'Edit it to specify the volume ID list to use.')
        volset = self.get_complete_volume_set()
        try:
            with open(LIST_PATH, 'w') as f:
                for volume in volset:
                    f.write('# name=%s size=%d id=%s\n# %s\n'
                                % (volume.name, volume.size, volume.volid, volume.volid))
        except (IOError, OSError) as e:
            console.abort('Failed to generate volume ID list file "%s".' % LIST_PATH, e)

    def cs_volids(self):
        if not os.path.exists(LIST_PATH):
            self.cs_generate_list_file()
            sys.exit(1)
        volids = []
        try:
            with open(LIST_PATH) as f:
                for line in f:
                    s = line.strip()
                    if not s.startswith('#'):
                        volids.append(s)
        except (IOError, OSError) as e:
            console.abort('Failed to read volume ID list file "%s".' % LIST_PATH, e)
        return volids

    def cs_mount(self):
        volids = self.cs_volids()
        if not volids:
            console.abort('There are no volumes to mount.',
                          'Make sure at least one is specified in "%s".' % LIST_PATH)
        volset = self.get_volume_set(volids)
        self.mount_volume_set(volset)
