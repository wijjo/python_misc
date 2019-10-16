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
Declarative layer for standard argparse module.

All needed functionality is accessible through the CLI namespace class. Nothing
else at the module level is considered public.

Dependencies are kept minimal and the few required import statements are placed
inline within the functions that require them.

Structured decorators provide a thin declarative veneer over the imperative
argparse API, both to make its usage more intuitive and to place it closer to
CLI-specific code. More flexibility and modularity is possible.

Users can leverage argparse knowledge and documentation, since most decorators
and related objects map pretty well to argparse entities.

This module serves a similar purpose to the older scriptbase.cli module.
However, it takes a much more minimalist and transparent approach.
"""

import os
import argparse
import re
from . import console
from . import utility


class _GlobalData:
    subparser_base_name = 'SUBCOMMAND'
    name_regex = re.compile(r'^\w+$')
    abort_exception = False


class _ConsoleContext(console.Context):
    """Overrides console.Context to tweak behavior, e.g. abort() exceptions."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_abort_exception(_GlobalData.abort_exception)


class _ArgumentBase(utility.DumpableObject):
    """
    Base class for argument and option declaration classes.

    Usage notes:

    Derived classes should be used to assure sane argument combinations.

    Avoids conflicts by renaming "help" and "type" to "help_text" and
    "data_type", and by making them required positional arguments.

    "data_type" should ultimately be provided by a derived class in this
    library, not the user.
    """
    def __init__(self, name, action, data_type, help_text,
                 metavar=None,
                 nargs=None,
                 const=None,
                 default=None,
                 choices=None,
                 required=None):
        # The add_arguments() positional arguments is only for option flags.
        # Even though the call can accept name as a positional argument, it
        # will always be provided through the 'dest' keyword.
        self.name = name
        self.action = action
        self.data_type = data_type
        self.help_text = help_text
        self.metavar = metavar
        self.nargs = nargs
        self.const = const
        self.default = default
        self.choices = choices
        self.required = required
        self.add_argument_args = []
        self.add_argument_kwargs = {}
        # Flags are populated while building the parser and walking through
        # arguments lists that might have (flags, argument) pairs.
        self.flags = None
        utility.DumpableObject.__init__(self)

    def initialize(self, flags):
        """Initialize option or argument."""
        # Basic sanity checks to catch positional argument swapping, etc..
        if not _CommandRegistry.is_valid_name(self.name):
            console.abort('Bad argument name "{}".'.format(self.name))
        if isinstance(flags, str) and not flags.startswith('-'):
            console.abort('"{}" option flag "{}"" does not start with "-".'
                          .format(self.name, flags))
        if isinstance(flags, (list, tuple)) and [s for s in flags if s[:1] != '-']:
            console.abort('Not all "{}" option flags in {} start with "-".'
                          .format(self.name, str(flags)))
        if hasattr(self, 'prepare'):
            self.prepare(not flags)
        if isinstance(flags, str):
            self.add_argument_args.append(flags)
        elif isinstance(flags, (list, tuple)):
            self.add_argument_args.extend(flags)
        elif flags is not None:
            console.abort('Unsupported type ({}) for argument {} flags.'
                          .format(type(flags), self.name))
        # Build keyword argument dict with items that have non-None values.
        self.add_argument_kwargs = {
            key: value
            for key, value in (('dest', self.name),
                               ('action', self.action),
                               ('type', self.data_type),
                               ('metavar', self.metavar),
                               ('help', self.help_text),
                               ('nargs', self.nargs),
                               ('const', self.const),
                               ('default', self.default),
                               ('choices', self.choices),
                               ('required', self.required))
            if value is not None
        }

    def prepare(self, is_argument):
        """Override this method to adjust argument data."""
        pass


class _RegisteredCommand(utility.DumpableObject):
    """Base class for Main and Command objects."""
    def __init__(self, names, args, kwargs, func):
        self.name_tuple = tuple(names) if names else tuple()
        self.name = names[-1] if names else ''
        self.update(args, kwargs, func)
        # Populated by decorator.
        self._subcommands = {}
        # Populated by @property invocation.
        self._sorted_subcommands = None
        self._subparsers_dest = None
        super().__init__()

    @property
    def subcommands(self):
        """Get cached sorted sub-command list property."""
        if not self._sorted_subcommands:
            self._sorted_subcommands = sorted(self._subcommands.values(),
                                              key=lambda scmd: scmd.name)
        return self._sorted_subcommands

    @property
    def subparsers_dest(self):
        """Get name for subparsers dest name."""
        if self._subparsers_dest is None:
            name_parts = [_GlobalData.subparser_base_name]
            name_parts.extend(self.name_tuple)
            self._subparsers_dest = '_'.join(name_parts).upper()
        return self._subparsers_dest

    def has_subcommand(self, name):
        """Return True if name is a subcommand."""
        return name in self._subcommands

    def add_subcommand(self, name, subcommand):
        """Add subcommand by name."""
        self._subcommands[name] = subcommand

    def get_subcommand(self, name):
        """Add subcommand by name."""
        return self._subcommands.get(name, None)

    def update(self, args, kwargs, func):
        """Update associated command information."""
        self.args = args or tuple()
        self.kwargs = kwargs or dict()
        self.func = func
        self.arguments = list(self.kwargs.pop('arguments', []))


class _CommandRegistry:
    """Command registry manages data from by @Main and @Command decorators."""

    add_help = False

    # Default main (command tree root) - updated by @Main decorator.
    main = _RegisteredCommand([], None, None, None)

    @classmethod
    def register_command(cls, name_or_names, args, kwargs, func):
        """Register a discovered command."""
        if not name_or_names:
            if cls.main.func:
                console.abort('More than one @Main encountered.')
            cls.add_help = kwargs and kwargs.pop('add_help', False)
            cls.main.update(args, kwargs, func)
            return cls.main
        # Update the command hierarchy top-down from the main root.
        # Fill in missing container commands.
        if isinstance(name_or_names, tuple):
            name_tuple = name_or_names
        elif isinstance(name_or_names, list):
            name_tuple = tuple(name_or_names)
        else:
            name_tuple = tuple([name_or_names])
        container = cls.main
        for name, name_idx in enumerate(name_tuple[:-1]):
            # Missing parent Command? -> add stub object.
            if not container.has_subcommand(name):
                stub_command = _RegisteredCommand(name_tuple[:name_idx], None, None, None)
                container.add_subcommand(name, stub_command)
            # Descend to child.
            container = container.get_subcommand(name)
        subcommand = container.get_subcommand(name_tuple[-1])
        if subcommand:
            if subcommand.func:
                console.abort('Duplicate @Command: {}'.format(name_tuple))
            # Update the previously-registered subcommand stub.
            subcommand.update(args, kwargs, func)
        else:
            # Attach newly-registered subcommand.
            subcommand = _RegisteredCommand(name_tuple, args, kwargs, func)
            container.add_subcommand(name_tuple[-1], subcommand)
        return subcommand

    @classmethod
    def is_valid_name(cls, name):
        """Return True if name is valid."""
        return (_GlobalData.name_regex.match(name)) is not None

    @classmethod
    def build_parser(cls):
        """Recursively initialize argparse command tree."""
        def _init_command_tree(command, parser, ctx):
            arguments = []
            for ctx.argument in command.arguments:
                if isinstance(ctx.argument, (list, tuple)):
                    # Unpack (flags, argument) pair.
                    if len(ctx.argument) != 2:
                        ctx.abort('Argument is not a tuple or list pair: {argument}')
                    flags, ctx.argument = ctx.argument
                else:
                    # Simple argument without option flags.
                    if not isinstance(ctx.argument, _ArgumentBase):
                        ctx.abort('Bad argument: {argument}')
                    flags = None
                ctx.argument.initialize(flags)
                ctx.arg_args = ctx.argument.add_argument_args
                ctx.arg_kwargs = ctx.argument.add_argument_kwargs
                if console.is_debug():
                    ctx.debug('parser.add_argument({arg_args}, {arg_kwargs})')
                parser.add_argument(*ctx.arg_args, **ctx.arg_kwargs)
                arguments.append(ctx.argument)
            # Get rid of the (flags, argument) pairs, now that the argument
            # objects themselves have flags initialized.
            command.arguments = arguments
            if command.subcommands:
                ctx.debug('parser.add_subparsers(dest="{}")'.format(command.subparsers_dest))
                ctx.subparsers = parser.add_subparsers(dest=command.subparsers_dest,
                                                       required=True)
                for ctx.subcommand in command.subcommands:
                    ctx.debug(('subparsers.add_parser({})'.format(ctx.subcommand.name), (
                        ctx.subcommand.args, ctx.subcommand.kwargs)))
                    ctx.subparser = ctx.subparsers.add_parser(ctx.subcommand.name,
                                                              *ctx.subcommand.args,
                                                              **ctx.subcommand.kwargs)
                    _init_command_tree(ctx.subcommand, ctx.subparser, ctx.subcontext())
                if cls.add_help:
                    help_parser = ctx.subparsers.add_parser('help')
        ctx = _ConsoleContext()
        #pylint: disable=attribute-defined-outside-init
        ctx.main_parser = argparse.ArgumentParser(*cls.main.args, **cls.main.kwargs)
        _init_command_tree(cls.main, ctx.main_parser, ctx)
        return ctx.main_parser

    @classmethod
    def get_active_commands(cls, args):
        """Find active command(s) based on CLI args."""
        active_commands = []
        def _collect_active_subcommands(command):
            for subcommand in command.subcommands:
                match_name = getattr(args, command.subparsers_dest, None)
                if match_name and subcommand.name == match_name:
                    active_commands.append(subcommand)
                _collect_active_subcommands(subcommand)
        active_commands.append(cls.main)
        _collect_active_subcommands(cls.main)
        if not active_commands:
            console.abort('There is no @Main or active @Command.')
        return active_commands

    @classmethod
    def fix_command_args(cls, args, commands):
        """Validate and convert argument data."""
        errors = 0
        for command in commands:
            for argument in command.arguments:
                attr_value = getattr(args, argument.name)
                if attr_value is not None and hasattr(argument, 'fix'):
                    try:
                        setattr(args, argument.name, argument.fix(attr_value))
                    except (TypeError, ValueError) as exc:
                        console.error('Unable to convert argument "{}" value: {}'
                                      .format(argument.name, str(attr_value)))
                        console.error(exc)
                        errors += 1
        if errors > 0:
            console.abort('Errors during argument data conversion: {}'.format(errors))

    @classmethod
    def parse_cli(cls, cli_args=None):
        """Call once to parse command line. Return (args, commands)."""

        # Build an argparse.ArgumentParser based on the decorator-provided @Main
        # and @Command data.
        parser = cls.build_parser()

        # Parse the command line arguments.
        console.debug('parser.parse_args(args={})'.format(cli_args))
        args = parser.parse_args(args=cli_args, )
        console.debug('args={}'.format(args))

        # Recursively collect one or two Command objects for @Main and or active @Command.
        active_commands = cls.get_active_commands(args)

        # Validate and convert argument data.
        cls.fix_command_args(args, active_commands)

        return (args, active_commands)


class CLI:
    """Wrapper namespace for CLI declaration decorators and classes."""

    class Command:
        """
        Command function decorator for sub-command implementation.

        Accepts all ArgumentParser() positional/keyword arguments.

        Mandatory positional arguments:
            name_or_names  command name or name sequence

        Additional keyword arguments:
            arguments  Opt.XXX/Arg.XXX instances for options/arguments

        Sequence name_or_names values are used for lower level sub-commands.
        """
        def __init__(self, name_or_names, *args, **kwargs):
            self.name_or_names = name_or_names
            self.args = args
            self.kwargs = kwargs

        def __call__(self, func):
            _CommandRegistry.register_command(self.name_or_names,
                                              self.args,
                                              self.kwargs,
                                              func)

    class Main(Command):
        """
        Application main() function decorator.

        Accepts all ArgumentParser() positional/keyword arguments.

        Additional keyword arguments:
            arguments  Arg.XXX instances for global options/arguments
            add_help   add help command and sub-commands if True
        """
        def __init__(self, *args, **kwargs):
            super().__init__(tuple(), *args, **kwargs)

    class String(_ArgumentBase):
        """String option."""
        def __init__(self, name, help_text,
                     metavar=None,
                     nargs=None,
                     const=None,
                     default=None,
                     choices=None,
                     required=None):
            super().__init__(name, 'store', str, help_text,
                             metavar=metavar,
                             nargs=nargs,
                             const=const,
                             default=default,
                             choices=choices,
                             required=required)

    class Integer(_ArgumentBase):
        """Integer option."""
        def __init__(self, name, help_text,
                     metavar=None,
                     nargs=None,
                     const=None,
                     default=None,
                     choices=None,
                     required=None):
            super().__init__(name, 'store', int, help_text,
                             metavar=metavar,
                             nargs=nargs,
                             const=const,
                             default=default,
                             choices=choices,
                             required=required)

    class Boolean(_ArgumentBase):
        """Boolean option."""
        def __init__(self, name, help_text,
                     metavar=None,
                     nargs=None,
                     const=None,
                     default=None,
                     choices=None,
                     required=None):
            super().__init__(name, 'store_true', None, help_text,
                             metavar=metavar,
                             nargs=nargs,
                             const=const,
                             default=default,
                             choices=choices,
                             required=required)
        def prepare(self, is_argument):
            """Use store/str for arguments and store_true/None for options."""
            if is_argument:
                self.action = 'store'
                self.data_type = str
        def fix(self, value):
            """Validate boolean string and convert to bool."""
            bvalue = utility.string_to_boolean(value)
            if bvalue is None:
                raise ValueError('Bad boolean argument value "{}"'.format(value))
            return bvalue


    @classmethod
    def main(cls, *args, **kwargs):
        """
        Call once to parse command line and invoke @Main/@Command functions.

        Special keyword arguments:

            cli_args         command line arguments to use instead of sys.argv
            abort_exception  raise console.FatalError instead of exiting in abort()

        Additional positional and keyword arguments are passed to @Main and or
        @Command functions.

        Set ARGDECO_DEBUG environment variable to true/t/yes/y/1 for verbose
        argument parsing output.
        """
        if os.environ.get('ARGDECO_DEBUG', '').lower() in utility.TRUE_STRINGS:
            console.set_debug(True)
        cli_args = kwargs.pop('cli_args', None)
        _GlobalData.abort_exception = kwargs.pop('abort_exception', False)
        (parsed_args, parsed_commands) = _CommandRegistry.parse_cli(cli_args=cli_args)
        for command in parsed_commands:
            if command.func:
                command.func(parsed_args, *args, **kwargs)
