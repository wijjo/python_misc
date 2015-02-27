#!/usr/bin/env python

import sys
import os
import getpass
import diskutil
from .. import logger

LIST_PATH = os.path.expanduser('~/.bcvols')


class VolumeManager(diskutil.VolumeManager):

    def __init__(self, dryrun=False):
        def get_password():
            return getpass.getpass('Password: ')
        diskutil.VolumeManager.__init__(self, get_password=get_password, dryrun=dryrun)

    def cs_generate_list_file(self):
        logger.info('"%s" does not exist.' % LIST_PATH,
                    'Generated a new file with information about all volumes.',
                    'Edit it to specify the volume ID list to use.')
        volset = self.get_complete_volume_set()
        try:
            with open(LIST_PATH, 'w') as f:
                for volume in volset:
                    f.write('# name=%s size=%d id=%s\n# %s\n'
                                % (volume.name, volume.size, volume.volid, volume.volid))
        except (IOError, OSError), e:
            logger.abort('Failed to generate volume ID list file "%s".' % LIST_PATH, e)

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
        except (IOError, OSError), e:
            logger.abort('Failed to read volume ID list file "%s".' % LIST_PATH, e)
        return volids

    def cs_mount(self):
        volids = self.cs_volids()
        if not volids:
            logger.abort('There are no volumes to mount.',
                         'Make sure at least one is specified in "%s".' % LIST_PATH)
        volset = self.get_volume_set(volids)
        self.mount_volume_set(volset)
