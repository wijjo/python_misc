#!/usr/bin/env python

"""
Wraps the standard Python subprocess module to simplify common usage patterns.

It supports real-time or all at once access to output.  Limitations are that it
is line-oriented only, and always merges stderr with stdout, and generally much
less flexible than subprocess.Popen().

It is currently compatible with both Python versions 2 and 3. It has not been
tested with Python versions older than 2.7.

Examples:

from python_misc.cmd import Command

# Output to console
with Command('ls', '-l') as lscmd:
    lscmd.run()
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

# Pipe one command into another (using pipe_out).
with Command('ls', '-l') as lscmd:
    with lscmd.pipe_out('grep', '^-rwx') as grepcmd:
        for line in grepcmd:
            print line
    print('grep returned %d' % grepcmd.rc)
print('ls returned %d' % lscmd.rc)

# Pipe one command into another (using pipe_in).
with Command('ls', '-l') as lscmd:
    with Command('grep', '^-rwx').pipe_in(lscmd) as grepcmd:
        for line in grepcmd:
            print line
    print('grep returned %d' % grepcmd.rc)
print('ls returned %d' % lscmd.rc)

# Pipe string into command.
with Command('grep', 'abc').pipe_in('111\\n222\\nabc\\n333\\n') as grepcmd:
    for line in grepcmd:
        print line
print('grep returned %d' % grepcmd.rc)

# Pipe file stream into command.
with Command('grep', 'abc').pipe_in(open('/path/to/file')) as grepcmd:
    for line in grepcmd:
        print line
print('grep returned %d' % grepcmd.rc)
"""

import sys
import subprocess
import tempfile

# Import six if available globally or locally from python_misc/python
# Python2-3 compatibility helper library.
try:
    import six
except ImportError:
    from python import six


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

    class NotInWithBlock(RuntimeError):
        """
        Raised when attempting to run a Command object that was created outside of a "with" block.
        """
        def __init__(self):
            RuntimeError.__init__(self, 'Illegal attempt to use a Command without a "with" block.')

    class AlreadyRunning(RuntimeError):
        """
        Raised when attempting to set options for a Command object that is already running.
        """
        def __init__(self):
            RuntimeError.__init__(self, 'Illegal attempt to set Command options after it is running.')

    def __init__(self, *args):
        """
        Constructor accepts a variable length command line argument list.
        """
        self.args = args
        self.p = None
        self.done = False
        self.lines = []
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
        It isn't very useful yet, except internally.

        bufsize          buffer size, see subprocess.Popen() for more information (default=1)
        capture_on_exit  captures remaining output to "lines" member if True (default=True)
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
                self.lines.extend([line for line in self.__iter__()])
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

        Arguments:
            input_obj  string, stream, or Command to serve as the pipe input
        """
        if isinstance(input_obj, Command):
            # If it's a command use its p.stdout member as the stream.
            input_obj._check_in_with_block()
            input_source = input_obj.p.stdout
        elif isinstance(input_obj, six.string_types) or isinstance(input_obj, bytes):
            # Spool a string through a temporary file.
            input_source = tempfile.SpooledTemporaryFile()
            if isinstance(input_obj, bytes):
                input_source.write(input_obj)
            else:
                input_source.write(str.encode(input_obj))
            input_source.seek(0)
        else:
            # Assume anything else is a proper file stream.
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


def test():

    print('=== full iteration')
    # Add a sleep after the echo to see that output isn't delayed.
    with Command('bash', '-c', 'for i in 111 222 333; do echo $i; done') as test_cmd:
        lines = [line for line in test_cmd]
    assert(lines == [b'111', b'222', b'333'])
    assert(not test_cmd.lines)
    assert(test_cmd.rc == 0)

    print('=== partial iteration')
    lines = []
    with Command('bash', '-c', 'for i in 111 222 333; do echo $i; done') as test_cmd:
        for line in test_cmd:
            lines.append(line)
            break
    assert(lines == [b'111'])
    assert(not test_cmd.lines)

    print('=== captured on close')
    with Command('bash', '-c', 'for i in 111 222 333; do echo $i; done') as test_cmd:
        pass
    assert(test_cmd.lines == [b'111', b'222', b'333'])
    assert(test_cmd.rc == 0)

    print('=== all at once')
    with Command('bash', '-c', 'for i in 111 222 333; do echo $i; done') as test_cmd:
        lines = test_cmd.read_lines()
    assert(lines == [b'111', b'222', b'333'])
    assert(not test_cmd.lines)
    assert(test_cmd.rc == 0)

    print('=== console')
    with Command('bash', '-c', 'ls -l /tmp > /dev/null') as test_cmd:
        test_cmd.run()
    assert(not test_cmd.lines)
    assert(test_cmd.rc == 0)

    print('=== NotInWithBlock exception')
    test_cmd = Command('bash', '-c', 'for i in 111 222 333; do echo $i; done')
    try:
        test_cmd.read_lines()
        assert(False)
    except Command.NotInWithBlock:
        pass

    print('=== output pipe')
    lines = []
    with Command('bash', '-c', 'for i in a b c d e; do echo $i; done') as test_cmd:
        with test_cmd.pipe_out('grep', '[bd]') as grep_cmd:
            lines = [line for line in grep_cmd]
        assert(not grep_cmd.lines)
        assert(grep_cmd.rc == 0)
    assert(lines == [b'b', b'd'])
    assert(not test_cmd.lines)
    assert(test_cmd.rc == 0)

    print('=== input pipe')
    lines = []
    with Command('bash', '-c', 'for i in a b c d e; do echo $i; done') as test_cmd:
        with Command('grep', '[bd]').pipe_in(test_cmd) as grep_cmd:
            lines = [line for line in grep_cmd]
        assert(not grep_cmd.lines)
        assert(grep_cmd.rc == 0)
    assert(lines == [b'b', b'd'])
    assert(not test_cmd.lines)
    assert(test_cmd.rc == 0)

    print('=== input bytes')
    lines = []
    with Command('grep', '[bd]').pipe_in(b'a\nb\n\c\nd\n\e\n') as test_cmd:
        lines = [line for line in test_cmd]
    assert(lines == [b'b', b'd'])
    assert(not test_cmd.lines)
    assert(test_cmd.rc == 0)

    print('=== input string')
    lines = []
    with Command('grep', '[bd]').pipe_in('a\nb\n\c\nd\n\e\n') as test_cmd:
        lines = [line for line in test_cmd]
    assert(lines == [b'b', b'd'])
    assert(not test_cmd.lines)
    assert(test_cmd.rc == 0)

    print('=== input stream')
    lines = []
    tmp = tempfile.SpooledTemporaryFile()
    tmp.write(b'a\nb\n\c\nd\n\e\n')
    tmp.seek(0)
    with Command('grep', '[bd]').pipe_in(tmp) as test_cmd:
        lines = [line for line in test_cmd]
    assert(lines == [b'b', b'd'])
    assert(not test_cmd.lines)
    assert(test_cmd.rc == 0)

    print(':: all tests passed ::')

if __name__ == '__main__':
    test()
