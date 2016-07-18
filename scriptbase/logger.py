# Copyright 2016 Steven Cooper
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

import sys
from . import listutil

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
    sindent = level * '  '
    # Recursively process message list and sub-lists.
    for msg in listutil.flatten_split_strings('\n', *msgs, **kwargs):
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
                    display_messages(msg, kwargs, f=f, tag=tag, level=level + 1)
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
    sys.exit(1)
