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
Declaritive command line interfaces.

Currently wraps the standard argparse module, but attempts to make it much
simpler and more obvious how to build a CLI.

All needed functionality is accessible through the CLI namespace class. Nothing
else at the module level is public.

This stand-alone module only depends on the Python Standard Library.

This module is intended as a simpler/cleaner rewrite of scriptbase/cli.

Set the ARGDECO_DEBUG environment variable to true/t/yes/y/1 for verbose
argument parsing output.
"""

#TODO:
# - Format and rewrap help NOTES.

import sys
import os
import argparse
import re
import traceback


class _Constants:
    # Global stuff.
    subparser_base_name = 'SUBCOMMAND'
    name_regex = re.compile(r'^\w+$')
    quantity_regex = re.compile(r'^[+*?]|\d+')


class _Console:
    is_debug = False

    @classmethod
    def _display(cls, msg, stream=None, tag=None):
        output_stream = stream or sys.stdout
        if isinstance(msg, Exception):
            template = 'Exception[%s]: %s' % (template.__class__.__name__, str(template))
        if tag:
            output_stream.write(tag)
            output_stream.write(': ')
        output_stream.write(msg)
        output_stream.write(os.linesep)

    @classmethod
    def info(cls, msg):
        """Display informational messages."""
        cls._display(msg)

    @classmethod
    def debug(cls, msg):
        """Display debug messages."""
        if cls.is_debug:
            cls._display(msg, stream=sys.stderr, tag='DEBUG')

    @classmethod
    def error(cls, msg):
        """Display error messages."""
        cls._display(msg, stream=sys.stderr, tag='ERROR')

    @classmethod
    def abort(cls, msg):
        """Display fatal error messages and exit with return code 255."""
        cls.error(msg)
        sys.stderr.write('ABORT')
        sys.stderr.write(os.linesep)
        sys.exit(255)


class _Dumpable:

    def __init__(self, exclude=None, include=None):
        self._exclude = exclude or []
        self._include = include or []

    def iter_filtered_attributes(self):
        """Iterate name/value pairs with include/exclude filtering."""
        for name in sorted(self.__dict__.keys()):
            if (name in self._include or not (
                    name.startswith('_') or name in self._exclude)):
                yield (name, getattr(self, name))

    def __str__(self):
        lines = ['---', '{}:'.format(self.__class__.__name__)]
        for name, value in self.iter_filtered_attributes():
            if isinstance(value, str):
                value = '"{}"'.format(value)
            elif isinstance(value, (list, dict)):
                value = '{}[{}]'.format(value.__class__.__name__, len(value))
            lines.append('   {}={}'.format(name, value))
        lines.append('---')
        return os.linesep.join(lines)


class _RegisteredCommand(_Dumpable):
    """Command registration information."""

    def __init__(self, names, sort_last=False):
        self.name_tuple = tuple(names) if names else tuple()
        self.name = names[-1] if names else ''
        self.sort_key = self.name if not sort_last else None
        # Data provided by decorators later.
        self.description = None
        self.notes = None
        self.arguments = []
        self.func = None
        self._subcommands = {}
        # Populated by @property invocation.
        self._sorted_subcommands = None
        self._subparsers_dest = None
        super().__init__(include='_subcommands')

    def update(self,
               description=None,
               notes=None,
               arguments=None,
               func=None):
        """Called when information is received from a decorator."""
        if description is not None:
            self.description = description
        if notes is not None:
            self.notes = notes
        if arguments is not None:
            self.arguments = arguments
        if func is not None:
            self.func = func

    @property
    def subcommands(self):
        """Get cached sorted sub-command list property."""
        if not self._sorted_subcommands:
            scmds1 = [cmd for cmd in self._subcommands.values() if cmd.sort_key]
            scmds2 = [cmd for cmd in self._subcommands.values() if not cmd.sort_key]
            self._sorted_subcommands = (sorted(scmds1, key=lambda cmd: cmd.sort_key) +
                                        sorted(scmds2, key=lambda cmd: cmd.name))
        return self._sorted_subcommands

    @property
    def subparsers_dest(self):
        """Get name for subparsers dest name."""
        if self._subparsers_dest is None:
            name_parts = [_Constants.subparser_base_name]
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

    def reset(self):
        """Clear cached data."""
        self._sorted_subcommands = None


class _Registry:
    """Command registry manages data from by @Command decorators."""

    # Program name. May be updated later.
    program_name = os.path.basename(sys.argv[0])
    # Command tree root - updated by @Root decorator.
    root = _RegisteredCommand([])
    # Call-back hook function called before @Root and @Command functions.
    start_func = None
    # Accumulate errors so user can see all of them.
    errors = []

    @staticmethod
    def string_to_boolean(svalue, default=None):
        """Convert string to True, False, default value, or None."""
        if svalue.lower() in ('true', 't', 'yes', 'y', '1'):
            return True
        if svalue.lower() in ('false', 'f', 'no', 'n', '0'):
            return False
        return default

    @classmethod
    def add_error(cls, msg):
        """Add an error message."""
        cls.errors.append(msg)

    @classmethod
    def add_exception(cls, msg, exc):
        """Add an exception message, and optionally dump the stack."""
        cls.add_error('{}: {}({})'.format(msg, exc.__class__.__name__, exc))
        if _Console.is_debug:
            traceback.print_last()

    @classmethod
    def _get_by_name(cls, name_or_names, create_missing=False):
        # Return new or existing command object.
        # Fill in missing parents with stub objects.
        if isinstance(name_or_names, tuple):
            name_tuple = name_or_names
        elif isinstance(name_or_names, list):
            name_tuple = tuple(name_or_names)
        else:
            name_tuple = tuple([name_or_names])
        if not name_tuple:
            return cls.root
        container = cls.root
        for name_idx, name in enumerate(name_tuple[:-1]):
            if not container.has_subcommand(name):
                if create_missing:
                    stub_command = _RegisteredCommand(name_tuple[:name_idx])
                    container.add_subcommand(name, stub_command)
                else:
                    return None
            container = container.get_subcommand(name)
        command = container.get_subcommand(name_tuple[-1])
        if not command:
            if create_missing:
                command = _RegisteredCommand(name_tuple)
                container.add_subcommand(name_tuple[-1], command)
            else:
                return None
        return command

    @classmethod
    def register_start(cls, func):
        """Register @Start function."""
        cls.start_func = func

    @classmethod
    def register_root(cls, arguments, func):
        """Register discovered @Root command."""
        if cls.root.func:
            cls.add_error('More than one @Root encountered.')
        cls.root.update(arguments=arguments, func=func)
        return cls.root

    @classmethod
    def register_command(cls,
                         command_name_or_names,
                         description,
                         notes,
                         arguments,
                         func):
        """Register a discovered command."""
        command = cls._get_by_name(command_name_or_names, create_missing=True)
        if command.func:
            cls.add_error('Duplicate @Command: {}'.format(command_name_or_names))
        command.update(description=description,
                       notes=notes,
                       arguments=arguments,
                       func=func)
        return command

    @classmethod
    def register_help_command(cls):
        """Inject "help" commands."""
        def _help(args):
            command = cls._get_by_name(args.COMMAND_NAME)
            if command:
                cls.print_help(command=command)
            else:
                _Console.abort('No help available for command: {}'
                               .format(' '.join(args.COMMAND_NAME)))
        command = _RegisteredCommand(['help'], sort_last=True)
        command.update(description='display command help', func=_help, arguments=[
            CLI.String('COMMAND_NAME', 'command name(s)', quantity='*'),
        ])
        cls.root.add_subcommand('help', command)
        cls.root.reset()

    @classmethod
    def get_active_commands(cls, parsed_args):
        """Find active command(s) based on CLI arguments."""
        active_commands = []
        def _collect_active_subcommands(command):
            for subcommand in command.subcommands:
                match_name = getattr(parsed_args, command.subparsers_dest, None)
                if match_name and subcommand.name == match_name:
                    active_commands.append(subcommand)
                _collect_active_subcommands(subcommand)
        if cls.root.func:
            active_commands.append(cls.root)
        _collect_active_subcommands(cls.root)
        return active_commands

    @classmethod
    def fix_command_args(cls, parsed_args, commands):
        """Validate and convert argument data."""
        for command in commands:
            for argument in command.arguments:
                attr_value = getattr(parsed_args, argument.name)
                if attr_value is not None and hasattr(argument, 'fix'):
                    try:
                        setattr(parsed_args, argument.name, argument.fix(attr_value))
                    except (TypeError, ValueError) as exc:
                        cls.add_exception(
                            'Unable to convert argument "{}" value ({})'
                            .format(argument.name, str(attr_value)), exc)

    @classmethod
    def _build_parser_command(cls, parser, command):
        arguments = []
        for argument in command.arguments:
            if not isinstance(argument, _ArgumentBase):
                cls.add_error('Bad argument - not an argument type object: {}'
                              .format(argument))
                continue
            arg_args = argument.option_flags if argument.option_flags else []
            arg_kwargs = {
                key: value
                for key, value in (('dest', argument.name),
                                   ('action', argument.action),
                                   ('type', argument.data_type),
                                   ('metavar', argument.display_name),
                                   ('help', argument.help_text),
                                   ('nargs', argument.quantity),
                                   ('const', argument.constant_value),
                                   ('default', argument.default_value),
                                   ('choices', argument.valid_values),
                                   ('required', argument.mandatory_option))
                if value is not None
            }
            if _Console.is_debug:
                _Console.debug('parser.add_argument({}, {})'
                               .format(arg_args, arg_kwargs))
            try:
                parser.add_argument(*arg_args, **arg_kwargs)
                arguments.append(argument)
            except (ValueError, TypeError) as exc:
                cls.add_exception('Failed to add argument "{}" to parser'
                                  .format(argument.name), exc)

    @classmethod
    def _build_parser_command_tree(cls, parser, command):
        cls._build_parser_command(parser, command)
        if command.subcommands:
            _Console.debug('parser.add_subparsers(dest="{}")'
                           .format(command.subparsers_dest))
            subparsers = parser.add_subparsers(dest=command.subparsers_dest,
                                               required=False)
            for subcommand in command.subcommands:
                _Console.debug('subparsers.add_parser({})'.format(subcommand))
                subparser = None
                try:
                    subparser = subparsers.add_parser(
                        subcommand.name, description=subcommand.description)
                except (ValueError, TypeError) as exc:
                    cls.add_exception('Sub-parser creation exception', exc)
                if subparser:
                    cls._build_parser_command_tree(subparser, subcommand)

    @classmethod
    def build_parser(cls, description, options=None):
        """
        Argparse parser builder.

        Builds root parser and subparsers. Populates options and arguments based
        on a depth-first command tree traversal.
        """
        options = options or CLI.RunOptions()
        # These options have no local implementation, but are provided for
        # convenience because they are common.
        if options.verbose_option:
            cls.root.arguments.append(
                CLI.Boolean('VERBOSE', 'display verbose messages',
                            option_flags=('-v', '--verbose')))
        if options.dry_run_option:
            cls.root.arguments.append(
                CLI.Boolean('DRY_RUN', 'display actions without making changes',
                            option_flags='--dry-run'))
        main_parser = None
        try:
            main_parser = argparse.ArgumentParser(
                description=description,
                formatter_class=argparse.RawDescriptionHelpFormatter,
                add_help=options.help_option,
                epilog=options.notes,
            )
        except (ValueError, TypeError) as exc:
            cls.add_exception('Argument parser creation exception', exc)
        cls.root.description = description
        if main_parser:
            error_count = len(cls.errors)
            cls._build_parser_command_tree(main_parser, cls.root)
            if len(cls.errors) > error_count:
                main_parser = None
        return main_parser

    @classmethod
    def run(cls, description, program_name=None, cli_args=None, payload=None, options=None):
        """Parse command line arguments and invoke appropriate functions."""
        if program_name:
            cls.program_name = program_name
        # Add "help" subcommands as needed.
        if options.help_command:
            cls.register_help_command()
        parser = cls.build_parser(description, options=options)
        options = options or CLI.RunOptions()
        parsed_args = None
        active_commands = None
        if parser:
            _Console.debug('parser.parse_args(args={})'.format(cli_args))
            parsed_args = parser.parse_args(args=cli_args)
            _Console.debug('parsed_args={}'.format(parsed_args))
            # Recursively collect one or two Command objects for @Root and or active @Command.
            active_commands = cls.get_active_commands(parsed_args)
            # Validate and convert argument data.
            if active_commands:
                cls.fix_command_args(parsed_args, active_commands)
        if cls.errors:
            for error in cls.errors:
                _Console.abort(error)
        if cls.start_func:
            cls.start_func()   #pylint: disable=not-callable
        if active_commands:
            for command in active_commands:
                if command.func:
                    func_args = []
                    if payload:
                        func_args.append(payload)
                    command.func(parsed_args, *func_args)
        else:
            cls.print_help(command=cls.root, options=options)

    @classmethod
    def print_help(cls, command=None, options=None):
        """Display command help."""
        command = command or cls.root
        hanging_indent = 20
        sep_space = '  '
        indent = '    '
        max_lhs_width = hanging_indent - len(indent) - len(sep_space)
        fmt_2_line = '%s{}%s%s{}' % (indent, os.linesep, ' ' * hanging_indent)
        option_pairs = []
        argument_pairs = []
        subcommand_pairs = []
        option_width_max = 0
        argument_width_max = 0
        if options and options.help_option:
            lhs = '-h, --help'
            option_width_max = max(len(lhs), option_width_max)
            option_pairs.append((lhs, 'display command help and exit'))
        for argument in command.arguments:
            if argument.option_flags:
                lhs = ', '.join(argument.option_flags) if argument.option_flags else ''
                option_width_max = max(len(lhs), option_width_max)
                option_pairs.append((lhs, argument.help_text))
            else:
                lhs = argument.name
                argument_width_max = max(len(lhs), argument_width_max)
                argument_pairs.append((lhs, argument.help_text))
        for subcommand in command.subcommands:
            subcommand_pairs.append((subcommand.name, subcommand.description))
        _Console.info('USAGE:')
        usage_parts = [cls.program_name]
        if command.name_tuple:
            usage_parts.extend(command.name_tuple)
        if option_pairs:
            usage_parts.append('[OPTION ...]')
        for argument in command.arguments:
            if not argument.option_flags:
                usage_parts.append(argument.get_argument_usage_string())
        if subcommand_pairs:
            usage_parts.append('SUBCOMMAND ...')
        _Console.info('{}{}'.format(indent, ' '.join(usage_parts)))
        if command.description:
            _Console.info('')
            _Console.info('DESCRIPTION:')
            _Console.info('{}{}'.format(indent, command.description))
        def _display_section(caption, pairs):
            if pairs:
                _Console.info('')
                _Console.info('{}:'.format(caption))
                max_width = 0
                for lhs, _rhs in pairs:
                    max_width = max(len(lhs), max_width)
                    if max_width > max_lhs_width:
                        max_width = max_lhs_width
                        break
                fmt_1_line = '%s{:%d}  {}' % (indent, max_width)
                for lhs, rhs in pairs:
                    if len(lhs) > max_lhs_width:
                        _Console.info(fmt_2_line.format(lhs, rhs))
                    else:
                        _Console.info(fmt_1_line.format(lhs, rhs))
        _display_section('ARGUMENT', argument_pairs)
        _display_section('OPTION', option_pairs)
        _display_section('SUBCOMMAND', subcommand_pairs)
        if command.notes:
            _Console.info('')
            _Console.info('NOTES:')
            for line in command.notes.split(os.linesep):
                _Console.info('{}{}'.format(indent, line))


class _ArgumentBase:
    # Base class for argument and option declaration classes.
    #
    # # Arguments
    #
    # ==== input =====  == output ===  === from ====  ======== when =========
    # name              dest           user           required for all
    # action            action         subclass       required for all
    # data_type         type           subclass       required for all
    # help_text         help           user           required for all
    # quantity          nargs          user           option or last argument
    # constant_value    const          user|subclass  appropriate types
    # default_value     default        user|subclass  optional for any
    # valid_values      choices        user|subclass  appropriate types
    # mandatory_option  required       user|subclass  optional for options
    # display_name      metavar        user           optional for any
    # option_flags      flags          user           optional for any
    #
    # # Notes
    #
    # The "output" column has the ArgumentParser.add_argument() argument name.
    #
    # A non-None "option_flags" value converts an argument to an option. It can
    # be a string, tuple, list, or None. All flag individual strings must start
    # with '-' or '--'.
    #
    # Except for (user) arguments, derived classes are responsible for
    # providing and assuring sane combinations of (internal) arguments.
    #
    # # Optional sub-class customization methods:
    #
    # ## prepare(self, is_argument):
    #
    # Adjust argument meta-data before calling ArgumentParser.add_argument().
    #
    # ## fix(self, value) -> final_value (can raise ValueError):
    #
    # Validate and convert an argument value.
    #
    # ## Sub-class customization methods example for "yes"/"no" boolean:
    #
    # def prepare(self, is_argument):
    #     self.action = 'store' if is_argument 'store_true'
    #     self.data_type = str if is_argument else None
    #
    # def fix(self, value):
    #     if value is not None:
    #         if value not in ('yes', 'no'):
    #             raise ValueError('Bad boolean value "%s".' % value)
    #         value = (value == 'yes')
    #     return value

    def __init__(self,
                 name,
                 action,
                 data_type,
                 help_text,
                 quantity=None,
                 constant_value=None,
                 default_value=None,
                 valid_values=None,
                 mandatory_option=None,
                 display_name=None,
                 option_flags=None):
        self.name = name
        self.action = action
        self.data_type = data_type
        self.help_text = help_text
        self.display_name = display_name
        self.quantity = quantity
        self.constant_value = constant_value
        self.default_value = default_value
        self.valid_values = valid_values
        self.mandatory_option = mandatory_option
        self.option_flags = option_flags
        self._check_data()
        self._call_prepare_method()
        super().__init__()

    def _check_data(self):
        # Normalize option_flags to be a list or None.
        have_flags = False
        if not self.option_flags:
            self.option_flags = None
        elif isinstance(self.option_flags, list):
            have_flags = True
        elif isinstance(self.option_flags, str):
            self.option_flags = [self.option_flags]
            have_flags = True
        elif isinstance(self.option_flags, tuple):
            self.option_flags = list(self.option_flags)
            have_flags = True
        else:
            _Registry.add_error(
                'Argument option_flags ({}) is not a string, tuple, or list.'
                .format(self.option_flags))
            self.option_flags = [str(self.option_flags)]
        # Other checks.
        # Some would be caught by argparse, but would result in harder to
        # interpret error messages.
        if not _Constants.name_regex.match(self.name):
            _Registry.add_error('Bad argument name "{}".'.format(self.name))
        if not self.option_flags and self.mandatory_option:
            _Registry.add_error(
                'Non-option "{}" may not use the "mandatory_option" keyword.'
                .format(self.name))
        if (have_flags
                and self.option_flags
                and [s for s in self.option_flags if s[:1] != '-']):
            _Registry.add_error(
                'Argument "{}" option_flags {} must all start with "-".'
                .format(self.name, self.option_flags))
        if self.quantity and not _Constants.quantity_regex.match(self.quantity):
            _Registry.add_error('Bad argument quantity "{}"'.format(self.quantity))

    def get_quantity_min_max(self):
        """Return (min, max) quantity."""
        if self.quantity is None:
            return (1, 1)
        if self.quantity == '?':
            return (0, 1)
        if self.quantity == '+':
            return (1, None)
        if self.quantity == '*':
            return (0, None)
        quantity = int(self.quantity)
        return (quantity, quantity)

    def get_argument_usage_string(self):
        """Return usage string based on argument name and quantity."""
        if self.quantity is None:
            return self.name
        if self.quantity == '?':
            return '[{}]'.format(self.name)
        if self.quantity == '+':
            return '{name} [{name} ...]'.format(name=self.name)
        if self.quantity == '*':
            return '[{} ...]'.format(self.name)
        return ' '.join([':'.join(
            [self.name, str(idx + 1)]) for idx in range(int(self.quantity))])

    def _call_prepare_method(self):
        if hasattr(self, 'prepare'):
            getattr(self, 'prepare')(not self.option_flags)

    def __str__(self):
        return '{}({})'.format(self.__class__.__name__, '\n,   '.join([
            'name={}'.format(self.name),
            'action={}'.format(self.action),
            'data_type={}'.format(self.data_type),
            'help_text={}'.format(self.help_text),
            'display_name={}'.format(self.display_name),
            'quantity={}'.format(self.quantity),
            'constant_value={}'.format(self.constant_value),
            'default_value={}'.format(self.default_value),
            'valid_values={}'.format(self.valid_values),
            'mandatory_option={}'.format(self.mandatory_option),
            'option_flags={}'.format(self.option_flags),
        ]))

class CLI:
    """
    Public classes/functions wrapped in a namespace.

    Avoids excessive namespace pollution.

    This is the recommended import:

        from argdeco import CLI
    """

    class Command:
        """
        Command function decorator for sub-command implementation.

        Positional arguments:
            command_name_or_names  command name string or sequence
            description            command description

        Keyword arguments:
            notes      additional help text displayed near the bottom
            arguments  Arg.XXX instances for global options/arguments

        Sequence command_name_or_names values are used for lower level sub-commands.
        """
        def __init__(self,
                     command_name_or_names,
                     description,
                     notes=None,
                     arguments=None):
            self.command_name_or_names = command_name_or_names
            self.description = description
            self.notes = notes
            self.arguments = arguments

        def __call__(self, func):
            _Registry.register_command(self.command_name_or_names,
                                       self.description,
                                       self.notes,
                                       self.arguments,
                                       func)

    class Root(Command):
        """
        Application root command function decorator.

        Keyword arguments:
            arguments           Arg.XXX instances for global options/arguments

        """
        def __init__(self, arguments=None):
            super().__init__(tuple(), arguments=arguments)

        def __call__(self, func):
            _Registry.register_root(self.arguments, func)

    class Start:
        """
        Start function decorator.

        Called before invoking any command functions.
        """
        def __call__(self, func):
            _Registry.register_start(func)

    class String(_ArgumentBase):
        """String option."""
        def __init__(self, name, help_text,
                     display_name=None,
                     quantity=None,
                     constant_value=None,
                     default_value=None,
                     valid_values=None,
                     mandatory_option=None,
                     option_flags=None):
            super().__init__(name, 'store', str, help_text,
                             display_name=display_name,
                             quantity=quantity,
                             constant_value=constant_value,
                             default_value=default_value,
                             valid_values=valid_values,
                             mandatory_option=mandatory_option,
                             option_flags=option_flags)

    class Integer(_ArgumentBase):
        """Integer option."""
        def __init__(self, name, help_text,
                     display_name=None,
                     quantity=None,
                     constant_value=None,
                     default_value=None,
                     valid_values=None,
                     mandatory_option=None,
                     option_flags=None):
            super().__init__(name, 'store', int, help_text,
                             display_name=display_name,
                             quantity=quantity,
                             constant_value=constant_value,
                             default_value=default_value,
                             valid_values=valid_values,
                             mandatory_option=mandatory_option,
                             option_flags=option_flags)

    class Boolean(_ArgumentBase):
        """Boolean option."""
        def __init__(self, name, help_text,
                     display_name=None,
                     quantity=None,
                     constant_value=None,
                     default_value=None,
                     valid_values=None,
                     mandatory_option=None,
                     option_flags=None):
            super().__init__(name, 'store_true', None, help_text,
                             display_name=display_name,
                             quantity=quantity,
                             constant_value=constant_value,
                             default_value=default_value,
                             valid_values=valid_values,
                             mandatory_option=mandatory_option,
                             option_flags=option_flags)
        def prepare(self, is_argument):
            """Use store/str for arguments and store_true/None for options."""
            if is_argument:
                self.action = 'store'
                self.data_type = str
        def fix(self, value):
            """Validate boolean string and convert to bool."""
            if isinstance(value, bool):
                bvalue = value
            else:
                bvalue = _Registry.string_to_boolean(str(value))
            if bvalue is None:
                raise ValueError('Bad boolean argument value "{}"'.format(value))
            return bvalue

    class RunOptions:
        """
        Additional options for run().

        notes           optional text to be displayed near the bottom of the help screen
        help_command    add "help" command (default is True)
        help_option     add (-h, --help) options (not recommended vs. "help" sub-command)
        verbose_option  add (-v, --verbose) options (VERBOSE) for verbose message display
        dry_run_option  add (--dry-run) option (DRY_RUN), that can be examined by the outer
                        program to avoid running destructive commands
        """
        def __init__(
                self,
                notes=None,
                help_option=False,
                help_command=False,
                verbose_option=False,
                dry_run_option=False,
            ):
            self.notes = notes
            self.help_option = help_option
            self.help_command = help_command
            self.verbose_option = verbose_option
            self.dry_run_option = dry_run_option

    @classmethod
    def run(cls, description, cli_args=None, payload=None, options=None):
        """
        Call once to parse command line and invoke @Command functions.

        Positional arguments:
            description  program description

        Keyword arguments:
            cli_args  command line arguments to use instead of sys.argv
            payload   optional payload object to pass along to call-backs
            options   additional runtime options (as RunOptions object)
        """
        _Console.is_debug = _Registry.string_to_boolean(os.environ.get('ARGDECO_DEBUG', ''))
        _Registry.run(description, cli_args=cli_args, payload=payload, options=options)
