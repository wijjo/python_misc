#!/usr/bin/env python

import sys


class G:
    verbose = False
    debug = False


def set_verbose(verbose):
    G.verbose = verbose


def set_debug(debug):
    G.debug = debug


def display_messages(msgs, f=sys.stdout, tag=None, level=0):
    """
    Low level message display.
    """
    if tag:
        stag = '%s: ' % tag
    else:
        stag = ''
    # Special case to allow a string instead of an iterable.
    try:
        # Raises TypeError if not string
        var = msgs + ' '
        msgs = [msgs]
    except TypeError:
        pass
    sindent = level * '  '
    # Recursively process message list and sub-lists.
    for msg in msgs:
        if msg is not None:
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
                        display_messages(msg, f=f, tag=tag, level=level + 1)
                    else:
                        for msg2 in str(msg).split('\n'):
                            f.write('%s%s%s\n' % (stag, sindent, msg2))


def info(*msgs):
    display_messages(msgs, tag='INFO')


def is_verbose():
    return G.verbose

def verbose_info(*msgs):
    if G.verbose:
        display_messages(msgs, tag='INFO2')


def debug(*msgs):
    if G.debug:
        display_messages(msgs, tag='DEBUG')


def warning(*msgs):
    display_messages(msgs, tag='WARNING')


def error(*msgs):
    display_messages(msgs, tag='ERROR')


def abort(*msgs):
    display_messages(msgs, tag='ABORT')
    sys.exit(1)
