#!/usr/bin/env python

import sys, os, os.path, glob
import dialog

uid = os.getuid()
gid = os.getgid()
umask = 077
locale = 'utf8'
locale_full = 'en_US.utf8'
verbose = False

(progdir, progname) = os.path.split(os.path.realpath(sys.argv[0]))

def set_verbose(value):
    global verbose
    verbose = value

def do_mount(device, mountpoint, filesystem, passphrase):
    fsopt = '--fs-options=uid=%d,gid=%d,umask=%03o' % (gid, uid, umask)
    if filesystem == 'ntfs-3g':
        fsopt += ',locale=%s' % locale_full
    else:
        fsopt += ',%s' % locale
    #cmd   = 'truecrypt --load-preferences --cache "%s" "%s" %s' % (device, mountpoint, fsopt)
    if dialog.is_text:
        textopt = ' --text'
    else:
        textopt = ''
    cmd = 'truecrypt%s --load-preferences "%s" "%s" %s' % (textopt, device, mountpoint, fsopt)
    if filesystem:
        cmd += ' --filesystem=%s' % filesystem
    if passphrase:
        cmd += ' --password="%s" --non-interactive' % passphrase
    return dialog.sudo(cmd)

def do_unmount(device, mountpoint):
    cmd = 'truecrypt -d "%s"' % mountpoint
    ret = dialog.sudo(cmd)
    if ret == 0 and os.path.isfile(device):
        os.system('touch "%s"' % device)
    return ret

class Mounter(object):
    class Op(object):
        def __init__(self, device, mountpoint, filesystem = None):
            self.device     = device
            self.mountpoint = mountpoint
            self.filesystem = filesystem
    def __init__(self):
        self.ops = []
    def add(self, mountpoint, devicePat, filesystem = None):
        for device in glob.glob(devicePat):
            self.ops.append(Mounter.Op(device, mountpoint, filesystem = filesystem))
            break
        else:
            dialog.error('device "%s" not found' % devicePat)
    def iter(self):
        if not self.ops:
            dialog.abort('No devices found')
        for op in self.ops:
            if not os.path.exists(op.device):
                dialog.abort('Volume %s does not exist' % op.device)
            if not os.path.exists(op.mountpoint):
                dialog.abort('Mount point %s does not exist' % op.mointpoint)
            yield op
    def mount(self):
        msg = ''
        ops = []
        for op in self.iter():
            if msg:
                msg += '\n'
            for line in open('/proc/mounts'):
                (device, mountpoint) = line.strip().split()[:2]
                if mountpoint == op.mountpoint:
                    msg += '\nOK: %s\n  already mounted' % op.mountpoint
                    break
            else:
                ops.append(op)
        if ops:
            passphrase = dialog.get_password('Mount Passphrase', 'Passphrase')
            if not passphrase:
                dialog.abort('Cancelled')
            for op in ops:
                if do_mount(op.device, op.mountpoint, op.filesystem, passphrase) != 0:
                    msg += '\n* %s mount failed *' % op.mountpoint
                for line in open('/proc/mounts'):
                    (device, mountpoint) = line.strip().split()[:2]
                    if mountpoint == op.mountpoint:
                        msg += '\nMOUNTED: %s' % op.mountpoint
                        break
        if msg:
            dialog.info(msg)
    def unmount(self):
        msg = ''
        for op in self.iter():
            if msg:
                msg += '\n'
            for line in open('/proc/mounts'):
                (device, mountpoint) = line.strip().split()[:2]
                if mountpoint == op.mountpoint:
                    if do_unmount(op.device, op.mountpoint) != 0:
                        msg += '\n* %s unmount failed *' % op.mountpoint
                    break
            else:
                msg += '\nERROR: %s\n  not mounted' % op.mountpoint
        if msg:
            dialog.info(msg)
