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

"""
This module provides support for wrapping callables, including methods,
functions, and objects that implement __call__(), so that a fixed set of
positional and or keyword arguments are merged into the calls.

Caveats: This implementation does no argument validation. Diagnosis of
argument-related errors is complicated by the need to understand how currying
affects the calls.

It is compatible with Python 2.x and 3.x
"""

class Curry(object):
    """
    Curry usage example:

    def foo(*args, **kwargs):
        return args, kwargs
    curry_foo = Curry(foo, before=(-2, -1), after=(998, 999), keywords=dict(x='yes', y='no'))

    print curry_foo()
    print curry_foo(1, 2, a='aaa', b='bbb')

    Output:

    (-2, -1, 998, 999) {'x': 'yes', 'y': 'no'}
    (-2, -1, 1, 2, 998, 999) {'a': 'aaa', 'b': 'bbb', 'x': 'yes', 'y': 'no'}

    """

    def __init__(self, callable_obj, before=tuple(), after=tuple(), keywords=dict()):
        """
        The constructor takes a callable, position arguments to insert or
        append, and keyword arguments to merge. Note that callable_obj can also
        be a Curry object, to allow more than one layer of currying.
        """
        if not callable(callable_obj):
            raise ArgumentError('Curry() requires a callable as the first argument.')
        self.callable_obj = callable_obj
        self.before = before
        self.after = after
        self.keywords = keywords

    def prepare_positional_arguments(self, args):
        """
        Method to prepend "before" and append "after" arguments. Override to
        support custom generation of positional arguments.
        """
        return self.before + args + self.after

    def prepare_keyword_arguments(self, kwargs):
        """
        Method to merge with curried keyword arguments.  Override to support
        custom generation of keyword arguments.
        """
        curried_kwargs = self.keywords.copy()
        curried_kwargs.update(kwargs)
        return curried_kwargs

    def __call__(self, *args, **kwargs):
        """
        Makes the final call after injecting the positional and keyword
        arguments as specified at construction time.
        """
        curried_args = self.prepare_positional_arguments(args)
        curried_kwargs = self.prepare_keyword_arguments(kwargs)
        return self.callable_obj(*curried_args, **curried_kwargs)

import unittest

class TestCurry(unittest.TestCase):
    def test_all(self):
        def foo(*a, **k):
            return a, k
        a, k = foo(1, 2, 3, a=1, b=2, c=3)
        self.assertEqual(a, (1, 2, 3))
        self.assertEqual(k, dict(a=1, b=2, c=3))
        curry_foo_1 = Curry(foo, after=(10, 11, 12), keywords=dict(n=11, o=12, p=13))
        a, k = curry_foo_1(1, 2, 3, a=1, b=2, c=3)
        self.assertEqual(a, (1, 2, 3, 10, 11, 12))
        self.assertEqual(k, dict(a=1, b=2, c=3, n=11, o=12, p=13))
        curry_foo_2 = Curry(curry_foo_1, before=(100, 101, 102), keywords=dict(x=101, y=102, z=103))
        a, k = curry_foo_2(1, 2, 3, a=1, b=2, c=3)
        self.assertEqual(a, (100, 101, 102, 1, 2, 3, 10, 11, 12))
        self.assertEqual(k, dict(a=1, b=2, c=3, n=11, o=12, p=13, x=101, y=102, z=103))

if __name__ == '__main__':
    unittest.main()
