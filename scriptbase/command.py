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


class ExternalCommandError(Exception):
    """Exception for command failure in ExternalCommandHandler sub-classes."""
    #pylint: disable=unnecessary-pass
    pass


class ExternalCommandHandler(object):
    """
    Base class for command runners.

    Provides surrounding logic for running external commands. Handles options,
    including dry-run, verbose, and pause.

    Used by the Command, Runner, and Batch classes in this module. Not
    generally useful externally.
    """

    def __init__(self, **options):
        """
        External command handler constructor.

        Noted that all valid options must be initialized here so that they can
        be validated by set_options().
        """
        self.options = options

    def set_options(self, **options):
        """Apply option changes."""
        bad_keys = [key for key in sorted(options.keys()) if key not in self.options]
        if bad_keys:
            console.warning('Bad set option key(s): %s' % ' '.join(bad_keys))
        self.options.update(options)

    def get_option(self, key):
        """Get option value."""
        if key not in self.options:
            console.warning('Bad get option key: %s' % key)
            return None
        return self.options[key]

    def run_command(self, *args, **options):
        """
        Use call-backs to run a command.

        Positional arguments provide command parts.

        Keyword arguments are temporary option settings.
        """
        def _get_option(key):
            if key in options:
                return options[key]
            return self.options.get(key, False)
        def _command_text():
            return self.on_get_command_text(self, *args)
        if _get_option('dry_run'):
            sys.stdout.write('>>> ')
            sys.stdout.write(_command_text())
            sys.stdout.write(os.linesep)
            return 0
        if _get_option('verbose'):
            console.display_messages(_command_text(), tag='TRACE')
        elif _get_option('pause'):
            sys.stdout.write('COMMAND: ')
            sys.stdout.write(_command_text())
            sys.stdout.write(os.linesep)
            sys.stdout.write('[Press Enter to continue] ')
            sys.stdin.readline()
        try:
            return self.on_invoke_command(*args)
        except ExternalCommandError as exc:
            self.error('External command error:', [_command_text(), exc])

    def error(self, *args, **kwargs):
        """Display error and optionally abort."""
        error_function = console.abort if self.get_option('abort') else console.error
        error_function(*args, **kwargs)

    def on_invoke_command(self, *args):
        """Must be implemented by a sub-class."""
        raise NotImplementedError

    @classmethod
    def on_get_command_text(cls, *args):
        """Override in sub-class for custom command text."""
        return ' '.join([str(arg) for arg in args])


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

    #=== Command nested classes.

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

    class _Handler(ExternalCommandHandler):

        def __init__(self, args):
            ExternalCommandHandler.__init__(
                self,
                bufsize=1,
                input_source=None,
                capture_on_exit=True,
                dry_run=False,
                verbose=False,
                pause=False,
            )
            self.args = args
            self.process = None

        def on_invoke_command(self):        #pylint: disable=arguments-differ
            """
            Customize the command invocation.

            The arguments were supplied to the constructor, so no args or
            kwargs are expected.
            """
            input_stream = self.get_option('input_source')
            self.process = subprocess.Popen(
                self.args,
                bufsize=self.get_option('bufsize'),
                stdin=input_stream,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            if input_stream and hasattr(input_stream, 'fileno'):
                input_stream.close()

        def on_get_command_text(self):      #pylint: disable=arguments-differ
            """
            Customize the command display text.

            The arguments were supplied to the constructor, so no args or
            kwargs are expected.
            """
            return shell.quote_arguments(*self.args)

    #=== Command methods

    def __init__(self, *args):
        """Construct with variable length command line argument list."""
        self.process = None
        self.done = False
        self.output_lines = []
        self.in_with_block = False
        self.return_code = None
        self._handler = Command._Handler(args)

    def options(self, **kwargs):
        """
        Set options immediately after constructions.

        Returns self so that a chained call provides the "with" statement object.

        bufsize          buffer size, see subprocess.Popen() for more information (default=1)
        input_source     string, stream, or Command to pipe to standard input (default=None)
        dry_run          don't execute if True
        verbose          display verbose messages if True
        pause            pause before executing the command if True
        capture_on_exit  captures remaining output to "output_lines" member if True (default=True)
        """
        self._check_not_running()
        self._handler.set_options(**kwargs)
        return self

    def __enter__(self):
        """Open sub-process at the start of a with block."""
        self.in_with_block = True
        self._handler.run_command()
        self.process = self._handler.process
        return self

    def __exit__(self, exit_type, exit_value, exit_traceback):
        """Close sub-process and capture results at the end of a with block."""
        if self.process is not None:
            if self._handler.get_option('capture_on_exit'):
                self.output_lines.extend([line for line in self.__iter__()])
            self.return_code = self.process.wait()

    def _check_in_with_block(self):
        if not self.in_with_block:
            raise Command.NotInWithBlock()

    def _check_not_running(self):
        if self.process is not None:
            raise Command.AlreadyRunning()

    def __iter__(self):
        """Iteration yields an output line at a time."""
        if not self._handler.get_option('dry_run'):
            self._check_in_with_block()
            self._handler.set_options(capture_on_exit=False)
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


class CommandContext(utility.DictObject):
    """Local data with console methods enhanced with automatic formatting."""

    def info(self, *msgs, **symbols):
        """Display informational message(s)."""
        msgs2 = [self.format(msg, **symbols) for msg in msgs]
        console.info(*msgs2)

    def verbose_info(self, *msgs, **symbols):
        """Display informational message(s) if verbose output is enabled."""
        msgs2 = [self.format(msg, **symbols) for msg in msgs]
        console.verbose_info(*msgs2)

    def debug(self, *msgs, **symbols):
        """Display debug message(s)."""
        msgs2 = [self.format(msg, **symbols) for msg in msgs]
        console.debug(*msgs2)

    def warning(self, *msgs, **symbols):
        """Display warning message(s)."""
        msgs2 = [self.format(msg, **symbols) for msg in msgs]
        console.warning(*msgs2)

    def error(self, *msgs, **symbols):
        """Display error message(s)."""
        msgs2 = [self.format(msg, **symbols) for msg in msgs]
        console.error(*msgs2)

    def abort(self, *msgs, **symbols):
        """Display error message(s) and exit with return code 255."""
        msgs2 = [self.format(msg, **symbols) for msg in msgs]
        console.abort(*msgs2)

    def header(self, *msgs, **symbols):
        """Display header message(s)."""
        msgs2 = [self.format(msg, **symbols) for msg in msgs]
        console.header(*msgs2)

    def pause(self, *msgs, **symbols):
        """Display message(s) and wait for user confirmation to continue."""
        msgs2 = [self.format(msg, **symbols) for msg in msgs]
        console.pause(*msgs2)


class Runner(object):
    """
    Command runner.

    Runner objects are passed by the "cli" module to all call-back functions,
    but can also be used independently for the command execution and or
    template expansion functionality.
    """

    #=== Runner nested classes.

    class VarNamespace(utility.DictObject):
        """Variable namespace is a dictionary with attribute access."""
        #pylint: disable=unnecessary-pass
        pass

    class CommandArguments(utility.DictObject):
        """Command argument dictionary with attribute access."""
        #pylint: disable=unnecessary-pass
        pass

    class _ShellCommandHandler(ExternalCommandHandler):

        def on_invoke_command(self, cmd_line):                      #pylint: disable=arguments-differ
            """Shell command invocation."""
            ret_code = os.system(cmd_line)
            if ret_code != 0:
                raise ExternalCommandError('Shell command failed with return code %d' % ret_code)
            return ret_code

        def on_get_command_text(self, cmd_line):                    #pylint: disable=arguments-differ
            """Shell command display text."""
            return cmd_line

    class _ChangeDirectoryCommandHandler(ExternalCommandHandler):

        def on_invoke_command(self, directory):                     #pylint: disable=arguments-differ
            """Change directory invocation."""
            try:
                os.chdir(directory)
            except (IOError, OSError) as exc:
                raise ExternalCommandError('Directory change error "%s"' % str(exc))

        def on_get_command_text(self, directory):                   #pylint: disable=arguments-differ
            """Change directory display text."""
            return 'cd %s' % shell.quote_argument(directory)

    class _CheckDirectoryCommandHandler(ExternalCommandHandler):

        def on_invoke_command(self, path, exists):                  #pylint: disable=arguments-differ
            """Check directory invocation."""
            actual_exists = os.path.exists(path)
            if exists and not actual_exists:
                return 'Directory "%s" does not exist' % path
            if not exists and actual_exists:
                return 'Directory "%s" already exists' % path

        def on_get_command_text(self, path, exists):                #pylint: disable=arguments-differ
            """Check directory display text."""
            return 'test -d %s %s exit 1' % (shell.quote_argument(path), '||' if exists else '&&')

    #=== Runner methods.

    def __init__(self,      #pylint: disable=too-many-arguments
                 command_args,
                 program_name=None,
                 program_directory=None,
                 var=None):
        """
        Construct runner.

        Positional arguments:
            1) sequence providing command line arguments

        Keyword arguments:
            program_name       program name override
            program_directory  program directory override
            var                symbol dictionary for string expansion
        """
        self.arg = command_args
        # Default program name and directory are based on the command line arguments.
        if not program_name:
            program_name = os.path.basename(sys.argv[0])
        if not program_directory:
            program_directory = os.path.dirname(sys.argv[0])
        # Application-specific variables are accessible through the "var" namespace.
        var_dict = {} if var is None else var
        self.var = Runner.VarNamespace(
            program_name=program_name,
            program_directory=program_directory,
            **var_dict)
        # Option dictionary provided to generated Command and Batch objects.
        self.options = dict(
            dry_run=getattr(self.arg, 'DRY_RUN', False),
            verbose=getattr(self.arg, 'VERBOSE', False),
            pause=getattr(self.arg, 'PAUSE', False),
        )
        # Command handlers for various external actions.
        self._handlers = utility.DictObject(
            shell_command=Runner._ShellCommandHandler(**self.options),
            change_directory=Runner._ChangeDirectoryCommandHandler(**self.options),
            check_directory=Runner._CheckDirectoryCommandHandler(**self.options),
        )
        # Stack of context data for message formatting, etc..
        self._context_stack = []

    def shell(self, cmd_line, abort=True):
        """Run a shell command from a single string or split arguments."""
        if utility.is_non_string_sequence(cmd_line):
            cmd_line_expanded = self.expand(shell.quote_arguments(*cmd_line))
        else:
            cmd_line_expanded = self.expand(cmd_line)
        return self._handlers.shell_command.run_command(cmd_line_expanded, abort=abort)

    def chdir(self, directory):
        """Change working directory with path expansion."""
        directory_expanded = self.expand(directory)
        self._handlers.change_directory.run_command(directory_expanded)

    @contextmanager
    def chdir_context(self, directory):
        """Change and restore working directory in a "with" block."""
        save_directory = os.getcwd()
        self.chdir(directory)
        yield
        self.chdir(save_directory)

    def check_directory(self, path, exists):
        """Validate a directory with path expansion."""
        return self._handlers.check_directory.run_command(self.expand(path), exists)

    def command(self, *args):
        """
        Create a Command for use in a "with" block.

        Obeys the DRY_RUN option, if set.

        See the Command class for more information.
        """
        return Command(*args).options(**self.options)

    def batch(self):
        """
        Create a Batch object for executing multiple commands.

        Obeys the "DRY_RUN" option, if set.

        See the Batch class for more information.
        """
        return Batch(**self.options)

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
                # Expand using both format() and '%' operator.
                str_out = str_out.format(**self.var) % self.var
            except (ValueError, KeyError) as exc:
                console.abort('Runner.expand() error.', [
                    '  input: %s' % str_in,
                    'symbols: %s' % str(self.var),
                    exc])
        return str_out

    @contextmanager
    def context(self, **kwargs):
        """
        Context manager for saving a state stack.

        Provides temporary scoped data for message formatting methods below.
        """
        ctx = CommandContext(self.var, **kwargs)
        self._context_stack.append(ctx)
        yield ctx
        self._context_stack.pop()


class Batch(object):
    """Build and execute a batch of shell commands (blocking)."""

    #=== Batch nested classes.

    class Error(Exception):
        """Exception for batch errors prior to execution."""
        #pylint: disable=unnecessary-pass
        pass

    class Failure(Exception):
        """Exception for batch errors during execution."""

        def __init__(self, command, return_code):
            """Constructor adds a hard-coded string and saves the command and return code."""
            Exception.__init__(self, 'Command batch failed')
            self.command = command
            self.return_code = return_code

    class _CommandHandler(ExternalCommandHandler):

        def __init__(self, **options):
            """Batch command handler constructor."""
            ExternalCommandHandler.__init__(self, **options)
            self.temporary_paths = []

        def on_invoke_command(self, cmd_line):  # pylint: disable=arguments-differ
            """Shell command invocation."""
            ret_code = os.system(cmd_line)
            if ret_code != 0:
                self.delete_temporary_files()
                raise Batch.Failure(cmd_line, ret_code)
            return ret_code

        def on_get_command_text(self, cmd_line):  # pylint: disable=arguments-differ
            """Batch command display text."""
            return cmd_line

        def add_temporary_path(self, path):
            """Add a path to clean up when an error occurs."""
            self.temporary_paths.append(path)

        def delete_temporary_files(self):
            """Delete intermediate files after a batch failure occurs."""
            for path in self.temporary_paths:
                if os.path.exists(path):
                    try:
                        if os.path.isdir(path):
                            console.info('Delete partial directory: %s' % path)
                            shutil.rmtree(path)
                        else:
                            console.info('Delete partial file: %s' % path)
                            os.remove(path)
                    except (IOError, OSError) as exc:
                        console.error(
                            'Unable to remove partial output path: %s' % path, exc)

    #=== Batch methods.

    def __init__(self, **options):
        """Batch constructor initializes an empty batch."""
        self.quoted_command_args_batch = []
        self.index = 0
        self.error_deletion_paths = []
        self._handler = Batch._CommandHandler(**options)

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
            raise Batch.Error('Bad rewind index: %d' % index)
        self.index = index

    def add_error_deletion_path(self, path):
        """Add a path to clean up when an error occurs."""
        self._handler.add_temporary_path(path)

    def run(self):
        """Run the batch."""
        for quoted_command_args in self.quoted_command_args_batch:
            command_string = ' '.join(quoted_command_args)
            self._handler.run_command(command_string)

    def handle_failure_cleanup(self):
        """
        Override this for custom cleanup needed when the batch failed.

        Make sure to call this base implementation if it is overridden.
        """
        self._handler.delete_temporary_files()

    def _current_command(self):
        index = self.index - 1
        if index < 0 or index >= len(self.quoted_command_args_batch):
            raise(Batch.Error('No command exists at batch index: %d' % index))
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
