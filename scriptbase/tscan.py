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
Awk-like text processing with decorated classes.

Basic usage involves deriving a TScanner subclass and implementing
@handle()-decorated methods that receive matches. The subclass can collect data
as it receives matches.

It can also change state via the set_state() method to efficiently route
processing to different matchers and handlers.

The begin() method, if implemented is called at the start of a scan.

An @handle() method may call end_scan() to stop scanning and return. It can
also call next_line() to skip any other handlers for the current line.
"""

import re
from io import StringIO
from typing import List, Union, Callable, Tuple, Text, IO, Dict, Hashable, Optional


class NoStateCls:
    pass


NoState = NoStateCls()


class NextLine(Exception):
    """Exception used to move on to the next scanning line."""
    pass


class TScanner:
    """Base class for awk-like text scanners."""

    scanners: Dict[Hashable, List[Tuple[Optional[re.Pattern], Callable]]] = None

    def __init__(self):
        self._state = None

    @classmethod
    def match(cls,
              pattern: Text = None,
              flags: Union[int, re.RegexFlag] = 0,
              state: Hashable = None):
        if cls.scanners is None:
            cls.scanners = {}

        def _inner(function: Callable) -> Callable:
            compiled_pattern = re.compile(pattern, flags) if pattern else None
            cls.scanners.setdefault(state, []).append((compiled_pattern, function))
            return function

        return _inner

    def scan(self, string_or_stream: Union[Text, IO], state: Hashable = NoState):
        if state is not NoState:
            self.set_state(state)
        self.begin()
        if isinstance(string_or_stream, str):
            stream = StringIO(string_or_stream)
        else:
            stream: IO = string_or_stream
        try:
            for line in stream.readlines():
                for matcher, handler in self.scanners.get(self._state, []):
                    match = matcher.match(line)
                    if match:
                        try:
                            handler(self, match)
                        except NextLine:
                            break
        except StopIteration:
            pass
        # Make it chainable for one-liners.
        return self

    def next_line(self):
        raise NextLine()

    def end_scan(self):
        raise StopIteration

    def begin(self, *args, **kwargs):
        pass

    def get_state(self) -> Hashable:
        return self._state

    def set_state(self, state: Hashable):
        if state not in self.scanners:
            raise RuntimeError(f'State {state} is not supported by '
                               f'parser: {self.__class__.__name__}')
        self._state = state
