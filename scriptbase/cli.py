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

"""
CLI Module.

Introduction
------------
This module wraps argparse to make it easier to define a command line
interface, a.k.a. CLI, that supports multi-level commands, options, and help.
It adapts argparse's procedural interface with a declarative wrapper theat
brings the CLI metadata closer to the implementation.

Decorators declare the main program, along with the individual commands and
sub-commands. Once the implementation functions are declared using the
decorators a single call to cli.main() runs the program after parsing the
command line options.

Note that the decorated functions can have any name, but if no "name" attribute
is specified the function names are used as the command names. The optional
"name" attribute is particularly useful when command names are invalid Python
symbols, e.g. when using a digit as the first charactor of the command name.

Sample
------
There is no user guide yet. The sample program below will hopefully help to get
you started. More advanced features may be discovered in doc strings, comments,
and the code itself. Better documentation is planned.

Sample code::

  from scriptbase import cli

  TIMEOUT = 60

  @cli.Main('Access remote web pages', support_dryrun=True, args=[
      cli.Integer('timeout', 'time-out in seconds', '--timeout', default=TIMEOUT)])
  def main(runner):
      global TIMEOUT
      TIMEOUT = runner.arg.timeout

  @cli.Command(description='download page', args=[
      cli.String('url', 'URL of page to download'),
      cli.Boolean('pdf', 'convert to a PDF', '--pdf')])
  def download(runner):
      if runner.arg.dryrun:
          print('Download(dryrun): %s' % runner.arg.url)
      elif runner.arg.pdf:
          print('Download(PDF): %s' % runner.arg.url)
      else:
          print('Download(HTML): %s' % runner.arg.url)

  @cli.Command(description='display various statistics', args=[
      cli.String('url', 'URL of page to download')])
  def show(runner):
      print('show')

  @cli.Command(description='display route to host', parent=show)
  def route(runner):
      print('show_route(%s)' % runner.arg.url)

  @cli.Command(description='display latency to host', parent=show)
  def latency(runner):
      print('show_latency(%s)' % runner.arg.url)

  if __name__ == '__main__':
      cli.main()

The sample is runnable, e.g. save it as sample.py and make sure scriptbase
is in your PYTHONPATH.

Compatibility
-------------
Python 2.7 or 3.5 and later.
"""

# Future features:
# - YAML configuration
# - Save option sets for scopes, e.g. exclude object files in build environment
#   from sync and archive command, or run using sudo in /etc.
# - Wrap existing external commands with DSL. E.g. all saving default options
#   for ag/ack searches in various scopes (locations).
# - Generate new cli-based scripts.
# - Automatically load sub-commands from a directory.
# - Add/modify/delete sub-commands dynamically.
# - Dynamically build and modify @Command specification for sub-commands.

import sys
import os
import copy
import inspect
import traceback

from . import command
from . import utility
from . import console
from .configuration import Config

try:
    import argparse
except ImportError:
    from .python import argparse


class ArgumentSpec(object):
    """ArgumentSpec class is used to declare typed arguments and options."""

    def __init__(self, dest, help_text, *args, **kwargs):
        """Constructor mirrors ArgumentParser.add_argument."""
        self.args = args
        self.kwargs = kwargs
        self.kwargs['dest'] = dest
        self.kwargs['help'] = help_text
        if 'default' in self.kwargs and 'help' in self.kwargs:
            self.kwargs['help'] += ' (default=%s)' % str(self.kwargs['default'])

    def __str__(self):
        """String conversion used for dumping contents."""
        return 'ArgumentSpec:%s(%s)' % (self.kwargs['dest'], self.__class__.__name__)


class String(ArgumentSpec):
    """String type ArgumentSpec subclass."""

    def __init__(self, dest, help_text, *args, **kwargs):
        """Constructor mirrors ArgumentParser.add_argument for a string argument."""
        kwargs['action'] = 'store'
        ArgumentSpec.__init__(self, dest, help_text, *args, **kwargs)


class Boolean(ArgumentSpec):
    """Boolean type ArgumentSpec subclass."""

    def __init__(self, dest, help_text, *args, **kwargs):
        """Constructor mirrors ArgumentParser.add_argument for a boolean argument."""
        kwargs['action'] = 'store_true'
        ArgumentSpec.__init__(self, dest, help_text, *args, **kwargs)


class Integer(ArgumentSpec):
    """Integer type ArgumentSpec subclass."""

    def __init__(self, dest, help_text, *args, **kwargs):
        """Constructor mirrors ArgumentParser.add_argument for an integer argument."""
        kwargs['action'] = 'store'
        kwargs['type'] = int
        ArgumentSpec.__init__(self, dest, help_text, *args, **kwargs)


class Verb(object):     #pylint: disable=too-many-instance-attributes
    """
    Verb class defines commands and sub-commands.

    Specifically defines options, arguments, and implementation functions.
    """

    root = None
    parser = None
    verbs_by_function_ref = {}

    class Help(object):
        """Help provider callable class."""

        def __init__(self, parsers_by_name):
            """Need to look up a parser by name to print the help."""
            self.parsers_by_name = parsers_by_name

        def __call__(self, runner):
            """Function call to print help."""
            names = runner.arg.verbs
            if not names:
                names = ['_']
            i = 0
            for verbname in names:
                if i > 0:
                    sys.stdout.write('\n')
                i += 1
                if verbname in self.parsers_by_name:
                    self.parsers_by_name[verbname].print_help()
                else:
                    sys.stderr.write('* "%s" is not a supported verb. *\n' % verbname)

    def __init__(self,      #pylint: disable=too-many-arguments
                 name=None,
                 description=None,
                 is_root=False,
                 parent=None,
                 function=None,
                 args=None,
                 aliases=None):
        """
        Verb constructor.

        Keyword arguments:
          name         name used to invoke verb from a CLI command
          description  text description
          is_root      used internally to identify the root verb
          parent       parent Verb object or @Command function
          function     implementation function reference
          args         argument/option specifications list
          aliases      alias list, i.e. alternative names, for this verb
        """
        # Set the root if missing, whether or not the app provides one explicitly.
        if not Verb.root:
            Verb.root = self if is_root else Verb(is_root=True)
        self.name = name
        if description is None:
            self.description = '(no description provided)'
        else:
            self.description = description
        self.is_root = is_root
        self.function = function
        self.arg_specs = []
        self.child_verbs = []
        self.dirty = True
        self.aliases = aliases if aliases else []
        badargs = []
        if args:
            for arg_spec in args:
                if isinstance(arg_spec, Verb):
                    self.child_verbs.append(arg_spec)
                elif isinstance(arg_spec, ArgumentSpec):
                    self.arg_specs.append(arg_spec)
                else:
                    badargs.append(arg_spec)
        for badarg in badargs:
            sys.stderr.write('* CLI: ignoring bad argument specification: %s*\n' % repr(badarg))
        if not self.is_root:
            self._add_to_parent(parent)

    def _add_to_parent(self, parent):
        if parent is None:
            Verb.root.add_verb(self)
        elif isinstance(parent, Verb):
            parent.add_verb(self)
        elif inspect.isfunction(parent) and parent in Verb.verbs_by_function_ref:
            Verb.verbs_by_function_ref[parent].add_verb(self)
        else:
            console.abort('Parent is not a known command function.')

    def configure_parser(self, parser):
        """Initialize the ArgumentParser based on the specification objects."""
        self._update()
        for arg_spec in self.arg_specs:
            parser.add_argument(*arg_spec.args, **arg_spec.kwargs)
        if self.function:
            parser.set_defaults(func=self.function)
        if self.get_verbs():
            help_text = '"help SUBCOMMAND" for details'
            # For some reason Python 3 needs dest set in order to get the
            # correct function that was saved by set_defaults(func=...).  Note
            # that nested sub-commands with this use of set_defaults() is
            # broken in Python 3 versions before 3.5.
            subparsers = parser.add_subparsers(dest='subcommand', help=help_text)
            subparsers.required = True
            parsers_by_name = {'_': parser}
            for verb in self.get_verbs():
                for verb_name in [verb.name] + list(verb.aliases):
                    subparser = subparsers.add_parser(verb_name, description=verb.description)
                    parsers_by_name[verb_name] = subparser
                    verb.configure_parser(subparser)
            if self.is_root:
                helpparser = subparsers.add_parser(
                    'help',
                    description='display command or verb help')
                helpparser.add_argument('verbs', help='optional verb list', nargs='*')
                helpparser.set_defaults(func=Verb.Help(parsers_by_name))

    def set_function(self, function):
        """Set the verb's call-back implementation function."""
        Verb.verbs_by_function_ref[function] = self
        # Fall back to using the function name if no explicit name was given.
        if not self.name:
            self.name = function.__name__
        self.function = function
        # Returning the function is a convenience for decorator implementations.
        return self.function

    def add_verb(self, verb):
        """Add child verb."""
        self.child_verbs.append(verb)
        self.dirty = True

    def get_verbs(self):
        """Return child verbs after performing an update to sort them."""
        self._update()
        return self.child_verbs

    def __str__(self):
        """String conversion used for dumping contents."""
        self._update()
        sargs = '(%s)' % ', '.join([str(a) for a in self.arg_specs])
        sverb_list = [str(verb).replace('\n', '\n      ') for verb in self.child_verbs]
        sverbs = '\n'.join(sverb_list)
        return '''Verb:%s%s:
   description: %s
   function: %s
   verbs:
      %s''' % (self.name, sargs, self.description, self.function, sverbs)

    def _update(self):
        if self.dirty:
            self.child_verbs = sorted(self.child_verbs, key=lambda x: x.name)
            self.dirty = False

    class CustomArgumentParser(argparse.ArgumentParser):
        """Inherit from ArgumentParser for custom error handling."""

        def error(self, message):
            """Custom error handler."""
            if message:
                console.error(message)
            self.print_help(sys.stderr)
            sys.stderr.write(os.linesep)
            self.exit(255)

    @classmethod
    def get_parser(cls, description, add_arg_specs):
        """Provide an argument/option parser."""
        # Support tests with multiple command lines run against one specification.
        if cls.parser:
            return cls.parser
        cls.root.description = description
        if add_arg_specs:
            cls.root.arg_specs.extend(add_arg_specs)
        cls.parser = Verb.CustomArgumentParser(
            description='  %s' % '\n  '.join(cls._description_lines()),
            formatter_class=argparse.RawDescriptionHelpFormatter)
        cls.root.configure_parser(cls.parser)
        return cls.parser

    @classmethod
    def _description_lines(cls):
        lines = ['%(prog)s [OPTION ...] SUBCOMMAND [SUBOPTION ...] [ARG ...]', '']
        prog = os.path.basename(sys.argv[0])
        verb_usage_pairs = [
            ('%s help' % prog, 'Display general help.'),
            ('%s help SUBCOMMAND' % prog, 'Display sub-command help.'),
        ] + [('%s %s ...' % (prog, verb.name), verb.description) for verb in cls.root.get_verbs()]
        verb_usage_pairs = sorted(verb_usage_pairs, key=lambda x: x[0])
        width = 0
        for verb_usage_pair in verb_usage_pairs:
            if len(verb_usage_pair[0]) > width:
                width = len(verb_usage_pair[0])
        fmt = '%%-%ds  %%s' % width
        lines.extend([fmt % (p[0], p[1]) for p in verb_usage_pairs])
        return lines


class Command(Verb):
    """
    Function decorator class used to declare a command or sub-command.

    Sub-commands have a non-None parent.

    Remember the verb implementation function, and its options and arguments.

    Keyword arguments (all are optional):

      name         primary command name the user has to type
                   (defaults to the function name)
      description  one line help text describing the command
      parent       sub-commands need a reference to the parent command function
      args         argument and option type list (sequence), e.g.
                   [cli.String(...), cli.Boolean(...), cli.Integer(...), ...]
      aliases      list of alternative names (sequence)
    """

    def __init__(self,      #pylint: disable=too-many-arguments
                 name=None,
                 description=None,
                 parent=None,
                 args=None,
                 aliases=None
                ):
        """Decorator constructor to capture command specification."""
        Verb.__init__(self,
                      name=name,
                      description=description,
                      args=args,
                      parent=parent,
                      aliases=aliases)

    def __call__(self, function):
        """Decorator call to capture implementation function."""
        return self.set_function(function)


class Main(object):     #pylint: disable=too-many-instance-attributes
    """
    Main function decorator class.

    Used to declare the @Main function that declares the top level CLI
    arguments and options, specifies other options that affect how the CLI is
    built, and performs other optional setup operations.

    Note that support_discovery defaults to False, so that commands are not
    discoverable without @Main being pre-loaded. This assures that command
    directory names follow any program_name override in the @Main decorator.
    """

    instance = None

    def __init__(self,      #pylint: disable=too-many-arguments
                 description=None,
                 args=None,
                 support_verbose=False,
                 support_dryrun=False,
                 support_pause=False,
                 support_discovery=False,
                 support_plugins=False,
                 runner_type=command.Runner,
                 program_name=None,
                 program_directory=None,
                 configuration=None):
        """Decorator constructor for Main specification."""
        self.description = description
        self.arg_specs = args if args else []
        self.support_verbose = support_verbose
        self.support_dryrun = support_dryrun
        self.support_pause = support_pause
        self.runner_type = runner_type
        self.support_discovery = support_discovery
        self.support_plugins = support_plugins
        self.program_name = program_name
        self.program_directory = program_directory
        self.function = None
        self.configuration = configuration

    def __call__(self, function):
        """Decorator call to capture implementation function."""
        if Main.instance:
            console.abort('Only one @cli.Main() is allowed.')
        self.function = function
        Main.instance = self

#===============================================================================
# Utility functions for main()
#===============================================================================

def _get_arg_specs():
    arg_specs = copy.copy(list(Main.instance.arg_specs))
    if Main.instance.support_verbose:
        arg_specs.append(Boolean('verbose', "display verbose messages", '-v', '--verbose'))
    if Main.instance.support_dryrun:
        arg_specs.append(Boolean('dryrun', "display commands without executing them", '--dry-run'))
    if Main.instance.support_pause:
        arg_specs.append(Boolean('pause', "pause before executing each command", '--pause'))
    return arg_specs

def _preparse_args(args, arg_specs):
    # Only doing the preparsing exercise to set the verbose flag early.
    preparser = argparse.ArgumentParser()
    for arg_spec in arg_specs:
        preparser.add_argument(*arg_spec.args, **arg_spec.kwargs)
    tmp_args, _ = preparser.parse_known_args(args=args)
    if Main.instance.support_verbose:
        console.set_verbose(tmp_args.verbose)

def _parse_args(args, arg_specs):
    parser = Verb.get_parser(Main.instance.description, arg_specs)
    return parser.parse_args(args=args)

# Load a discovered CLI module by importing the file rather than exec-ing a
# string so that other symbols in the file, e.g. utility functions, are
# available when registered @Command functions get invoked.
def _load_cli_module(path):
    console.verbose_info('CLI import: %s' % path)
    try:
        utility.import_module_path(path)
    except Exception as exc:
        console.error('Exception while executing CLI source file: %s' % path, exc)
        raise

def _discover_commands(command_dirs):
    # Search the <name>.cli directory. Execute *.py from the top level
    # directory and __cli__.py from subdirectories. @Main and @Command
    # decorators will be registered.
    if not Main.instance.support_discovery:
        return
    for command_dir in command_dirs:
        if os.path.isdir(command_dir):
            console.verbose_info('Discovering commands in directory: %s' % command_dir)
            # Load *.py from the top level directory.
            paths = sorted([os.path.join(command_dir, name) for name in os.listdir(command_dir)])
            for path in paths:
                if os.path.isfile(path) and path.endswith('.py'):
                    _load_cli_module(path)
            # Load __cli__.py from immediate subdirectories.
            for path in paths:
                cli_path = os.path.join(path, '__cli__.py')
                if os.path.isfile(cli_path):
                    _load_cli_module(cli_path)
    if not Main.instance:
        console.abort('No @Main() was registered.')
    if not Verb.root:
        console.abort("No @Command's were registered.")

def _discover_plugins(program_name):
    if Main.instance.support_plugins:
        plugins = utility.DictObject()
        symbols = dict(program_name=program_name)
        dir_paths = [
            os.path.realpath(os.path.expanduser(os.path.expandvars(dir_path % symbols)))
            for dir_path in [
                os.path.join('~', '.%(program_name)s.d'),
                '.%(program_name)s.d)',
                os.path.join('%(program_directory)s', '%(program_name)s.d'),
            ]
        ]
        for dir_path in dir_paths:
            if os.path.isdir(dir_path):
                imported_modules = utility.import_modules_from_directory(dir_path)
                if imported_modules:
                    plugins.update(**imported_modules)
        return plugins

def _prepare_runner(program_name, program_directory, command_args, plugins):
    # The runner gets passed to @Main and @Command implementation functions.
    runner = Main.instance.runner_type(command_args,
                                       program_name=program_name,
                                       program_directory=program_directory)
    # Add the runner.cfg configuration namespace as needed.
    if Main.instance.configuration:
        _prepare_configuration(runner)
    # Add the runner.mod plugin namespace as needed.
    if plugins:
        runner.mod = plugins
    return runner

def _prepare_configuration(runner):
    # Expand symbols in ConfigSpec text properties.
    for cfg_spec in Main.instance.configuration:
        cfg_spec.name = runner.expand(cfg_spec.name)
        cfg_spec.desc = runner.expand(cfg_spec.desc)
    # Generate the file name based on the program name as .<program-name>rc.
    # Allow customization of the config file name?
    runner.cfg = Config(runner.expand('.%(program_name)src'), *Main.instance.configuration)
    # Load the configuration.
    runner.cfg.load_for_paths('~', '.')

def _invoke(runner, name, func):
    try:
        func(runner)
    except KeyboardInterrupt:
        console.abort('%s interrupted by user.' % name)
    except command.BatchError as exc:
        console.abort(exc)
    except command.BatchFailure as exc:
        console.abort('%s command batch failed.' % name,
                      ['return code: %d' % exc.return_code, 'command: %s' % exc.command])
    except Exception:    #pylint: disable=broad-except
        console.error('%s traceback (most recent call last)' % name)
        (exc_type, exc_value, exc_tb) = sys.exc_info()
        for line in traceback.format_list(traceback.extract_tb(exc_tb)[1:]):
            console.error(line.rstrip())
        exc_lines = [line.rstrip() for line in traceback.format_exception_only(exc_type, exc_value)]
        console.error(*exc_lines)
        sys.exit(255)


def main(program_name=None,
         program_directory=None,
         command_line=None):
    """
    Main function.

    Parse and validate the arguments and options, and then invoke the assigned
    command function.

    Returns any result provided by the command function, which should be a
    system exit code, i.e. 0 for success or non-zero for failure.
    """
    if command_line is None:
        command_line = sys.argv
    if not program_name:
        program_name = os.path.basename(command_line[0])
    if program_directory:
        sys.path.insert(0, program_directory)
        exec('import %s.__cli_main__' % program_name)   #pylint: disable=exec-used
    else:
        program_directory = os.path.dirname(command_line[0])

    # Basic argument specs for universal options, like verbose, dry-run, and pause.
    arg_specs = _get_arg_specs()

    # Pre-parse arguments so that discovery can be verbose if the option is set.
    _preparse_args(command_line[1:], arg_specs)

    # Discover commands from discoverable cli directories.
    # Look elsewhere, e.g. under home, /usr/share, etc.?
    command_dirs = [os.path.join(program_directory, 'plugins')]
    _discover_commands(command_dirs)

    # Use program overrides provided by the @Main decorator.
    if Main.instance.program_name:
        program_name = Main.instance.program_name
    if Main.instance.program_directory:
        program_directory = Main.instance.program_directory

    # Parse the full command line.
    command_args = _parse_args(command_line[1:], arg_specs)

    # Discover plugin modules, if supported and present.
    plugins = _discover_plugins(program_name)

    # Run the command by invoking the @Main() and the corresponding @Command() functions.
    runner = _prepare_runner(program_name, program_directory, command_args, plugins)

    # Invoke @Main function (frequently does little or nothing).
    _invoke(runner, '@Main', Main.instance.function)

    # Invoke @Command function and return the exit code.
    if hasattr(runner.arg, 'func'):
        command_name = '@Command[%s]' % command_args.subcommand
        return _invoke(runner, command_name, runner.arg.func)
