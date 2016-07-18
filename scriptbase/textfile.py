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

from contextlib import contextmanager

class TextFile(object):
    '''Simplifies line-oriented text output.  The write() method flattens
    strings and iterable items and writes lines to the path or file object
    passed to the constructor.  A None argument closes the file, as will
    exceptions and the close() method.  Exceptions are passed to the caller.'''
    def __init__(self, file_or_path, indent_by = 2):
        self.file_or_path = file_or_path
        self.f            = None
        self.indent_by    = indent_by
        self.indent_pos   = 0
    def write(self, *lines_and_sublists):
        if not self.f:
            self._open('w')
        self._write(lines_and_sublists)
    def read(self):
        if not self.f:
            self._open('r')
        for line in self.f:
            yield line.rstrip()
        self._close()
    def __iter__(self):
        for line in self.read():
            yield line
    def close(self):
        if not self.f:
            # Make sure we can close a file object, but don't open a path (None).
            self._open(None)
        self._close()
    def _open(self, mode):
        # Assume file_or_path is either a string or a file-like object
        if mode:
            self.f = self.file_or_path
            try:
                self.f = open(self.file_or_path + '', mode)
            except TypeError:
                pass
    def _write(self, lists_or_sublists):
        if lists_or_sublists is None:
            self.close()
        else:
            try:
                for list_or_sublist in lists_or_sublists:
                    # Strings support concatenation.  Assume anything else is iterable.
                    try:
                        line = list_or_sublist + '\n'
                        if self.indent_pos > 0:
                            self.f.write(' ' * (self.indent_by * self.indent_pos))
                        self.f.write(line)
                    except TypeError:
                        # Indent sub-lists
                        with self.indented():
                            self._write(list_or_sublist)
            except:
                self._close()
                raise
    def _close(self):
        if self.f:
            self.f.close()
        self.f = None
    @contextmanager
    def indented(self, count = 1):
        '''Use indented() as the argument to a "with" statement for balanced indentation.'''
        try:
            self.indent_pos += count
            yield None
        except:
            raise
        else:
            self.indent_pos -= count
    # Support entry/exit conditions for "with" statement
    def __enter__(self):
        # Actual open is lazy in order to know what mode to use.
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
