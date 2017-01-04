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

class DotDict(object):

    # Choose slot names to hopefully avoid conflicts with user attribute names.
    __slots__ = ('_value_', '_children_')

    '''
    DotDict is a multi-level in-memory key/value store with dictionary and
    attribute access mechanisms. Memory is conserved by using Python slots.

    Dictionary-style access allows chained indexing, e.g. d[key1][key2]... .

    Attribute-style access uses dot-separated names, e.g. d.key1.key2... .

    Keys can be anything, including non-strings, but any keys that are not
    valid Python symbols must be accessed using dictionary style indexing.

    Each level's entry can have a value and or child DotDict entries. Call
    syntax is supported for reading and writing entry values. Assignment can
    also be used to write entry values. Here are some examples.

        dotdict.key1.key2(value)
        dotdict[key1][key2](value)
        dotdict.key1.key2 = value
        dotdict[key1][key2] = value
        value = dotdict.key1.key2(value)
        value = dotdict[key1][key2](value)

    The overloaded call syntax is what allows entries to have both child
    entries and a value. It doesn't encroach on the dictionary/attribute symbol
    space, because the value is not accessed by name and because named
    read/write methods aren't required.

    Remember that the object received directly from an index or attribute is a
    DotDict, not a value. A call is required on that object to get the value.
    This will be a common mistake.

    Examples:

        d = DotDict()

        Set the value of a top level item:
            d['a'](1)
            d['a'] = 1
            d.a(1)
            d.a = 1
            da = d.a
            da(1)
            da = 1

        Set the value of a lower level item:
            d['a']['b'](1)
            d['a']['b'] = 1
            d.a.b(1)
            d.a.b = 1
            dab = d.a.b
            dab(1)
            dab = 1

        Get the value of a top level item:
            x = d['a']()
            x = d.a()
            da = d.a
            x = da()

        Get the value of a lower level item:
            x = d['a']['b']()
            x = d.a.b()

        Mix attribute and indexed access for names that are invalid tokens.
            x = d.a[':x:']()
            d.a[':x:'](1)
    '''

    def __init__(self):
        '''
        Constructor initializes private data slots.
        '''
        object.__setattr__(self, '_value_', None)
        object.__setattr__(self, '_children_', None)

    def __getitem__(self, key):
        '''
        Returns a DotDict so that children can be added or accessed.
        '''
        if self._children_ is None:
            object.__setattr__(self, '_children_', {})
        return self._children_.setdefault(key, DotDict())

    def __setitem__(self, key, value):
        '''
        Item setter is overloaded to set the value. This is a convenience and
        provides an alternative to using function call syntax.
        '''
        self.__getitem__(key)(value)

    def __getattr__(self, key):
        '''
        Attribute getter uses the overloaded __getitem__() method to return a
        DotDict for the entry.
        '''
        return self.__getitem__(key)

    def __setattr__(self, key, value):
        '''
        Attribute setter is overloaded to set the value. This is a convenience
        and provides an alternative to using function call syntax.
        '''
        self.__getitem__(key)(value)

    def __str__(self):
        '''
        Recursely generate a string for the current entry and its children.
        '''
        lines = ['value=%s' % str(self._value_)]
        if self._children_:
            for key in sorted(self._children_.keys()):
                lines.append('%s:' % key)
                lines.extend(['  %s' % s for s in str(self._children_.get(key)).split(os.linesep)])
        return os.linesep.join(lines)

    def __call__(self, *args):
        '''
        DotDict function calls return the entry value when there is no argument
        or set the value when there is precisely one. Any other argument
        quantity results in an exception.
        '''
        if not args:
            return self._value_
        if len(args) == 1:
            object.__setattr__(self, '_value_', args[0])
        else:
            raise TypeError('DotDict() takes at most 1 positional argument '
                                'but %d were given' % len(args))
