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
Assorted console input/output functions.

Includes functions for multi-level messaging and some simple text mode user
prompts, input, and menus.
"""

import sys
import os
import re
from getpass import getpass
from copy import copy
from collections import OrderedDict

from .flatten import flatten

# Import six if available globally or locally from scriptbase/python
# Python2-3 compatibility helper library.
try:
    import six
except ImportError:
    from .python import six


class Global(object):
    """Global variables."""

    VERBOSE = False
    DEBUG = False
    OUTPUT_STREAM = sys.stdout
    ERROR_STREAM = sys.stderr
    INDENT_STRING = '  '
    MENU_OTHER_MARKER = '...'
    RE_YES_NO = re.compile('[yn]?', re.IGNORECASE)


def set_verbose(verbose):
    """Enable verbose output if True."""
    Global.VERBOSE = verbose


def is_verbose():
    """Return True if verbose output is enabled."""
    return Global.VERBOSE


def set_debug(debug_flag):
    """Enable debug output if debug is True."""
    Global.DEBUG = debug_flag


def is_debug():
    """Return True if debug output is enables."""
    return Global.DEBUG


def set_indentation(indent_string):
    """Set custom message indentation string, the default is 2 blanks."""
    Global.INDENT_STRING = indent_string


def set_streams(output_stream, error_stream):
    """Override output and error streams (stdout and stderr)."""
    Global.OUTPUT_STREAM = output_stream
    Global.ERROR_STREAM = error_stream


def format_strings(templates, symbols=None, tag=None, level=0, split_strings_on=os.linesep):
    """
    Low level message display.

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
        sindent = (level + sublevel) * Global.INDENT_STRING
        yield ''.join([stag, sindent, str(template)])


def format_string(template, symbols=None, tag=None, level=0):
    """Format a single string without splitting on line separators."""
    for out_str in format_strings(template, symbols=symbols, tag=tag, level=level,
                                  split_strings_on=None):
        return out_str


def display_messages(msgs, stream=None, symbols=None, tag=None, level=0):
    """
    Low level message display.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    output_stream = stream if stream else Global.OUTPUT_STREAM
    for msg in format_strings(msgs, symbols=symbols, tag=tag, level=level):
        output_stream.write(msg)
        output_stream.write(os.linesep)


def info(*msgs, **symbols):
    """
    Display informational messages.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    display_messages(msgs, symbols=symbols)


def verbose_info(*msgs, **symbols):
    """
    Display informational messages if verbose output is enabled.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    if Global.VERBOSE:
        display_messages(msgs, symbols=symbols, tag='TRACE')


def debug(*msgs, **symbols):
    """
    Display debug messages.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    if Global.DEBUG:
        display_messages(msgs, symbols=symbols, stream=Global.ERROR_STREAM, tag='DEBUG')


def warning(*msgs, **symbols):
    """
    Display warning messages.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    display_messages(msgs, symbols=symbols, stream=Global.ERROR_STREAM, tag='WARNING')


def error(*msgs, **symbols):
    """
    Display error messages.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    display_messages(msgs, symbols=symbols, stream=Global.ERROR_STREAM, tag='ERROR')


def abort(*msgs, **symbols):
    """
    Display error messages and exit with return code 255.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.

    A special "return_code" symbol is supported to allow the caller to override
    the default return code of 255.
    """
    display_messages(msgs, symbols=symbols, stream=Global.ERROR_STREAM, tag='ERROR')
    Global.ERROR_STREAM.write('ABORT')
    Global.ERROR_STREAM.write(os.linesep)
    sys.exit(symbols.get('return_code', 255))


def header(*msgs, **symbols):
    """
    Display header line.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    line_separator = '=' * 70
    display_messages(['', line_separator])
    display_messages(msgs, level=1, symbols=symbols)
    display_messages([line_separator, ''])


def pause(*msgs, **symbols):
    """
    Display a message and wait for user confirmation to continue.

    Keywords can be expanded using either '%' operator tags, e.g. "%(<name>)s",
    or format() string "{<name>}" tags. Both tag styles will work.
    """
    display_messages([''] + list(msgs), symbols=symbols)
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
    return (prompt_regex('%s (%s)' % (prompt, yes_no), Global.RE_YES_NO, sdef).lower() == 'y')


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
        print('')
        if heading:
            print('::: %s :::' % heading)
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
            print(template % ('[%s]' % choice_id, tag, choice.text))
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


class Context(object):
    """
    Context object holds symbols that can be expanded for output.

    By default this uses format() string expansion.

    Use of this class is preferred to the (deprecated) module level functions.
    """

    def __init__(self, **symbols):
        """Construct with initial symbols, if provided."""
        self.symbols = symbols

    def update(self, **symbols):
        """Add symbols to the context."""
        self.symbols.update(symbols)

    def format_strings(self, msgs, symbols=None, tag=None, split_strings_on=os.linesep):
        """See the module level function for more information."""
        merged_symbols = self._merge_symbols(symbols)
        for out_str in format_strings(msgs, symbols=merged_symbols, tag=tag,
                                      split_strings_on=split_strings_on):
            yield out_str

    def format_string(self, template, symbols=None, tag=None, level=0):
        """Format a single string without splitting on line separators."""
        merged_symbols = self._merge_symbols(symbols)
        return format_string(template, symbols=merged_symbols, tag=tag, level=level)

    def display_messages(self, msgs, stream=None, symbols=None, tag=None):
        """See the module level function for more information."""
        merged_symbols = self._merge_symbols(symbols)
        display_messages(msgs, stream=stream, symbols=merged_symbols, tag=tag)

    def info(self, *msgs, **symbols):
        """See the module level function for more information."""
        self.display_messages(msgs, symbols=symbols)

    def verbose_info(self, *msgs, **symbols):
        """See the module level function for more information."""
        if Global.VERBOSE:
            self.display_messages(msgs, symbols=symbols, tag='TRACE')

    def warning(self, *msgs, **symbols):
        """See the module level function for more information."""
        self.display_messages(msgs, symbols=symbols, stream=Global.ERROR_STREAM, tag='WARNING')

    def error(self, *msgs, **symbols):
        """See the module level function for more information."""
        self.display_messages(msgs, symbols=symbols, stream=Global.ERROR_STREAM, tag='ERROR')

    def abort(self, *msgs, **symbols):
        """See the module level function for more information."""
        merged_symbols = self._merge_symbols(symbols)
        abort(*msgs, **merged_symbols)

    def header(self, *msgs, **symbols):
        """See the module level function for more information."""
        merged_symbols = self._merge_symbols(symbols)
        header(*msgs, **merged_symbols)

    def pause(self, *msgs, **symbols):
        """See the module level function for more information."""
        merged_symbols = self._merge_symbols(symbols)
        pause(*msgs, **merged_symbols)

    def _merge_symbols(self, symbols):
        if not symbols:
            return self.symbols
        merged_symbols = copy(self.symbols)
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
