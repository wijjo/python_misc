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
import os
import shutil
import re
import inspect

from . import console

# Import six if available globally or locally from scriptbase/python
# Python2-3 compatibility helper library.
try:
    import six
except ImportError:
    from .python import six


RE_RANGE = re.compile('\[([^\]-])-([^\]-])')


# https://gist.github.com/techtonik/2151727/raw/4169b8cccbb0350b709e43d464031616e1b89252/caller_name.py
# Public Domain, i.e. feel free to copy/paste
# Considered a hack in Python 2
def caller_name(skip=2):
    """
    Get a name of a caller in the format module.class.method

    `skip` specifies how many levels of stack to skip while getting caller
    name.  skip=1 means "who calls me", skip=2 "who calls my caller" etc.

    An empty string is returned if skipped levels exceed stack height
    """
    stack = inspect.stack()
    start = 0 + skip
    if len(stack) < start + 1:
      return ''
    parentframe = stack[start][0]

    name = []
    module = inspect.getmodule(parentframe)
    # `modname` can be None when frame is executed directly in console
    # TODO(techtonik): consider using __main__
    if module:
        name.append(module.__name__)
    # detect classname
    if 'self' in parentframe.f_locals:
        # I don't know any way to detect call from the object method
        # XXX: there seems to be no way to detect static method call - it will
        #      be just a function call
        name.append(parentframe.f_locals['self'].__class__.__name__)
    codename = parentframe.f_code.co_name
    if codename != '<module>':  # top level usually
        name.append( codename ) # function or a method
    del parentframe
    return ".".join(name)


def is_string(o):
    return isinstance(o, six.string_types) or isinstance(o, bytes)


def is_iterable(o):
    return hasattr(o, '__iter__')


def is_non_string_sequence(o):
    return is_iterable(o) and not is_string(o)


def expand_ranges(*args):
    """
    Generate the cross-product of strings with embedded ranges written as [x-y].
    If y > x they are traversed in reverse order.
    """
    for a in args:
        m = RE_RANGE.search(a)
        if m:
            o1 = ord(m.group(1))
            o2 = ord(m.group(2))
            expanded = [''.join([a[:m.start(1)-1], chr(o), a[m.end(2)+1:]]) for o in range(o1, o2+1)]
            for s in expand_ranges(*expanded):
                yield s
        else:
            yield a


class DictObject(dict):
    def __getattr__(self, name):
        return self.get(name, None)
    def __setattr__(self, name, value):
        self[name] = value


def pluralize(word, quantity, suffix=None, replacement=None):
    if quantity == 1:
        return word
    if replacement:
        return replacement
    if suffix:
        return '%s%s' % (word, suffix)
    return '%ss' % word


def get_keywords(*names, **kwargs):
    d = DictObject()
    bad = []
    for keyword in kwargs:
        if keyword in names:
            d[keyword] = kwargs[keyword]
        else:
            bad.append(keyword)
    if bad:
        console.error('%s was called with %d bad keyword %s:'
                            % (caller_name(), len(bad), pluralize('argument', len(bad))),
                        ['Caller: %s' % caller_name(3)],
                        ['Bad %s: %s' % (pluralize('keyword', len(bad)), ' '.join(bad))])
    return d


def shlex_quote(arg):
    """
    Return argument quoted as needed for proper shell parsing.
    """
    return six.moves.shlex_quote(arg)


def import_module_path(module_source_path, module_name=None):
    """
    Import module using an explicit source file path.
    """
    if not module_name:
        module_name = '_%s' % '_'.join([s.replace('.', '_') for s in os.path.split(module_source_path)])
    # http://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
    if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 5):
        import importlib.util
        module_spec = importlib.util.spec_from_file_location(module_name, module_source_path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
    else:
        import imp
        module = imp.load_source(module_name, module_source_path)
    return module
