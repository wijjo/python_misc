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

All needed functionality is available in the CLI namespace class.

Uses structured decorators to provide a thin declarative veneer over the
imperative argparse API. Many decorator and object positional and keyword
arguments map directly to underlying argparse functions. Users can leverage
argparse knowledge and documentation.

Serves a similar purpose to the older scriptbase.cli module. However, it takes a
much more minimalist approach in leaving as much as possible to argparse.

When function/method parameters include *args and **kwargs please refer to
appropriate argparse documentation. It is not redundantly documented here, since
it may change.
"""

import sys
import os
import argparse


class Global:
    """Global data."""
    debug = False


class Declarations:
    """Items discovered by decorators."""
    main = None
    commands = []


def _message(stream, prefix, msg):
    if isinstance(msg, Exception):
        msg = '{}: {}'.format(type(msg), str(msg))
    if not prefix:
        stream.write(msg)
    else:
        stream.write('{}: {}'.format(prefix, msg))
    stream.write(os.linesep)


def debug(msg):
    """Like scriptbase.console.warning(), but keeps this module independent."""
    if Global.debug:
        _message(sys.stdout, 'DEBUG', msg)


def info(msg):
    """Like scriptbase.console.warning(), but keeps this module independent."""
    _message(sys.stdout, None, msg)


def warning(msg):
    """Like scriptbase.console.warning(), but keeps this module independent."""
    _message(sys.stderr, 'WARNING', msg)


def error(msg):
    """Like scriptbase.console.error(), but keeps this module independent."""
    _message(sys.stderr, 'ERROR', msg)


def abort(msg):
    """Like scriptbase.console.abort(), but keeps this module independent."""
    _message(sys.stderr, 'CRITICAL', msg)
    sys.exit(1)


def build_command_map():
    """
    Scan Declarations to build group name to group mapping.

    Note that CommandGroup is guaranteed to have a good "name" member and
    Command must have a good "group" member.
    """
    class _Group:
        def __init__(self, command_group):
            self.name = command_group.name
            self.symbol = command_group.symbol
            self.args = command_group.args
            self.kwargs = command_group.kwargs
            self.commands = []
    grouped_command_map = {}
    for group in Declarations.main.groups:
        if group.name not in grouped_command_map:
            grouped_command_map[group.name] = _Group(group)
        else:
            warning('Ignoring duplicate command group "{}".'.format(group.name))
    # Add missing groups for commands that reference unregistered group names.
    for command in Declarations.commands:
        if command.group and command.group not in grouped_command_map:
            grouped_command_map[command.group] = _Group(CLI.CommandGroup(command.group))
    # Build command lists in command groups.
    for command in Declarations.commands:
        grouped_command_map[command.group].commands.append(command)
    return grouped_command_map


class GenericArgumentBase:
    """
    Base class for argument and option declaration classes.

    Usage notes:

    Derived classes should be used to assure sane argument combinations.

    Avoids conflicts by renaming "help" and "type" to "help_text" and
    "data_type", and by making thme required positional arguments.

    "data_type" should ultimately be provided by a derived class in this
    library, not the user.
    """
    def __init__(self, name, action, data_type, metavar, help_text,
                 flags, required, nargs, const, default, choices):

        self.name = name

        # add_argument() requires flags or dest as positional arguments.
        self.add_argument_args = []
        if isinstance(flags, str):
            self.add_argument_args.append(flags)
        elif isinstance(flags, (list, tuple)):
            self.add_argument_args.extend(flags)
        elif flags is None:
            self.add_argument_args.append(name)
        else:
            abort('Unsupported type ({}) for argument {} flags.'.format(type(flags), name))

        # Build keyword argument dict with items that have non-None values.
        # Don't add "dest" if it was supplied as the positional argument.
        self.add_argument_kwargs = {
            key: value
            for key, value in (('dest', name if flags else None),
                               ('action', action),
                               ('type', data_type),
                               ('metavar', metavar),
                               ('help', help_text),
                               ('required', required),
                               ('nargs', nargs),
                               ('const', const),
                               ('default', default),
                               ('choices', choices))
            if value is not None
        }


class GenericOption(GenericArgumentBase):
    """Base class for argument declaration classes."""
    def __init__(self, name, action, data_type, metavar, help_text,
                 flags, required, const, default, choices):
        # flags is a single option string or a list.
        if isinstance(flags, str):
            flags = [flags]
        super().__init__(name, action, data_type, metavar, help_text,
                         flags, required, None, const, default, choices)


class GenericArgument(GenericArgumentBase):
    """Base class for argument declaration classes."""
    def __init__(self, name, action, data_type, metavar, help_text,
                 nargs, const, default, choices):
        # # Prefer nargs defaulting to 1.
        # if nargs is None:
        #     nargs = 1
        super().__init__(name, action, data_type, metavar, help_text,
                         None, None, nargs, const, default, choices)


class CLI:
    """Wrapper namespace for CLI declaration decorators and classes."""

    class Main:
        """
        Application main() function decorator.

        Accepts all ArgumentParser() positional/keyword arguments.

        Additional keyword arguments:
            arguments  Arg.XXX instances for global options/arguments
            groups     command groups
        """

        def __init__(self, *args, **kwargs):
            self.args = args
            self.arguments = kwargs.pop('arguments', [])
            self.groups = kwargs.pop('groups', [])
            self.kwargs = kwargs
            self.func = None

        def __call__(self, func):
            if Declarations.main:
                abort('More than one @Main encountered.')
            self.func = func
            Declarations.main = self


    class CommandGroup:
        """Holds args/kwargs for argparse add_subparsers()."""
        default_name = 'subcommands'

        def __init__(self, name, *args, **kwargs):
            self.name = name
            self.args = args
            self.kwargs = kwargs
            self.symbol = 'COMMAND_FROM_{}'.format(self.name.upper())
            if 'title' in self.kwargs and self.kwargs['title'] != self.name:
                warning('Overriding command group {} "title" value "{}" with "{}".'
                        .format(self.name, self.kwargs['title'], self.name))
            self.kwargs['title'] = self.name
            if 'dest' in self.kwargs and self.kwargs['dest'] != self.name:
                warning('Overriding command group {} "dest" value "{}" with "{}".'
                        .format(self.name, self.kwargs['dest'], self.symbol))
            self.kwargs['dest'] = self.symbol


    class Command:
        """
        Command function decorator for sub-command implementation.

        Accepts all ArgumentParser() positional/keyword arguments.

        Mandatory positional arguments:
            name  command name

        Additional keyword arguments:
            arguments  Arg.XXX instances for options/arguments
            group      command group name
        """

        def __init__(self, name, *args, **kwargs):
            self.name = name
            self.args = args
            self.arguments = kwargs.pop('arguments', [])
            self.group = kwargs.pop('group', CLI.CommandGroup.default_name)
            self.kwargs = kwargs
            self.func = None

        def __call__(self, func):
            self.func = func
            Declarations.commands.append(self)
            return func

    class Opt:
        """Option declaration class for ArgumentParser.add_argument() calls."""

        class String(GenericOption):
            """String option."""
            def __init__(self, name, flags, help_text,
                         metavar=None, required=None,
                         const=None, default=None, choices=None):
                super().__init__(name, 'store', str, metavar, help_text,
                                 flags, required, const, default, choices)

        class Integer(GenericOption):
            """Integer option."""
            def __init__(self, name, flags, help_text,
                         metavar=None, required=None,
                         const=None, default=None, choices=None):
                super().__init__(name, 'store', int, metavar, help_text,
                                 flags, required, const, default, choices)

        class Boolean(GenericOption):
            """Boolean option."""
            def __init__(self, name, flags, help_text,
                         metavar=None, required=None,
                         const=None, default=None, choices=None):
                super().__init__(name, 'store_true', None, metavar, help_text,
                                 flags, required, const, default, choices)

    class Arg:
        """Argument declaration class for ArgumentParser.add_argument() calls."""

        class String(GenericArgument):
            """String argument."""
            def __init__(self, name, help_text,
                         metavar=None, nargs=None,
                         const=None, default=None, choices=None):
                super().__init__(name, 'store', str, metavar, help_text,
                                 nargs, const, default, choices)

        class Integer(GenericArgument):
            """Integer argument."""
            def __init__(self, name, help_text,
                         metavar=None, nargs=None,
                         const=None, default=None, choices=None):
                super().__init__(name, 'store', int, metavar, help_text,
                                 nargs, const, default, choices)

        class Boolean(GenericArgument):
            """Boolean argument."""
            def __init__(self, name, help_text,
                         metavar=None, nargs=None,
                         const=None, default=None, choices=None):
                super().__init__(name, 'store', bool, metavar, help_text,
                                 nargs, const, default, choices)

    @classmethod
    def main(cls):
        """Call once to parse command line and invoke main and or command handler(s)."""
        Global.debug = os.environ.get('ARGDECO_DEBUG', '').lower() in ('true', 't', 'yes', 'y', '1')
        # Deal with main parser and arguments.
        if Declarations.main:
            debug('Create ArgumentParser for @Main.')
            parser = argparse.ArgumentParser(*Declarations.main.args,
                                             **Declarations.main.kwargs)
            for argument in Declarations.main.arguments:
                parser.add_argument(*argument.args, **argument.kwargs)
        else:
            if Global.debug:
                info('Create default ArgumentParser.')
            parser = argparse.ArgumentParser()
        # Deal with sub-parsers and their arguments.
        grouped_command_map = build_command_map()
        for group_name in sorted(grouped_command_map.keys()):
            group = grouped_command_map[group_name]
            if not group.commands:
                continue
            debug('Create sub-parser for {}.'.format(group.name))
            subparsers = parser.add_subparsers(*group.args, **group.kwargs)
            for command in group.commands:
                debug('Add command parser for {}:{}.'.format(group.name, command.name))
                subparser = subparsers.add_parser(command.name,
                                                  *command.args,
                                                  **command.kwargs)
                for argument in command.arguments:
                    debug('Add argument {}:{}.'.format(command.name, argument.name))
                    subparser.add_argument(*argument.add_argument_args,
                                           **argument.add_argument_kwargs)
        # Parse the command line arguments.
        args = parser.parse_args()
        # Find active group and command if it is a sub-command.
        active_command = None
        for group in grouped_command_map.values():
            command_name = getattr(args, group.symbol, None)
            if command_name:
                for command in group.commands:
                    if command_name == command.name:
                        active_command = command
                    break
                break
        # Fall back to the "main" command when it isn't a sub-command.
        if not active_command:
            active_command = Declarations.main
        # Fixup argument data.
        errors = 0
        for argument in active_command.arguments:
            attr_value = getattr(args, argument.name)
            if attr_value is not None and hasattr(argument, 'fix'):
                try:
                    if isinstance(attr_value, list):
                        fixed_values = []
                        for raw_value in attr_value:
                            fixed_values.append(argument.fix(raw_value))
                        setattr(args, argument.name, fixed_values)
                    else:
                        setattr(args, argument.name, argument.fix(attr_value))
                except (TypeError, ValueError) as exc:
                    error('Unable to convert argument "{}" value: {}'
                          .format(argument.name, str(attr_value)))
                    error(exc)
                    errors += 1
        if errors > 0:
            abort('Errors during argument data conversion: {}'.format(errors))
        # Invoke @Main and or @Command functions.
        funcs = []
        if Declarations.main and Declarations.main.func:
            funcs.append(Declarations.main.func)
        if active_command and active_command.func and active_command != Declarations.main:
            funcs.append(active_command.func)
        if not funcs:
            abort('No CLI @Main or @Command functions are available')
        for func in funcs:
            func(args)
