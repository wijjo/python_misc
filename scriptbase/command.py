# Copyright 2016-17 Steven Cooper
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

r"""
Wrap the standard Python subprocess module to simplify common usage patterns.

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

import sys
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager

from . import utility
from . import shell
from . import console


def _dry_run_print(message):
    sys.stdout.write('>>> %s%s' % (message, os.linesep))


class Command(object):  #pylint: disable=too-many-instance-attributes
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
        """Exception for using a Command object outside of a "with" block."""

        def __init__(self):
            """Construct with canned string."""
            RuntimeError.__init__(
                self,
                'Illegal attempt to use a Command without a "with" block.')

    class AlreadyRunning(RuntimeError):
        """Exception for setting options on a running Command object."""

        def __init__(self):
            """Construct with canned string."""
            RuntimeError.__init__(
                self,
                'Illegal attempt to set Command options after it is running.')

    def __init__(self, *args):
        """Construct with variable length command line argument list."""
        self.args = args
        self.process = None
        self.done = False
        self.output_lines = []
        self.capture_on_exit = True
        self.input_source = None
        self.dryrun = False
        self.in_with_block = False
        self.buffer_size = 1
        self.return_code = None

    def options(self,
                bufsize=None,
                capture_on_exit=None,
                input_source=None,
                dryrun=None,
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
            self.buffer_size = bufsize
        if capture_on_exit is not None:
            self.capture_on_exit = capture_on_exit
        if input_source is not None:
            self.input_source = input_source
            if not hasattr(self.input_source, 'fileno'):
                pass
        if dryrun is not None:
            self.dryrun = dryrun
        return self

    def __enter__(self):
        """Open sub-process at the start of a with block."""
        self.in_with_block = True
        if not self.dryrun:
            self.process = subprocess.Popen(
                self.args,
                bufsize=self.buffer_size,
                stdin=self.input_source,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
        else:
            _dry_run_print(shell.quote_arguments(*self.args))
        if self.input_source and hasattr(self.input_source, 'fileno'):
            self.input_source.close()
        return self

    def __exit__(self, exit_type, exit_value, exit_traceback):
        """Close sub-process and capture results at the end of a with block."""
        if self.process is not None:
            if self.capture_on_exit:
                self.output_lines.extend([line for line in self.__iter__()])
            self.return_code = self.process.wait()

    def _check_in_with_block(self):
        if not self.in_with_block:
            raise Command.NotInWithBlock()

    def _check_not_running(self):
        if self.process is not None:
            raise Command.AlreadyRunning()

    def __iter__(self):
        """Iteration to run command and yield one output line at a time."""
        if not self.dryrun:
            self._check_in_with_block()
            self.capture_on_exit = False
            # Work around a Python 2 readline issue (https://bugs.python.org/issue3907).
            if not self.process.stdout.closed:
                with self.process.stdout:
                    for line in iter(self.process.stdout.readline, b''):
                        yield line.decode('utf8').rstrip()

    def run(self):
        """Run the command with output going to the console (stdout)."""
        self._check_in_with_block()
        for line in self.__iter__():
            sys.stdout.write('%s' % line)
            sys.stdout.write(os.linesep)

    def read_lines(self):
        """Run the command and return a list of output lines."""
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
        elif utility.is_string(input_obj):
            input_source = self._input_source_from_strings(False, input_obj)
        elif utility.is_iterable(input_obj):
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
        return Command(*args).pipe_in(self.process.stdout)

    @classmethod
    def _input_source_from_command(cls, command_obj):
        command_obj._check_in_with_block()  #pylint: disable=protected-access
        return command_obj.process.stdout

    @classmethod
    def _input_source_from_strings(cls, add_line_separators, *input_strs):
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


def _run_function(tag, checker, command_args, func, abort, *args, **kwargs):
    def _arg_string():
        sargs = str(args)
        if sargs[-2] == ',':
            sargs = '%s)' % sargs[:-2]
        if kwargs:
            skwargs = ' %s' % str(kwargs)
        else:
            skwargs = ''
        return '%s%s%s' % (tag, sargs, skwargs)
    if command_args.verbose:
        console.display_messages(_arg_string(), tag='TRACE')
    elif command_args.pause:
        sys.stdout.write('COMMAND: %s%s[Press Enter to continue] ' % (_arg_string(), os.linesep))
        sys.stdin.readline()
    ret = -1
    try:
        ret = func(*args, **kwargs)
        if checker is not None:
            errmsg = checker(ret, *args, **kwargs)
            if errmsg is not None:
                if abort:
                    console.abort(errmsg, _arg_string())
                else:
                    console.error(errmsg, _arg_string())
    except Exception as exc:    #pylint: disable=broad-except
        if abort:
            console.abort(exc, _arg_string())
        else:
            console.error(exc, _arg_string())
    return ret


class RunnerCommandArguments(utility.DictObject):
    """Command argument dictionary with attribute access."""

    pass


class Runner(object):
    """
    Command runner.

    Runner objects are passed by the "cli" module to all call-back functions,
    but can also be used independently for the command execution and or
    template expansion functionality.
    """

    class VarNamespace(utility.DictObject):
        """Variable namespace is a dictionary with attribute access."""

        pass

    def __init__(self,      #pylint: disable=too-many-arguments
                 command_args,
                 program_name=None,
                 program_directory=None,
                 expand_with_format=False,
                 var=None):
        """
        Construct runner.

        Positional arguments:
            1) sequence providing command line arguments

        Keyword arguments:
            program_name        program name override
            program_directory   program directory override
            expand_with_format  expand() uses format() instead of '%' if True
            var                 symbol dictionary for string expansion
        """
        self.arg = command_args
        self.program_name = program_name
        self.program_directory = program_directory
        self.expand_with_format = expand_with_format
        # Default program name and directory are based on the command line arguments.
        if not self.program_name:
            self.program_name = os.path.basename(sys.argv[0])
        if not self.program_directory:
            self.program_directory = os.path.dirname(sys.argv[0])
        # Application-specific variables are accessible through the "var" namespace.
        var_dict = {} if var is None else var
        self.var = Runner.VarNamespace(
            program_name=self.program_name,
            program_directory=self.program_directory,
            **var_dict)

    def shell(self, cmdline, abort=True):
        """Run a shell command line."""
        def _checker(retcode, cmdline):
            if retcode != 0:
                return 'Shell command failed with return code %d: %s' % (retcode, cmdline)
        cmdlinex = self.expand(cmdline)
        if self.arg.dryrun:
            _dry_run_print(cmdlinex)
            return 0
        return _run_function('shell', _checker, self.arg, os.system, abort, cmdlinex)

    def chdir(self, directory):
        """Change working directory with path expansion."""
        directory = self.expand(directory)
        if self.arg.dryrun:
            _dry_run_print('cd "%s"' % directory)
        else:
            _run_function('chdir', None, self.arg, os.chdir, True, directory)

    @contextmanager
    def chdir_context(self, directory):
        """Change and restore working directory in a "with" block."""
        save_directory = os.getcwd()
        self.chdir(directory)
        yield
        self.chdir(save_directory)

    def check_directory(self, path, exists):
        """Validate a directory with path expansion."""
        pathx = self.expand(path)
        if self.arg.dryrun:
            _dry_run_print('test -d "%s" || exit 1' % pathx)
        else:
            def _checker(actual_exists, path):
                if exists and not actual_exists:
                    return 'Directory "%s" does not exist' % path
                if not exists and actual_exists:
                    return 'Directory "%s" already exists' % path
            _run_function('check_directory', _checker, self.arg, os.path.exists, True, pathx)

    def command(self, *args):
        """
        Create a Command for use in a "with" block.

        Obeys the dryrun option, if set.

        See the Command class for more information.
        """
        return Command(*args).options(dryrun=self.arg.dryrun)


    def batch(self):
        """
        Create a Batch object for executing multiple commands.

        Obeys "dryrun" and "echo" options, if set.

        See the Batch class for more information.
        """
        return Batch(echo=getattr(self.arg, 'echo', False),
                     dryrun=getattr(self.arg, 'dryrun', False))


    def expand(self, str_in, expand_user=False, expand_env=False):
        """
        Expand string or path using internal symbols.

        If expand_user is True replace '~' with the user HOME. (default=False)

        if expand_env is True expand environment variables. (default=False)

        Return the expanded string.
        """
        str_out = str_in
        if str_out:
            try:
                if expand_env:
                    str_out = os.path.expandvars(str_out)
                if expand_user:
                    str_out = os.path.expanduser(str_out)
                if self.expand_with_format:
                    str_out = str_out.format(self.var)
                else:
                    str_out = str_out % self.var
            except ValueError as exc:
                console.abort(exc, str_in)
        return str_out


class BatchError(Exception):
    """Exception for batch errors prior to execution."""

    pass


class BatchFailure(Exception):
    """Exception for batch errors during execution."""

    def __init__(self, command, return_code):
        """Constructor adds a hard-coded string and saves the command and return code."""
        Exception.__init__(self, 'Command batch failed')
        self.command = command
        self.return_code = return_code


class Batch(object):
    """Build and execute a batch of shell commands (blocking)."""

    def __init__(self, echo=False, dryrun=False):
        """Batch constructor initializes an empty batch."""
        self.echo = echo
        self.dryrun = dryrun
        self.quoted_command_args_batch = []
        self.index = 0
        self.error_deletion_paths = []

    def add_command(self, *command_args):
        """Add a command specified as separate arguments to the batch."""
        self.quoted_command_args_batch.insert(self.index, self._prepare_arg_strings(command_args))
        self.index += 1

    def add_args(self, *args):
        """Add command arguments to the current command."""
        self._current_command().extend(self._prepare_arg_strings(args))

    def add_operator(self, operator):
        """Add an operator argument to the current command."""
        self._current_command().append(operator)

    def rewind(self, index=0):
        """Rewind the current command index."""
        if index < 0 or index >= len(self.quoted_command_args_batch):
            raise BatchError('Bad rewind index: %d' % index)
        self.index = index

    def add_error_deletion_path(self, path):
        """Add a path to clean up when an error occurs."""
        self.error_deletion_paths.append(path)

    def run(self):
        """Run the batch."""
        for quoted_command_args in self.quoted_command_args_batch:
            command_string = ' '.join(quoted_command_args)
            if self.dryrun:
                _dry_run_print(command_string)
            elif self.echo:
                console.info(command_string)
            if not self.dryrun:
                return_code = os.system(command_string)
                if return_code != 0:
                    self.handle_failure_cleanup()
                    raise BatchFailure(command_string, return_code)

    def handle_failure_cleanup(self):
        """
        Override this for custom cleanup needed when the batch failed.

        Make sure to call this base implementation if it is overridden.
        """
        for path in self.error_deletion_paths:
            if os.path.exists(path):
                try:
                    if os.path.isdir(path):
                        console.info('Delete partial directory: %s' % path)
                        shutil.rmtree(path)
                    else:
                        console.info('Delete partial file: %s' % path)
                        os.remove(path)
                except (IOError, OSError) as exc:
                    console.error('Unable to remove partial output path: %s' % path, exc)

    def _current_command(self):
        index = self.index - 1
        if index < 0 or index >= len(self.quoted_command_args_batch):
            raise(BatchError('No command exists at batch index: %d' % index))
        return self.quoted_command_args_batch[index]

    @classmethod
    def _prepare_arg_strings(cls, args):
        prepared_arg_strings = []
        for arg in args:
            if arg is not None:
                if isinstance(arg, (list, tuple)):
                    # List and tuple items get converted to strings and concatenated.
                    arg_string = ''.join([str(sub_arg) for sub_arg in arg])
                else:
                    # Everything else gets converted to a string.
                    arg_string = str(arg)
                # Quote the argument as needed for the shell to properly handle it.
                prepared_arg_strings.append(shell.quote_argument(arg_string))
        return prepared_arg_strings
