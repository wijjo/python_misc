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

"""Various utility functions and classes."""

import sys
import os
import re
import inspect
import glob
import bisect
from contextlib import contextmanager

# Import six if available globally or locally from scriptbase/python
# Python2-3 compatibility helper library.
try:
    import six
except ImportError:
    from .python import six


RE_RANGE = re.compile(r'\[([^\]-])-([^\]-])')
TRUE_STRINGS = ('true', 't', 'yes', 'y', '1')
FALSE_STRINGS = ('false', 'f', 'no', 'n', '0')


# https://gist.github.com/techtonik/2151727/raw/4169b8cccbb0350b709e43d464031616e1b89252/caller_name.py
# Public Domain, i.e. feel free to copy/paste
# Considered a hack in Python 2
def caller_name(skip=2):
    """
    Get a name of a caller in the format module.class.method.

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
    # (techtonik): consider using __main__
    if module:
        name.append(module.__name__)
    # detect classname
    if 'self' in parentframe.f_locals:
        # I don't know any way to detect call from the object method.
        # There seems to be no way to detect static method call -
        # it will be just a function call.
        name.append(parentframe.f_locals['self'].__class__.__name__)
    codename = parentframe.f_code.co_name
    if codename != '<module>':  # top level usually
        name.append(codename) # function or a method
    del parentframe
    return ".".join(name)


def is_string(value):
    """Return True if the object is a string type."""
    return isinstance(value, (six.string_types, bytes))


def make_list(item_or_sequence):
    """Coerce a sequence or non-sequence to a list."""
    if isinstance(item_or_sequence, list):
        return item_or_sequence
    if isinstance(item_or_sequence, tuple):
        return list(item_or_sequence)
    return [item_or_sequence]

def is_iterable(value):
    """Return True if the object is an iterable type."""
    return hasattr(value, '__iter__')


def is_non_string_sequence(value):
    """Return True if the object is an iterable type other than a string."""
    return is_iterable(value) and not is_string(value)


def format_sequence(seq, *positional_args, **keyword_args):
    """
    Format sequence items using provided positional and keyword arguments.

    Return a list or tuple sequence, depending on the input type.
    """
    if isinstance(seq, list):
        return [str(item).format(*positional_args, **keyword_args) for item in seq]
    return (str(item).format(*positional_args, **keyword_args) for item in seq)


def expand_ranges(*args):
    """
    Generate the cross-product of strings with embedded ranges written as [x-y].

    If y > x they are traversed in reverse order.
    """
    for arg in args:
        matched = RE_RANGE.search(arg)
        if matched:
            ord1 = ord(matched.group(1))
            ord2 = ord(matched.group(2))
            expanded = [''.join([arg[:matched.start(1)-1], chr(o), arg[matched.end(2)+1:]])
                        for o in range(ord1, ord2+1)]
            for exp_str in expand_ranges(*expanded):
                yield exp_str
        else:
            yield arg


class DictObject(dict):
    """Dictionary with read/write element access as attributes."""

    def __getattr__(self, name):
        """Read access to elements as attributes."""
        return self.get(name, None)

    def __setattr__(self, name, value):
        """Write access to elements as attributes."""
        self[name] = value

    def format(self, template, *args, **kwargs):
        """Format string using members and arguments."""
        kwargs2 = {}
        kwargs2.update(self, **kwargs)
        return template.format(*args, **kwargs2)


def pluralize(word, quantity, suffix=None, replacement=None):
    """Simplistic heuristic word pluralization."""
    if quantity == 1:
        return word
    if replacement:
        return replacement
    if suffix:
        return '%s%s' % (word, suffix)
    return '%ss' % word


def shlex_quote(value):
    """Return argument quoted as needed for proper shell parsing."""
    str_value = str(value)
    return six.moves.shlex_quote(str_value) #pylint: disable=too-many-function-args


def range_iter(*args, **kwargs):
    """Python 2/3-compatible front end to range/xrange."""
    if sys.version_info < (3,):
        return xrange(*args, **kwargs)      #pylint: disable=undefined-variable
    return range(*args, **kwargs)


def import_module_path(module_source_path, module_name=None):
    """Import module using an explicit source file path."""
    if not module_name:
        module_name = '_%s' % '_'.join(
            [s.replace('.', '_') for s in os.path.split(module_source_path)])
    # http://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
    #pylint:disable=import-outside-toplevel
    if sys.version_info.major == 2:
        import imp
        module = imp.load_source(module_name, module_source_path)
    elif sys.version_info.major == 3:
        if sys.version_info.minor >= 5:
            import importlib.util
            spec = importlib.util.spec_from_file_location(module_name, module_source_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            from importlib.machinery import SourceFileLoader
            module_loader = SourceFileLoader(module_name, module_source_path)
            module = module_loader.load_module()    #pylint: disable=deprecated-method,no-value-for-parameter
    else:
        sys.stderr.write('Python %d is not supported.' % sys.version_info.major)
        sys.stderr.write(os.linesep)
        sys.exit(255)
    return module


def import_modules_from_directory(dir_path):
    """Import all modules in a directory."""
    module_paths = sorted([p for p in glob.glob(os.path.join(dir_path, '*.py'))])
    modules = DictObject()
    for module_path in module_paths:
        module_name = os.path.splitext(os.path.basename(module_path))[0]
        modules[module_name] = import_module_path(module_path, module_name=module_name)
    return modules


def generate_one_or_none(generator, enforce=True):
    """
    Return first item from a generator.

    Optionally check that nothing else was generated.

    Return None if nothing was generated.
    """
    result = None
    for item in generator:
        result = item
        break
    if enforce:
        for item in generator:
            raise RuntimeError('Generator "%s" had more than one item.' % generator.__name__)
    return result


# http://stackoverflow.com/questions/212358/binary-search-bisection-in-python
def binary_search(array, search_for, pos_low=0, pos_high=None):
    """Perform binary search on an array."""
    pos_high = pos_high if pos_high is not None else len(array)
    pos = bisect.bisect_left(array, search_for, pos_low, pos_high)
    return (pos if pos != pos_high and array[pos] == search_for else -1)


@contextmanager
def working_directory_context(directory):
    """Temporarily change the working directory (in a "with" block)."""
    save_directory = os.getcwd()
    os.chdir(directory)
    yield
    os.chdir(save_directory)


def string_to_boolean(svalue, default=None):
    """Convert string to True, False, default value, or None."""
    if svalue.lower() in TRUE_STRINGS:
        return True
    if svalue.lower() in FALSE_STRINGS:
        return False
    return default


def object_repr(instance, exclude=None):
    """Format class instance repr() string."""
    exclude = exclude or []
    def _format_value(value):
        if isinstance(value, str):
            return "'{}'".format(value)
        if inspect.isfunction(value):
            return '{}()'.format(value.__name__)
        return repr(value)
    return '{}({})'.format(
        instance.__class__.__name__,
        ', '.join(['{}={}'.format(k, _format_value(getattr(instance, k)))
                   for k in sorted(instance.__dict__.keys())
                   if not k.startswith('_') and k not in exclude]))


class DumpableObject:
    """Mix-in class for attaching member-dumping __repr__ and __str__ methods."""
    def __init__(self, exclude=None):
        self._dumpable_exclude = exclude
    def __repr__(self):
        return object_repr(self, exclude=self._dumpable_exclude)
    def __str__(self):
        return object_repr(self, exclude=self._dumpable_exclude)
