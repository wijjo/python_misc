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
Assorted console input/output functions.

Includes functions for multi-level messaging and some simple text mode user
prompts, input, and menus.
"""

import sys
import os
import re
import inspect
from getpass import getpass
from copy import copy
from collections import OrderedDict

from .flatten import flatten
from .utility import DictObject

# Import six if available globally or locally from scriptbase/python
# Python2-3 compatibility helper library.
try:
    import six
except ImportError:
    from .python import six


class Global(object):
    """Global variables."""
    verbose = False
    debug = False
    output_stream = sys.stdout
    error_stream = sys.stderr
    indent_string = '  '
    re_yes_no = re.compile('[yn]?', re.IGNORECASE)
    abort_exception = False
    header_separator_line = '=' * 70


class FatalError(Exception):
    """Raised by Context.abort() if exceptions are enabled."""


def set_verbose(verbose):
    """Enable verbose output if True."""
    Global.verbose = verbose


def is_verbose():
    """Return True if verbose output is enabled."""
    return Global.verbose


def set_debug(debug_flag):
    """Enable debug output if debug_flag is True."""
    Global.debug = debug_flag


def is_debug():
    """Return True if debug output is enabled."""
    return Global.debug


def set_indentation(indent_string):
    """Set custom message indentation string, the default is 2 blanks."""
    Global.indent_string = indent_string


def set_streams(output_stream, error_stream):
    """Override output and error streams (stdout and stderr)."""
    Global.output_stream = output_stream
    Global.error_stream = error_stream


def format_strings(
        templates,
        symbols=None,
        tag=None,
        level=0,
        split_strings_on=os.linesep,
    ):
    """
    Format message strings.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    stag = '%s: ' % tag if tag else ''
    # Special case to allow a string instead of an iterable.
    if isinstance(templates, (six.string_types, bytes)):
        templates = [templates]
    # Recursively process message list and sub-lists.
    for sublevel, template in flatten(templates, symbols=symbols,
                                      split_strings_on=split_strings_on):
        if issubclass(template.__class__, Exception):
            template = 'Exception[%s]: %s' % (template.__class__.__name__, str(template))
        sindent = Global.indent_string * (level + sublevel)
        yield ''.join([stag, sindent, str(template)])


def format_string(
        template,
        symbols=None,
        tag=None,
        level=0,
    ):
    """Format a single message string without line splitting."""
    for out_str in format_strings(
            template,
            symbols=symbols,
            tag=tag,
            level=level,
            split_strings_on=None,
        ):
        return out_str


def _handle_messages(
        msgs,
        stream=None,
        symbols=None,
        tag=None,
        level=0,
        scope=None,
        fatal=None,
    ):
    """
    Internal low-level message display.

    "scope" values:
        None or 0      always display
        'debug'        verbose mode only
        'verbose'      debug mode only
        tuple or list  multiple scopes, e.g. ('debug', 'verbose')

    "fatal" values:
        None or 0           no action
        Exception subclass  raise provided exception class instance
        1-n                 exit with provided return code
    """
    scopes = [] if not scope else (scope if isinstance(scope, (tuple, list)) else [scope])
    if 'verbose' in scopes and not Global.verbose:
        return
    if 'debug' in scopes and not Global.debug:
        return
    output_stream = stream if stream else Global.output_stream
    msgs = format_strings(msgs, symbols=symbols, tag=tag, level=level)
    for msg in msgs:
        output_stream.write(msg)
        output_stream.write(os.linesep)
    if fatal:
        if inspect.isclass(fatal) and issubclass(fatal, Exception):
            raise fatal(os.linesep.join(list(msgs)))
        try:
            retcode = int(fatal)
        except ValueError:
            Global.error_stream.write('ERROR: Bad "fatal" value: {}'.format(str(fatal)))
            Global.error_stream.write(os.linesep)
            retcode = 255
        Global.error_stream.write('ABORT')
        Global.error_stream.write(os.linesep)
        sys.exit(retcode)
    return msgs


def display_messages(msgs, stream=None, symbols=None, tag=None):
    """
    Flexible message display.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    _handle_messages(msgs, stream=stream, symbols=symbols, tag=tag)


def info(*msgs, **symbols):
    """
    Display informational messages.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    _handle_messages(msgs, symbols=symbols)


def verbose_info(*msgs, **symbols):
    """
    Display informational messages if verbose output is enabled.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    _handle_messages(msgs, symbols=symbols, tag='TRACE', scope='verbose')


def debug(*msgs, **symbols):
    """
    Display debug messages.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    _handle_messages(msgs, symbols=symbols, stream=Global.error_stream,
                     tag='DEBUG', scope='debug')


def warning(*msgs, **symbols):
    """
    Display warning messages.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    _handle_messages(msgs, symbols=symbols, stream=Global.error_stream, tag='WARNING')


def error(*msgs, **symbols):
    """
    Display error messages.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    _handle_messages(msgs, symbols=symbols, stream=Global.error_stream, tag='ERROR')


def abort(*msgs, **symbols):
    """
    Display error messages and exit with return code 255.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.

    A special "return_code" symbol is supported to allow the caller to override
    the default return code of 255.
    """
    fatal = FatalError if Global.abort_exception else symbols.get('return_code', 255)
    _handle_messages(msgs, symbols=symbols, stream=Global.error_stream,
                     tag='ERROR', fatal=fatal)


def header(*msgs, **symbols):
    """
    Display header line.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    _handle_messages(['', Global.header_separator_line])
    _handle_messages(msgs, level=1, symbols=symbols)
    _handle_messages([Global.header_separator_line, ''])


def pause(*msgs, **symbols):
    """
    Display a message and wait for user confirmation to continue.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    _handle_messages([''] + list(msgs), symbols=symbols)
    response = '?'
    while response and response not in ('y', 'yes', 'n', 'no'):
        sys.stdout.write('>>> Continue? (Y|n) ')
        response = six.moves.input().strip().lower()
    if response and response[:1] != 'y':
        abort('Quit')


def prompt_for_text(prompt):
    """Prompt the user for input and return trimmed text."""
    sys.stdout.write('>>> %s: ' % prompt)
    try:
        return six.moves.input().strip()
    except ValueError:
        pass
    except KeyboardInterrupt:
        sys.stderr.write(os.linesep)
        sys.stderr.write('<BREAK>')
        sys.stderr.write(os.linesep)
        raise


def prompt_for_choice(prompt, *choices):
    """
    Prompt the user for multiple choice input.

    Keep prompting until a valid choice is received. Choice shortcuts require
    unique first letters. The user can either respond with a single letter or
    an entire word.
    """
    letters = set()
    choice_list = []
    for choice in choices:
        if not choice:
            abort('Empty choice passed to prompt_for_choice().')
        if choice[0] in letters:
            abort('Non-unique choices %s passed to prompt_for_choice().' % str(choices))
        letters.add(choice[0])
        choice_list.append('[%s]%s' % (choice[0], choice[1:]))
    while True:
        sys.stdout.write('%s (%s) ' % (prompt, '/'.join(choice_list)))
        sys.stdout.flush()
        response = six.moves.input().strip()
        if response in letters or response in choices:
            return response[0]


def prompt_regex(prompt, compiled_regex, default):
    """
    Prompt for a response that must match a regular expression.

    Re-prompt when it doesn't match.
    Return the response when it matches.
    """
    while True:
        sys.stdout.write('%s: ' % prompt)
        try:
            user_text = six.moves.input().strip()
            if compiled_regex.match(user_text):
                if not user_text:
                    return default
                return user_text
            error('bad input - try again')
        except KeyboardInterrupt:
            abort('', 'Keyboard interrupt')

def prompt_yes_no(prompt, default=False):
    """
    Prompt for a yes/no response.

    The boolean default value substitutes for an empty response.

    Return a boolean value when the response matches 'y', 'n', or empty.
    """
    if default:
        yes_no = 'Y/n'
        sdef = 'y'
    else:
        yes_no = 'y/N'
        sdef = 'n'
    return (prompt_regex('%s (%s)' % (prompt, yes_no), Global.re_yes_no, sdef).lower() == 'y')


class MenuChoice(object):
    """Simple text menu choice."""

    def __init__(self, text, user_input, input_checker):
        """Menu choice constructor."""
        self.text = text
        self.user_input = user_input
        self.input_checker = input_checker


class Menu(object):
    """Simple text menu."""

    def __init__(self):
        """Menu constructor."""
        self.choices = OrderedDict()
        # Choice IDs do not have to be integers, but when none is provided the
        # next sequential integer is used.
        self.next_integer_choice_id = 1
        self.default_choice_id = None

    def _add_item(self, choice_id, text, user_input, input_checker):
        # Provide an incremented integer (as string) when no choice ID is provided.
        if choice_id is None:
            choice_id = self.next_integer_choice_id
            self.next_integer_choice_id += 1
        # Normalize choice IDs to be strings.
        choice_id_key = str(choice_id)
        if choice_id_key in self.choices:
            # Ignore duplicate choice IDs.
            error('Menu choice ID "%s" was used more than once.' % choice_id_key)
        self.choices[choice_id_key] = MenuChoice(text, user_input, input_checker)
        # Support chaining
        return self

    def item(self, text, choice_id=None):
        """Add a menu choice."""
        # Support chaining
        return self._add_item(choice_id, text, False, None)

    def user_item(self, text, choice_id=None, checker=None):
        """
        Add a menu item with a value to be provided by the user.

        The checker argument, if provided, must be a call-back function which
        receives the value and returns True if the value is good.
        """
        # Support chaining
        return self._add_item(choice_id, text, True, checker)

    def default(self, choice_id):
        """Set the default choice ID."""
        self.default_choice_id = choice_id
        # Support chaining
        return self

    def invoke(self, prompt='Selection', heading='Menu'):
        """
        Prompt for an integer selection from a menu of choices.

        Use the default selection, if any, when no input is given.

        Re-prompt on bad or out of range selections or on empty input when
        there is no default selection.

        Return a (selection_number, item_text) pair.
        """
        if not self.choices:
            error('No menu choices were provided.')
            return None
        sys.stdout.write(os.linesep)
        if heading:
            sys.stdout.write('::: {} :::{}'.format(heading, os.linesep))
        prompt_parts = [prompt]
        default_choice_id = self.default_choice_id
        if default_choice_id is not None:
            if default_choice_id in self.choices:
                prompt_parts.append(' (default=[%s])' % default_choice_id)
            else:
                error('Bad default choice ID "%s".' % default_choice_id)
                default_choice_id = None
        max_key_width = max([len(choice_id) for choice_id in self.choices.keys()])
        max_tag_width = 1 if default_choice_id is not None else 0
        template = '  %%%ds%%%ds %%s' % (max_key_width + 2, max_tag_width)
        for choice_id, choice in self.choices.items():
            tag = '*' if choice_id == default_choice_id else ''
            sys.stdout.write(template % ('[{}]'.format(choice_id), tag, choice.text))
        return self._get_choice(''.join(prompt_parts), default_choice_id)

    def _get_choice(self, prompt, default_choice_id):
        while True:
            user_choice_id = prompt_for_text(prompt)
            if not user_choice_id and default_choice_id is not None:
                user_choice_id = default_choice_id
            if user_choice_id:
                if user_choice_id in self.choices:
                    user_choice = self.choices[user_choice_id]
                    if user_choice.user_input:
                        value = prompt_for_text(user_choice.text)
                        if value:
                            return (user_choice_id, value)
                    else:
                        return (user_choice_id, user_choice.text)
            error('Bad choice')


class Context(DictObject):
    """
    Context object holds symbols that can be expanded for output.

    By default this uses format() string expansion.

    Use of this class is preferred to the (deprecated) module level functions.

    It can be used in a "with" statement as a context manager.
    """

    def __init__(self, *args, **kwargs):
        self._level = 0
        self._pending_msgs = []
        self._sub_ctxs = []
        self._abort_exception = Global.abort_exception
        super().__init__(*args, **kwargs)

    def __enter__(self):
        pass

    def __exit__(self, exc_tupe, exc_val, exc_tb):
        self.flush()
        return False

    def set_abort_exception(self, enabled):
        """Use exception for abort() if True, otherwise sys.exit()."""
        self._abort_exception = enabled

    def flush(self):
        """Flush pending output, e.g. for tree display."""
        if self._level == 0 and (self._pending_msgs or self._sub_ctxs):
            pass

    def set_level(self, level):
        """Set indentation level."""
        self._level = level

    def subcontext(self, **symbols):
        """A sub-context indents displayed messaged and inherits symbols."""
        sub_ctx = Context(self, **symbols)
        sub_ctx.set_level(self._level + 1)
        sub_ctx.set_abort_exception(self._abort_exception)
        self._sub_ctxs.append(sub_ctx)
        return sub_ctx

    def format_strings(
            self,
            msgs,
            symbols=None,
            tag=None,
            split_strings_on=os.linesep,
        ):
        """See the module level function for more information."""
        return format_strings(msgs,
                              symbols=self._merge_symbols(symbols),
                              tag=tag,
                              split_strings_on=split_strings_on)

    def format_string(self, template, symbols=None, tag=None):
        """Format a single string without splitting on line separators."""
        return format_string(template,
                             symbols=self._merge_symbols(symbols),
                             tag=tag,
                             level=self.level)

    def display_messages(self, msgs, stream=None, symbols=None, tag=None):
        """See the module level function for more information."""
        _handle_messages(msgs,
                         stream=stream,
                         symbols=self._merge_symbols(symbols),
                         tag=tag,
                         level=self._level)

    def info(self, *msgs, **symbols):
        """See the module level function for more information."""
        _handle_messages(msgs,
                         symbols=self._merge_symbols(symbols),
                         level=self._level)

    def debug(self, *msgs, **symbols):
        """See the module level function for more information."""
        _handle_messages(msgs,
                         symbols=self._merge_symbols(symbols),
                         tag='DEBUG',
                         level=self._level,
                         scope='debug')

    def verbose_info(self, *msgs, **symbols):
        """See the module level function for more information."""
        _handle_messages(msgs,
                         symbols=self._merge_symbols(symbols),
                         tag='TRACE',
                         level=self._level,
                         scope='verbose')

    def warning(self, *msgs, **symbols):
        """See the module level function for more information."""
        _handle_messages(msgs,
                         stream=Global.error_stream,
                         symbols=self._merge_symbols(symbols),
                         tag='WARNING',
                         level=self._level)

    def error(self, *msgs, **symbols):
        """See the module level function for more information."""
        _handle_messages(msgs,
                         stream=Global.error_stream,
                         symbols=self._merge_symbols(symbols),
                         tag='ERROR',
                         level=self._level)

    def abort(self, *msgs, **symbols):
        """See the module level function for more information."""
        fatal = FatalError if self._abort_exception else symbols.get('return_code', 255)
        _handle_messages(msgs,
                         stream=Global.error_stream,
                         symbols=self._merge_symbols(symbols),
                         tag='ERROR',
                         level=self._level,
                         fatal=fatal)

    def header(self, *msgs, **symbols):
        """See the module level function for more information."""
        _handle_messages(['', Global.header_separator_line])
        _handle_messages(msgs, level=1, symbols=self._merge_symbols(symbols))
        _handle_messages([Global.header_separator_line, ''])

    def pause(self, *msgs, **symbols):
        """See the module level function for more information."""
        pause(*msgs, **self._merge_symbols(symbols))

    def _merge_symbols(self, symbols):
        if not symbols:
            return self
        merged_symbols = copy(self)
        merged_symbols.update(symbols)
        return merged_symbols


class PasswordProvider(object):
    """Class used to receive and cache a password on demand."""

    def __init__(self, dry_run=False):
        """Constructor with call-back and messages for display."""
        self.message = 'A password is required.'
        self.password = None
        if dry_run:
            self.password = 'PASSWORD'

    @classmethod
    def get_password(cls):
        """Get password from user."""
        return getpass('Password: ')

    def __call__(self):
        """
        Emulate a function to get the password once.

        Provide a cached copy after the first call.
        """
        if self.password is None:
            if self.message:
                info(self.message)
            self.password = self.get_password()
        return self.password
