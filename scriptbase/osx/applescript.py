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


from .. import command

def run_applescript(*lines):
    args = ['osascript']
    for line in lines:
        for subline in line.split('\n'):
            if subline.strip():
                args.extend(['-e', subline.strip()])
    with command.Command(*args) as cmd:
        cmd.run()
    return cmd.return_code


def run_application_applescript(app, *lines):
    lines2 = ['tell application "%s"' % app] + list(lines) + ['end tell']
    return run_applescript(*lines2)
