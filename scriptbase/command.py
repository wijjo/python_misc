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

import sys
import os
import subprocess
import tempfile

# Import six if available globally or locally from scriptbase/python
# Python2-3 compatibility helper library.
try:
    import six
except ImportError:
    from .python import six

"""
Wraps the standard Python subprocess module to simplify common usage patterns.

This module trades ease of use for much less flexibility than the subprocess
module it is built upon.  For example, it only supports line-buffering and
always merges stderr with stdout.

An input pipe can be accessed either real-time or all at once, but when piping
between Command objects the second Command does not receive the first Command's
output until EOF.

Compatibility is maintained with both Python versions 2 and 3, although it has
not been tested with Python 2 versions older than 2.7.

Examples:

from scriptbase.cmd import Command

# Output to console
with Command('ls', '-l') as lscmd:
    lscmd.run()
# Access the return code outside the with block to allow the command to finish.
print('ls returned %d' % lscmd.rc)

# Get all output lines as a list.
with Command('ls', '-l') as lscmd:
    output_lines = lscmd.read_lines()
print('ls returned %d' % lscmd.rc)

# Iterate output lines.
with Command('ls', '-l') as lscmd:
    for line in lscmd:
        print line
print('ls returned %d' % lscmd.rc)

# Pipe one command into another (using pipe_in).
with Command('ls', '-l') as lscmd:
    with Command('grep', '^-rwx').pipe_in(lscmd) as grepcmd:
        for line in grepcmd:
            print line
    print('grep returned %d' % grepcmd.rc)
print('ls returned %d' % lscmd.rc)

# Pipe one command into another (using pipe_out).
# Note that pipe_out() is just a convenience wrapper for pipe_in(), as used above.
with Command('ls', '-l') as lscmd:
    with lscmd.pipe_out('grep', '^-rwx') as grepcmd:
        for line in grepcmd:
            print line
    print('grep returned %d' % grepcmd.rc)
print('ls returned %d' % lscmd.rc)

# Pipe string into command.
with Command('grep', 'abc').pipe_in('111\\n222\\nabc\\n333\\n') as grepcmd:
    for line in grepcmd:
        print line
print('grep returned %d' % grepcmd.rc)

# Pipe string list (iterable) into command.
with Command('grep', 'abc').pipe_in(['111','222','abc','333']) as grepcmd:
    for line in grepcmd:
        print line
print('grep returned %d' % grepcmd.rc)

# Pipe file stream into command.
with Command('grep', 'abc').pipe_in(open('/path/to/file')) as grepcmd:
    for line in grepcmd:
        print line
print('grep returned %d' % grepcmd.rc)
"""


#===============================================================================
class Command(object):
    """
    Run a single command with various methods for accessing results.

    A Command object must be used in a "with" statement to assure proper clean-up.
    Once inside the "with" statement methods can be called to iterate output, run
    to completion with output on the console, or read output lines into a list.

    For now stdout and stderr are merged into one line-buffered output stream.

    Command objects support iteration that yields a line at a time.

    The return code rc member is None until outside the "with" block.
    """
#===============================================================================

    class NotInWithBlock(RuntimeError):
        """
        Raised when attempting to run a Command object that was created outside
        of a "with" block.
        """
        def __init__(self):
            RuntimeError.__init__(self,
                    'Illegal attempt to use a Command without a "with" block.')

    class AlreadyRunning(RuntimeError):
        """
        Raised when attempting to set options for a Command object that is
        already running.
        """
        def __init__(self):
            RuntimeError.__init__(self,
                    'Illegal attempt to set Command options after it is running.')

    def __init__(self, *args):
        """
        Constructor accepts a variable length command line argument list.
        """
        self.args = args
        self.p = None
        self.done = False
        self.output_lines = []
        self.capture_on_exit = True
        self.input_source = None
        self.bufsize=1
        self.rc = None

    def options(self,
        bufsize=None,
        capture_on_exit=None,
        input_source=None,
    ):
        """
        Set options immediately after constructions.

        Returns self so that a chained call provides the "with" statement object.

        bufsize          buffer size, see subprocess.Popen() for more information (default=1)
        capture_on_exit  captures remaining output to "output_lines" member if True (default=True)
        input_source     string, stream, or Command to pipe to standard input (default=None)
        """
        self._check_not_running()
        if bufsize is not None:
            self.bufsize = bufsize
        if capture_on_exit is not None:
            self.capture_on_exit = capture_on_exit
        if input_source is not None:
            self.input_source = input_source
        self.input_source = input_source
        return self

    def __enter__(self):
        self.p = subprocess.Popen(
                    self.args,
                    bufsize=self.bufsize,
                    stdin=self.input_source,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT)
        if self.input_source:
            self.input_source.close()
        return self

    def __exit__(self, type, value, traceback):
        if self.p is not None:
            if self.capture_on_exit:
                self.output_lines.extend([line for line in self.__iter__()])
            self.rc = self.p.wait()

    def _check_in_with_block(self):
        if self.p is None:
            raise Command.NotInWithBlock()

    def _check_not_running(self):
        if self.p is not None:
            raise Command.AlreadyRunning()

    def __iter__(self):
        """
        Iterator runs the command and yields a line at a time.
        """
        self._check_in_with_block()
        self.capture_on_exit = False
        # Work around a Python 2 readline issue (https://bugs.python.org/issue3907).
        if not self.p.stdout.closed:
            with self.p.stdout:
                for line in iter(self.p.stdout.readline, b''):
                    yield line.rstrip()

    def run(self):
        """
        Run the command with output going to the console (stdout).
        """
        self._check_in_with_block()
        for line in self.__iter__():
            sys.stdout.write('%s\n' % line)

    def read_lines(self):
        """
        Run the command and return a list of output lines.
        """
        return [line for line in self.__iter__()]

    def pipe_in(self, input_obj):
        """
        Set up an input stream pipe from a string, stream, or Command object.

        Note that a string list represents multiple lines, and line separators
        are added automatically.

        Arguments:
            input_obj  string, string list, stream, or Command pipe input
        """
        if isinstance(input_obj, Command):
            input_source = self._input_source_from_command(input_obj)
        elif isinstance(input_obj, six.string_types) or isinstance(input_obj, bytes):
            input_source = self._input_source_from_strings(False, input_obj)
        elif hasattr(input_obj, '__iter__'):
            input_source = self._input_source_from_strings(True, *input_obj)
        else:
            # Assume everything else is a proper file stream.
            input_source = input_obj
        return self.options(input_source=input_source)

    def pipe_out(self, *args):
        """
        Create a Command object to use in a "with" block with piped input.

        The stdout of self is attached to the stdin of the new Command.

        Arguments:
            args  variable length command argument list
        """
        return Command(*args).pipe_in(self.p.stdout)

    def _input_source_from_command(self, command_obj):
        command_obj._check_in_with_block()
        return command_obj.p.stdout

    def _input_source_from_strings(self, add_line_separators, *input_strs):
        # Spool strings or bytes through a temporary file.
        input_source = tempfile.SpooledTemporaryFile()
        for input_str in input_strs:
            if isinstance(input_str, bytes):
                input_source.write(input_str)
            else:
                input_source.write(str.encode(input_str))
            if add_line_separators:
                input_source.write(str.encode(os.linesep))
        input_source.seek(0)
        return input_source
