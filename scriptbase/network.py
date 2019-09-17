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

"""Network utilities."""

import os

from . import console
from . import disk
from . import command


def get_listener(port):
    """Return port listener if any."""
    with command.Command('lsof', '-i:%d' % port, '-sTCP:LISTEN', '-t') as cmd:
        for line in cmd:
            return int(line)


def ssh_tunnel_connect(     #pylint: disable=unused-argument
        remote_host,
        remote_port,
        local_port,
        ssh_port=22,
        dry_run=False):
    """Set up and connect an SSH tunnel."""
    context = console.Context(**locals())
    lpid = get_listener(local_port)
    if lpid is None:
        context.info('Connecting tunnel from {remote_host}:{remote_port} '
                     'to localhost:{local_port}...')
        autossh_cmd = ('autossh -M 0 -f -N -o '
                       '"ServerAliveInterval 60" -o "ServerAliveCountMax 3" '
                       '-p {ssh_port} '
                       '-L {local_port}:localhost:{remote_port} '
                       '{remote_host}')
        if dry_run:
            context.info(autossh_cmd)
        else:
            if os.system(autossh_cmd) == 0:
                context.info('Tunnel from {remote_host}:{remote_port} '
                             'to localhost:{local_port} is active.')
            else:
                context.abort('Failed to connect tunnel from {remote_host}:{remote_port} '
                              'to localhost:{local_port}.')
    else:
        context.info('Port {local_port} is already handled by process {lpid}.')


def ssh_tunnel_disconnect(local_port, dry_run=False):
    """Disconnect an ssh tunnel."""
    context = console.Context(**locals())
    lpid = get_listener(local_port)
    if lpid:
        context.info('Killing port {local_port} listener process {lpid}...')
        kill_cmd = context.format_string('kill {lpid}')
        if dry_run:
            context.info(kill_cmd)
        else:
            if os.system(kill_cmd) == 0:
                context.info('Port listener process {lpid} was killed and '
                             'port {local_port} was disconnected.')
            else:
                context.abort('Failed to kill listener process {lpid}.')
    else:
        context.info('Port {port} does not have an active listener.')


def sshfs_mount(mountpoint, remote_host, ssh_port=22, dry_run=False):  # pylint: disable=unused-argument
    """Use sshfs to mount a remote drive."""
    context = console.Context(**locals())
    if disk.mounts_check(mountpoint):
        context.info('{mountpoint} was already mounted.')
    else:
        if not os.path.exists(mountpoint):
            if dry_run:
                context.info('mkdir {mountpoint}')
            else:
                os.mkdir(mountpoint)
        sshfs_cmd = context.format_string(
            'sshfs -p {ssh_port} -o idmap=user -o defer_permissions {remote_host}:/ {mountpoint}')
        if dry_run:
            context.info(sshfs_cmd)
        else:
            if os.system(sshfs_cmd) == 0:
                context.info('{mountpoint} is mounted.')
            else:
                context.abort('{mountpoint} failed to mount.')
