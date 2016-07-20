#!/usr/bin/env python

# Mac diskutil API

import os
import time
from .. import run
from .. import console
import plistlib


class DiskutilCommand(run.Command):
    """
    Diskutil Command object for regular commands.
    """

    def __init__(self, verb, *args, **kwargs):
        """
        Constructor takes a verb and arguments and prepends ['diskutil'].
        """
        run.Command.__init__(self, 'diskutil', verb, *args, **kwargs)


class CoreStorageCommand(DiskutilCommand):
    """
    Diskutil Command object for corestorage commands.
    """

    def __init__(self, verb, *args, **kwargs):
        """
        Constructor takes a verb and arguments and prepends ['diskutil',
        'corestorage'].
        """
        DiskutilCommand.__init__(self, 'coreStorage', verb, *args, **kwargs)


class PasswordProvider(object):
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


class VolumeManager(object):
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
        cmd = CoreStorageCommand('list', '-plist')
        plist_text = '\n'.join(cmd.run())
        plist = plistlib.readPlistFromString(plist_text)
        volumes = []
        lvm_groups = plist['CoreStorageLogicalVolumeGroups']
        for lvm_group in lvm_groups:
            log_volume_families = lvm_group['CoreStorageLogicalVolumeFamilies']
            for log_volume_family in log_volume_families:
                log_volumes = log_volume_family['CoreStorageLogicalVolumes']
                for log_volume in log_volumes:
                    volumes.append(self._make_volume(log_volume['CoreStorageUUID']))
        return VolumeSet(volumes)

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
            cmd = run.Command('hdiutil', 'info')
            for line in cmd.run():
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
            return Volume(volid, name, blockcount * blocksize, status)
        else:
            cmd = CoreStorageCommand('information', '-plist', volid)
            plist_text = '\n'.join(cmd.run())
            if cmd.retcode != 0:
                return Volume(volid, None, 0, None)
            plist = plistlib.readPlistFromString(plist_text)
            return Volume(
                volid,
                plist['CoreStorageLogicalVolumeName'],
                int(plist['CoreStorageLogicalVolumeSize']),
                plist['CoreStorageLogicalVolumeStatus']
            )

    def _create_volume_set(self, volumes):
        password_provider = PasswordProvider(self.get_password,
            'A password is required to unlock volume(s).',
            'No get_password call-back was provided and a password is needed.',
            dryrun=self.dryrun)
        return VolumeSet(volumes, password_provider=password_provider)

    def _mount_volume(self, volume):
        cmd = DiskutilCommand('mount', volume.volid, dryrun=self.dryrun)
        output = cmd.run()
        if cmd.retcode != 0:
            console.abort('Mount failed: "%s" (%s)' % (volume.name, volume.volid), output)
        console.info('Mount succeeded: "%s" (%s)' % (volume.name, volume.volid))

    def _unlock_volume(self, volume, password):
        cmd = CoreStorageCommand('unlockVolume', volume.volid, '-passphrase', password,
                                 dryrun=self.dryrun)
        output = cmd.run()
        if cmd.retcode != 0:
            console.abort('Unlock failed: "%s" (%s)' % (volume.name, volume.volid), output)
        console.info('Unlock succeeded: "%s" (%s)' % (volume.name, volume.volid))
        time.sleep(5)
        self._mount_volume(volume)

    def _mount_image(self, volume, password):
        cmd = run.Command('hdiutil', 'attach', volume.volid, '-stdinpass',
                          input=password, dryrun=self.dryrun)
        output = cmd.run()
        if cmd.retcode != 0:
            console.abort('Attach failed: %s' % volume.volid, output)
        console.info('Attach succeeded: %s' % volume.volid)

class VolumeSet(object):
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


class Volume(object):

    def __init__(self, volid, name, size, status):
        self.volid = volid
        self.name = name
        self.size = size
        self.status = status
