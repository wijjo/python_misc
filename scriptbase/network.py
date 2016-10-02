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

import os

from . import comsole


def get_listener(port):
    with command.Command('lsof', '-i:%d' % port, '-sTCP:LISTEN', '-t') as cmd:
        for line in cmd:
            return int(line)


def ssh_tunnel_connect(remote_host, remote_port, local_port, ssh_port=22, dryrun=False):
    lpid = get_listener(local_port)
    if lpid is None:
        console.info('Connecting tunnel from %(remote_host)s:%(remote_port)d '
                     'to localhost:%(local_port)d...' % locals())
        autossh_cmd = ('autossh -M 0 -f -N -o '
                       '"ServerAliveInterval 60" -o "ServerAliveCountMax 3" '
                       '-p %(ssh_port)d '
                       '-L %(local_port)d:localhost:%(remote_port)d '
                       '%(remote_host)s' % locals())
        if dryrun:
            console.info(autossh_cmd)
        else:
            if os.system(autossh_cmd) == 0:
                console.info('Tunnel from %(remote_host)s:%(remote_port)d '
                             'to localhost:%(local_port)d is active.' % locals())
            else:
                console.abort('Failed to connect tunnel from %(remote_host)s:%(remote_port)d '
                              'to localhost:%(local_port)d.' % locals())
    else:
        console.info('Port %(local_port)d is already handled by process %(lpid)d.' % locals())


def ssh_tunnel_disconnect(local_port, dryrun=False):
    lpid = get_listener(local_port)
    if lpid:
        console.info('Killing port %(local_port)d listener process %(lpid)d...' % locals())
        kill_cmd = 'kill %(lpid)d' % locals()
        if dryrun:
            console.info(kill_cmd)
        else:
            if os.system(kill_cmd) == 0:
                console.info('Port listener process %(lpid)d was killed and '
                             'port %(local_port)d was disconnected.' % locals())
            else:
                console.abort('Failed to kill listener process %(lpid)d.' % locals())
    else:
        console.info('Port %(port)d does not have an active listener.' % locals())
