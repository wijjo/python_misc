# Copyright 2020 Steven Cooper
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

from __future__ import annotations
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Text, Optional, List, Callable, Any, NoReturn, Dict, ForwardRef

import PySimpleGUI as gui


@dataclass
class ActionButtonSpec:
    name: Text
    default: bool


HandlerFunction = Callable[[ForwardRef('AdminPanel'), Any], NoReturn]


class AdminPanel:

    def __init__(self, title: Text = None):
        self.title = title or 'Administration Panel'
        self.heading: Optional[Text] = None
        self.need_root = False
        self.bind_escape_key = False
        self.log_path: Optional[Text] = None
        self.actions: List[Text] = []
        self.default_action: Optional[Text] = None
        self.debug = False
        self.dry_run = False
        self.window: Optional[gui.Window] = None
        self.password: Optional[Text] = None
        self.handlers: Dict[Text, HandlerFunction] = {}

    def set_need_root(self, value: bool = False):
        self.need_root = value

    def add_action(self,
                   name: Text,
                   handler: Callable[[AdminPanel, Any], NoReturn] = None):
        action_name = f'{name[0].upper()}{name[1:].lower()}'
        self.actions.append(action_name)
        if handler:
            self.add_handler(name, handler)

    def set_default_action(self, default_action: Optional[Text]):
        self.default_action = default_action

    def set_heading(self, heading: Text):
        self.heading = heading

    def set_log_path(self, log_path: Text):
        self.log_path = log_path

    def set_debug(self, value: bool = False):
        self.debug = value

    def set_dry_run(self, value: bool = False):
        self.dry_run = value

    def set_bind_escape_key(self, value: bool = False):
        self.bind_escape_key = value

    def add_handler(self, name: Text, function: HandlerFunction):
        self.handlers[name] = function

    def make_layout(self) -> List:
        layout = []
        if self.heading:
            layout.append([gui.Text(self.heading)])
        if self.need_root:
            layout.append([gui.Text('Password:'),
                           gui.InputText(key='password', password_char='*')])
            default_text = 'Password is required to run some commands as root.\n'
        else:
            default_text = ''
        layout.append([gui.Multiline(key='status',
                                     size=(0, 5),
                                     disabled=True,
                                     default_text=default_text)])
        layout.append([gui.HorizontalSeparator()])
        buttons = [gui.Cancel(button_text='Close',
                              button_color=('white', 'grey')),
                   gui.Text(key='filler')]
        for action_name in self.actions:
            if action_name.lower() == self.default_action.lower():
                buttons.append(gui.Button(button_text=action_name,
                                          bind_return_key=True,
                                          button_color=('white', '#aa5555')))
            else:
                buttons.append(gui.Button(button_text=action_name))
        layout.append(buttons)
        return layout

    def log(self, message: Text, error=False, debug=False, status=False):
        preamble = '[E] ' if error else ''
        if error:
            for message_line in message.split(os.linesep):
                sys.stderr.write(f'{preamble}{message_line}{os.linesep}')
        elif not debug or self.debug:
            for message_line in message.split(os.linesep):
                sys.stdout.write(f'{preamble}{message_line}{os.linesep}')
        if self.log_path:
            with open(self.log_path, 'a', encoding='utf-8') as log_file:
                for message_line in message.split(os.linesep):
                    log_file.write(f'{preamble}{message_line}{os.linesep}')
        if status:
            self.add_status(message, error=error)

    def add_status(self, message: Text, error=False):
        preamble = '[E] ' if error else ''
        for message_line in message.split(os.linesep):
            self.window['status'].update(f'{preamble}{message_line}{os.linesep}',
                                         append=True, autoscroll=True)
        self.window.refresh()

    def clear_status(self):
        self.window['status'].update('')

    def run(self, *cmd_args, root=False, ignore_dry_run=False) -> Text:
        if root and self.password is None:
            raise RuntimeError('Unable to run command as root without a password.')
        cmd_args = (['sudo', '-S'] if root else []) + list(cmd_args)
        cmd_str = ' '.join([shlex.quote(arg) for arg in cmd_args])
        self.log(f'> {cmd_str}', status=True)
        if self.dry_run and not ignore_dry_run:
            return ''
        proc = subprocess.run(cmd_args,
                              input=self.password,
                              encoding='utf-8',
                              capture_output=True)
        if proc.stdout:
            if proc.returncode == 0:
                self.log(proc.stdout, debug=True)
            else:
                self.log(proc.stderr, error=True)
        if proc.stderr:
            self.log(proc.stderr, error=True)
        if proc.returncode != 0:
            raise RuntimeError(f'Failed ({proc.returncode}): {cmd_str}')
        return proc.stdout

    def handle_event(self, event: Text, values=None):
        if event in self.handlers:
            self.handlers[event](self, values)

    def start(self):
        assert self.window is None
        # gui.theme_previewer()
        gui.theme('BlueMono')
        gui.set_options(font='Sans 14', margins=(20, 20), element_padding=(2, 10))
        layout = self.make_layout()
        self.window = gui.Window(self.title, layout, finalize=True)
        if self.bind_escape_key:
            self.window.bind('<Escape>', None)
        self.window['filler'].expand(expand_row=True, expand_x=True)
        self.window['status'].expand(expand_row=True, expand_x=True)
        if self.need_root:
            self.window['password'].expand()
        self.handle_event('Initialize')
        while True:
            event, values = self.window.read()
            log_values = dict(values)
            if log_values.get('password'):
                log_values['password'] = '****'
            if log_values.get('status'):
                log_values['status'] = f'<{len(log_values["status"].strip().split(os.linesep))} line(s)>'
            self.log(f'event="{event}", values={log_values}')
            if self.need_root:
                self.password = values['password']
            if event == gui.WIN_CLOSED or event == 'Close' or event == '<Escape>':
                self.window.close()
                break
            try:
                self.handle_event(event, values)
            except RuntimeError as exc:
                self.log(str(exc), error=True, status=True)
                self.handle_event('Error', None)
                if self.log_path:
                    self.add_status(f'See {self.log_path} for details.')
