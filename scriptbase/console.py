#!/usr/bin/env python
#===============================================================================
#===============================================================================
# console
#
# Various console utilities
#
# 02/28/10 - Steve Cooper - author
#===============================================================================
#===============================================================================

import sys
import os
import copy
from . import flatten

"""
Assorted console input/output functions
"""

VERBOSE = False
DEBUG = False
OUTPUT_STREAM = sys.stdout
ERROR_STREAM = sys.stderr
INDENT_STRING = '  '


def set_verbose(verbose):
    global VERBOSE
    VERBOSE = verbose


def is_verbose():
    return VERBOSE


def set_debug(debug):
    global DEBUG
    DEBUG = debug


def is_debug():
    return DEBUG


def set_indentation(indent_string):
    global INDENT_STRING
    INDENT_STRING = indent_string


def set_streams(output_stream, error_stream):
    global OUTPUT_STREAM, ERROR_STREAM
    OUTPUT_STREAM = output_stream
    ERROR_STREAM = error_stream


def display_messages(msgs, kwargs={}, error=False, tag=None, level=0):
    """
    Low level message display.
    """
    f = ERROR_STREAM if error else OUTPUT_STREAM
    stag = '%s: ' % tag if tag else ''
    # Special case to allow a string instead of an iterable.
    try:
        # Raises TypeError if not string
        var = msgs + ' '
        msgs = [msgs]
    except TypeError:
        pass
    # Recursively process message list and sub-lists.
    for sublevel, msg in flatten.flatten(msgs, split_strings_on=os.linesep, vars=kwargs):
        if issubclass(msg.__class__, Exception):
            msg = 'Exception[%s]: %s' % (msg.__class__.__name__, str(msg))
        sindent = (level + sublevel) * INDENT_STRING
        f.write('%s%s%s%s' % (stag, sindent, str(msg), os.linesep))


def info(*msgs, **kwargs):
    display_messages(msgs, kwargs=kwargs)


def verbose_info(*msgs, **kwargs):
    if VERBOSE:
        display_messages(msgs, kwargs=kwargs, tag='INFO2')


def debug(*msgs, **kwargs):
    if DEBUG:
        display_messages(msgs, kwargs=kwargs, error=True, tag='DEBUG')


def warning(*msgs, **kwargs):
    display_messages(msgs, kwargs=kwargs, error=True, tag='WARNING')


def error(*msgs, **kwargs):
    display_messages(msgs, kwargs=kwargs, error=True, tag='ERROR')


def abort(*msgs, **kwargs):
    display_messages(msgs, kwargs=kwargs, error=True, tag='ERROR')
    ERROR_STREAM.write('ABORT%s' % os.linesep)
    sys.exit(255)


def header(*msgs, **kwargs):
    ul = '=' * 70
    display_messages('', ul)
    display_messages(level=1, *msgs, **kwargs)
    display_messages(ul, '')


def pause(*msgs, **kwargs):
    display_messages('', *msgs, **kwargs)
    response = '?'
    while response and response not in ('y', 'yes', 'n', 'no'):
        sys.stdout.write('>>> Continue? (Y|n) ')
        response = sys.stdin.readline().strip().lower()
    if response and response[:1] != 'y':
        abort('Quit')


def input(prompt):
    sys.stdout.write('>>> %s: ' % prompt)
    try:
        return sys.stdin.readline().strip()
    except ValueError:
        pass
    except KeyboardInterrupt:
        sys.stderr.write(os.linesep)
        sys.stderr.write('<BREAK>')
        sys.stderr.write(os.linesep)
        raise


def menu(fixed_choices,
         message = None,
         default = None,
         other   = None,
         test    = None,
         prompt  = 'Choice'):
    if not message:
        message = 'Menu'
    print('')
    print('::: %s :::' % message)
    choices = copy.copy(fixed_choices)
    imax = len(choices)
    iother = None
    if default is not None and isinstance(default, int):
        idefault = default
        default = None
    else:
        idefault = None
    if other is not None:
        choices.append(other + ' ...')
        iother = len(choices)
    if len(choices) == 0:
        abort('No choices available')
    if len(choices) == 1:
        prompt += ' [1]'
        if default is None:
            idefault = 1
    else:
        prompt += ' [1-%d]' % len(choices)
    for i in range(len(choices)):
        choice = choices[i]
        if i+1 == idefault:
            default  = choice
            print('  [%d]*%s' % (i+1, choice))
        elif choice == default:
            idefault = i+1
            print('  [%d]*%s' % (i+1, choice))
        else:
            print('  [%d] %s' % (i+1, choice))
    if idefault is not None:
        prompt += ' (default=%s)' % idefault
    while True:
        s = input(prompt)
        if s:
            try:
                i = int(s)
            except:
                i = -1
            if i > 0 and i <= imax:
                return choices[i-1]
            if i == iother:
                s = input(other)
                if s:
                    other_dir = os.path.realpath(os.path.expanduser(s))
                    if test is None or test(other_dir):
                        return other_dir
        else:
            if default is not None:
                return default
        error('Bad selection')
