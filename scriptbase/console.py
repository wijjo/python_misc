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
import copy
from . import listutil

"""
Assorted console input/output functions
"""

VERBOSE = False
DEBUG = False
OUTPUT_STREAM = sys.stdout
ERROR_STREAM = sys.stderr


def set_verbose(verbose):
    global VERBOSE
    VERBOSE = verbose


def set_debug(debug):
    global DEBUG
    DEBUG = debug


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
    for sublevel, msg in listutil.walk_flattened_split_strings('\n', *msgs, **kwargs):
        sindent = (level + sublevel) * '  '
        # Handle exceptions
        if issubclass(msg.__class__, Exception):
            f.write('%s%s%s Exception: %s\n' % (stag, sindent, msg.__class__.__name__, str(msg)))
        else:
            # Handle multi-line strings
            try:
                # Test that it's a string (raises TypeError if not).
                '' + msg
                # If it is a string slice and dice it by linefeeds.
                for msg2 in msg.split('\n'):
                    f.write('%s%s%s\n' % (stag, sindent, msg2))
            except TypeError:
                # Recursively display an iterable with indentation added.
                if hasattr(msg, '__iter__'):
                    display_messages(msg, kwargs, f=f, tag=tag, level=(level + 1))
                else:
                    for msg2 in str(msg).split('\n'):
                        f.write('%s%s%s\n' % (stag, sindent, msg2))


def info(*msgs, **kwargs):
    display_messages(msgs, kwargs=kwargs)


def is_verbose():
    return VERBOSE

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
    ERROR_STREAM.write('ABORT\n')
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
        sys.stderr.write('\n<BREAK>\n')
        raise


def menu(fixed_choices,
         message = None,
         default = None,
         other   = None,
         test    = None,
         prompt  = 'Choice'):
    if not message:
        message = 'Menu'
    print('\n::: %s :::' % message)
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
