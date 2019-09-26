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

import sys
import os
import argparse
import re
from inspect import isfunction


class _Private:
    """Private data, functions, and classes."""

    # Data from decorators
    main = None
    commands = []

    default_group_name = 'subcommands'
    name_regex = re.compile(r'^\w+$')
    true_strings = ('true', 't', 'yes', 'y', '1')
    false_strings = ('false', 'f', 'no', 'n', '0')
    enable_debug = os.environ.get('ARGDECO_DEBUG', '').lower() in true_strings

    @classmethod
    def string_to_boolean(cls, svalue, default=None):
        """Convert string to True, False, default value, or None."""
        if svalue.lower() in cls.true_strings:
            return True
        if svalue.lower() in cls.false_strings:
            return False
        return default

    @classmethod
    def _message(cls, msg, prefix=None, is_error=False):
        """Supports all console output functions, and can abort for fatal errors."""
        stream = sys.stderr if is_error else sys.stdout
        if isinstance(msg, Exception):
            msg = '{}: {}'.format(type(msg), str(msg))
        if not prefix:
            stream.write(msg)
        else:
            stream.write('{}: {}'.format(prefix, msg))
        stream.write(os.linesep)

    @classmethod
    def object_repr(cls, instance, exclude=None):
        """Format class instance repr() string."""
        exclude = exclude or []
        def _format_value(value):
            if isinstance(value, str):
                return "'{}'".format(value)
            if isfunction(value):
                return '{}()'.format(value.__name__)
            return repr(value)
        return '{}({})'.format(
            instance.__class__.__name__,
            ', '.join(['{}={}'.format(k, _format_value(getattr(instance, k)))
                       for k in sorted(instance.__dict__.keys())
                       if not k.startswith('_') and k not in exclude]))

    @classmethod
    def debug(cls, msg):
        """Debug message (if DEBUG enabled)."""
        if cls.enable_debug:
            cls._message(msg, prefix='DEBUG')

    @classmethod
    def debug_object(cls, obj, exclude=None):
        """Debug message for object instance."""
        if cls.enable_debug:
            cls._message(cls.object_repr(obj, exclude=exclude), prefix='DEBUG')

    @classmethod
    def info(cls, msg):
        """Information message."""
        cls._message(msg)

    @classmethod
    def warning(cls, msg):
        """Warning message."""
        cls._message(msg, prefix='WARNING', is_error=True)

    @classmethod
    def error(cls, msg):
        """Error message."""
        cls._message(msg, prefix='ERROR', is_error=True)

    @classmethod
    def abort(cls, msg):
        """Display critical error and exit."""
        cls._message(msg, prefix='CRITICAL', is_error=True)
        sys.exit(1)

    @classmethod
    def is_valid_name(cls, name):
        """Return True if name is valid."""
        return (cls.name_regex.match(name)) is not None

    @classmethod
    def build_command_map(cls):
        """
        Scan _Private to build group name to group mapping.

        Note that CommandGroup is guaranteed to have a good "name" member and
        Command must have a good "group" member.
        """
        if not cls.commands:
            return {}
        class _Group:
            def __init__(self, command_group):
                self.name = command_group.name
                self.symbol = command_group.symbol
                self.args = command_group.args
                self.kwargs = command_group.kwargs
                self.commands = []
            def __repr__(self):
                return cls.object_repr(self)
            def __str__(self):
                return cls.object_repr(self)
        grouped_command_map = {}
        default_group_name = None
        for group in cls.main.groups:
            if group.name not in grouped_command_map:
                grouped_command_map[group.name] = _Group(group)
                # The first explicitly-declared group becomes the default
                if not default_group_name:
                    default_group_name = group.name
            else:
                cls.warning('Ignoring duplicate command group "{}".'.format(group.name))
        # Add a default group if no groups were declared.
        if not grouped_command_map:
            grouped_command_map[cls.default_group_name] = CLI.CommandGroup(cls.default_group_name)
            default_group_name = cls.default_group_name
        # Add missing groups for commands that reference unregistered group names.
        for command in cls.commands:
            if command.group:
                if command.group not in grouped_command_map:
                    grouped_command_map[command.group] = _Group(CLI.CommandGroup(command.group))
            else:
                command.group = default_group_name
        # Build command lists in command groups.
        for command in cls.commands:
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
        def __init__(self, arg_type, name, action, data_type, metavar, help_text,
                     flags, required, nargs, const, default, choices):

            # Perform basic sanity checks against common positional arguments to
            # catch cases where they are accidentally swapped.
            if not _Private.is_valid_name(name):
                _Private.abort('Bad {} name "{}".'.format(arg_type, name))
            if isinstance(flags, str) and not flags.startswith('-'):
                _Private.abort('"{}" {} flag "{}"" does not start with "-".'
                               .format(name, arg_type, flags))
            if isinstance(flags, (list, tuple)) and [s for s in flags if s[:1] != '-']:
                _Private.abort('Not all "{}" {} flags in {} start with "-".'
                               .format(name, arg_type, str(flags)))

            self.arg_type = arg_type
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
                _Private.abort('Unsupported type ({}) for argument {} flags.'
                               .format(type(flags), name))

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

        def __repr__(self):
            return _Private.object_repr(self)

        def __str__(self):
            return _Private.object_repr(self)

    class GenericOption(GenericArgumentBase):
        """Base class for argument declaration classes."""
        def __init__(self, name, action, data_type, metavar, help_text,
                     flags, required, const, default, choices):
            # flags is a single option string or a list.
            super().__init__('option', name, action, data_type, metavar,
                             help_text, flags, required, None,
                             const, default, choices)


    class GenericArgument(GenericArgumentBase):
        """Base class for argument declaration classes."""
        def __init__(self, name, action, data_type, metavar, help_text,
                     nargs, const, default, choices):
            # # Prefer nargs defaulting to 1.
            # if nargs is None:
            #     nargs = 1
            super().__init__('argument', name, action, data_type, metavar,
                             help_text, None, None, nargs,
                             const, default, choices)

    class TrailingListArgument(GenericArgument):
        """
        Wrapper for Arg that declares a trailing list argument.

        As a sanity check, there must be only of these in the arguments list
        and it must be the last item in that list.
        """
        def __init__(self, argument, nargs=None):
            self.argument = argument
            super().__init__(argument.name, argument.action,
                             argument.data_type, argument.metavar,
                             argument.help_text, nargs, argument.const,
                             argument.default, argument.choices)

        def fix(self, values):
            """Validate and convert via the single argument fix() method."""
            if hasattr(self.argument, 'fix'):
                return [self.argument.fix(value) for value in values]
            return values

    @classmethod
    def parse_command_arguments(cls, parser, name, args):
        """Check and parse arguments for @Main or @Command."""
        found_trailing_list = False
        for arg in args:
            if found_trailing_list:
                cls.abort('TrailingList must be the single last argument.')
            cls.debug('Add argument {}:{}.'.format(name, arg.name))
            parser.add_argument(*arg.add_argument_args, **arg.add_argument_kwargs)
            if isinstance(arg, cls.TrailingListArgument):
                found_trailing_list = True

    @classmethod
    def parse_cli(cls, args=None):
        """Call once to parse command line. Return (args, commands)."""
        # Deal with main parser and arguments.
        if cls.main:
            cls.debug('Create ArgumentParser for @Main.')
            parser = argparse.ArgumentParser(*cls.main.args, **cls.main.kwargs)
            cls.parse_command_arguments(parser, '@Main', cls.main.arguments)
        else:
            cls.debug('Create default ArgumentParser.')
            parser = argparse.ArgumentParser()

        # Deal with sub-parsers and arguments.
        grouped_command_map = cls.build_command_map()
        for group_name in sorted(grouped_command_map.keys()):
            group = grouped_command_map[group_name]
            if group.commands:
                cls.debug('Create sub-parser for {}.'.format(group.name))
                subparsers = parser.add_subparsers(*group.args, **group.kwargs)
                for cmd in group.commands:
                    cls.debug('Add command parser for {}:{}.'.format(group.name, cmd.name))
                    subparser = subparsers.add_parser(cmd.name, *cmd.args, **cmd.kwargs)
                    cls.parse_command_arguments(subparser, cmd.name, cmd.arguments)

        # Parse the command line arguments.
        args = parser.parse_args(args=args)

        # Dump stuff if debug is enabled.
        if cls.enable_debug:
            cls.debug('Parsed arguments: {}'.format(args))
            for group_name in sorted(grouped_command_map.keys()):
                command_group = grouped_command_map[group_name]
                cls.debug_object(command_group, exclude=['commands'])
                for command in command_group.commands:
                    cls.debug_object(command, exclude=['arguments'])
                    for argument in command.arguments:
                        cls.debug_object(argument)

        # Find active group and command if it is a sub-command.
        active_command = None
        for group in grouped_command_map.values():
            command_name = getattr(args, group.symbol, None)
            if command_name:
                for cmd in group.commands:
                    if command_name == cmd.name:
                        active_command = cmd
                        break
                break

        # Fall back to the "main" command when there isn't a sub-command.
        if not active_command:
            cls.debug('There is no active sub-command.')
            active_command = cls.main

        # Validate and convert argument data.
        errors = 0
        for arg in active_command.arguments:
            attr_value = getattr(args, arg.name)
            if attr_value is not None and hasattr(arg, 'fix'):
                try:
                    setattr(args, arg.name, arg.fix(attr_value))
                except (TypeError, ValueError) as exc:
                    cls.error('Unable to convert argument "{}" value: {}'
                              .format(arg.name, str(attr_value)))
                    cls.error(exc)
                    errors += 1
        if errors > 0:
            cls.abort('Errors during argument data conversion: {}'.format(errors))

        # Return args and active @Main/@Command object(s).
        commands = []
        if cls.main:
            commands.append(cls.main)
        if active_command and active_command != cls.main:
            commands.append(active_command)
        if not commands:
            cls.abort('No CLI @Main or @Command functions are available')

        return (args, commands)


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
            if _Private.main:
                _Private.abort('More than one @Main encountered.')
            self.func = func
            _Private.main = self


    class CommandGroup:
        """Holds args/kwargs for argparse add_subparsers()."""
        def __init__(self, name, *args, **kwargs):
            self.name = name
            self.args = args
            self.kwargs = kwargs
            self.symbol = 'ZZZ_{}'.format(self.name.upper())
            if 'title' in self.kwargs and self.kwargs['title'] != self.name:
                _Private.warning('Overriding command group {} "title" value "{}" with "{}".'
                                 .format(self.name, self.kwargs['title'], self.name))
            self.kwargs['title'] = self.name
            if 'dest' in self.kwargs and self.kwargs['dest'] != self.name:
                _Private.warning('Overriding command group {} "dest" value "{}" with "{}".'
                                 .format(self.name, self.kwargs['dest'], self.symbol))
            self.kwargs['dest'] = self.symbol


    class Command:
        """
        Command function decorator for sub-command implementation.

        Accepts all ArgumentParser() positional/keyword arguments.

        Mandatory positional arguments:
            name  command name

        Additional keyword arguments:
            arguments  Opt.XXX/Arg.XXX instances for options/arguments
            group      command group name
        """

        def __init__(self, name, *args, **kwargs):
            self.name = name
            self.arguments = kwargs.pop('arguments', [])
            self.group = kwargs.pop('group', None)
            self.args = args
            self.kwargs = kwargs
            self.func = None

        def __call__(self, func):
            self.func = func
            _Private.commands.append(self)
            return func

        def __repr__(self):
            return _Private.object_repr(self)

        def __str__(self):
            return _Private.object_repr(self)

    class Opt:
        """Option declaration."""

        class String(_Private.GenericOption):
            """String option."""
            def __init__(self, name, flags, help_text,
                         metavar=None, required=None,
                         const=None, default=None, choices=None):
                super().__init__(name, 'store', str, metavar, help_text,
                                 flags, required, const, default, choices)

        class Integer(_Private.GenericOption):
            """Integer option."""
            def __init__(self, name, flags, help_text,
                         metavar=None, required=None,
                         const=None, default=None, choices=None):
                super().__init__(name, 'store', int, metavar, help_text,
                                 flags, required, const, default, choices)

        class Boolean(_Private.GenericOption):
            """Boolean option."""
            def __init__(self, name, flags, help_text,
                         metavar=None, required=None,
                         const=None, default=None, choices=None):
                super().__init__(name, 'store_true', None, metavar, help_text,
                                 flags, required, const, default, choices)

    class Arg:
        """Argument declaration."""

        class String(_Private.GenericArgument):
            """String argument."""
            def __init__(self, name, help_text, metavar=None,
                         const=None, default=None, choices=None):
                super().__init__(name, 'store', str, metavar, help_text,
                                 None, const, default, choices)

        class Integer(_Private.GenericArgument):
            """Integer argument."""
            def __init__(self, name, help_text, metavar=None,
                         const=None, default=None, choices=None):
                super().__init__(name, 'store', int, metavar, help_text,
                                 None, const, default, choices)

        class Boolean(_Private.GenericArgument):
            """Boolean argument."""
            def __init__(self, name, help_text, metavar=None,
                         const=None, default=None, choices=None):
                # Use str as the type, because argparse doesn't seem to convert
                # boolean arguments.
                super().__init__(name, 'store', str, metavar, help_text,
                                 None, const, default, choices)

            def fix(self, value):
                """Validate boolean string and convert to bool."""
                bvalue = _Private.string_to_boolean(value)
                if bvalue is None:
                    raise ValueError('Bad boolean argument value "{}"'.format(value))
                return bvalue

    @classmethod
    def trailing_argument_list(cls, argument, nargs=None):
        """
        Wrapper for an Arg class that declares a trailing list argument.

        As a sanity check, there must be only of these in the arguments list and
        it must be the last item in that list.
        """
        return _Private.TrailingListArgument(argument, nargs=nargs)

    @classmethod
    def main(cls, *args, **kwargs):
        """
        Call once to parse command line and invoke @Main/@Command functions.

        A special "cli_args" keyword accepts a list of command line arguments to
        use instead of sys.argv.

        Any additional positional or keyword arguments are passed to @Main and
        or @Command functions.

        Set ARGDECO_DEBUG environment variable to true/t/yes/y/1 for verbose
        argument parsing output.
        """
        cli_args = kwargs.pop('cli_args', None)
        (parsed_args, parsed_commands) = _Private.parse_cli(args=cli_args)
        for command in parsed_commands:
            if command.func:
                command.func(parsed_args, *args, **kwargs)
