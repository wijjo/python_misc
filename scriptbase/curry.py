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
if sys.version_info < (3,):
    range = xrange

from itertools import chain

"""
Introduction:

  This module provides support for wrapping callables, including methods,
  functions, and objects that implement __call__(), so that a fixed set of
  positional and or keyword arguments are merged into the calls.

  The available objects can be used individually for simple manipulation of of
  call arguments or composed to combine simple manipulations into complex ones.
  Alternatively, the Tweak class supports any combination of manipulations with
  one object.

Curry classes:

  Tweak   any combination of positional and keyword argument manipulations
  Before  insert positional arguments before the incoming ones
  After   append positional arguments after the incoming ones
  Remove  remove positional arguments by index
  Merge   update existing values and or add new keywords/values

Caveats: This implementation does no argument validation against the
expectations of the final callable. Diagnosis of argument-related errors is
complicated by the need to understand how currying affects the calls.

Combining curry operations:

  Nested operations occur left to right, e.g.

    Remove(Before(foo, 'a', 'b'), 0)('c', 'd')

  results in foo('a', 'b', 'd'), not foo('b', 'c', 'd')

  Explanation: Argument tweaks happen before calls, and each of these objects
  is a callable.  The above example calls Remove first with ('c', 'd'). It
  removes argument 0 ('c'), and calls Before with ('c'), which prepends
  ('a', 'b'), resulting in the final call of foo('a', 'b', 'd').

  Recommendation: Use Tweak for complex needs instead of chaining simpler
  operations. It will be more intuitive and efficient.

Compatibility:

  Python 2.x and 3.x
"""


class CurryBase(object):

    def prepare_args(self, args):
        """
        Produces the final positional arguments based on the before, after, and
        remove information specified during construction.
        Override to support custom generation of positional arguments.
        """
        return tuple(args)

    def prepare_kwargs(self, kwargs):
        """
        Produces the final keyword arguments based on the merge and delete
        information specified during construction.
        Override to support custom generation of keyword arguments.
        """
        return dict(kwargs)

    def __call__(self, *args, **kwargs):
        """
        Makes the final call after manipulating the positional and keyword
        arguments as specified during construction.
        """
        return self.call(*self.prepare_args(args), **self.prepare_kwargs(kwargs))


class Tweak(CurryBase):
    """
    Flexible manipulation of call arguments. Serves as the base class for
    simpler one-tweak-at-a-time classes. This class is more verbose, but can
    handle any combination of manipulations with one object.

    Tweak usage example:

    def foo(*args, **kwargs):
        print args, kwargs
    curry_foo = curry.Tweak(foo, before=(-2, -1),
                                 after=(998, 999),
                                 remove=(1, 'x'),
                                 merge={'y': 'yes', 'z': 'no', 2: 'two'})
    curry_foo(1, 'oopsy', 2, x=42, a='aaa', b='bbb')

    Output:
    (-2, -1, 1, 'two', 998, 999) {'a': 'aaa', 'b': 'bbb', 'y': 'yes', 'z': 'no'}
    """

    def __init__(self, call, before=tuple(), after=tuple(), remove=tuple(), merge=dict()):
        """
        Tweak constructor:

        Positional arguments.
          - function, method, or other callable, including layered Tweak-based
            object, to invoke after manipulating positional/keyword arguments

        Keyword arguments:
          before  iterable positional arguments inserted before incoming
          after   iterable positional arguments appended to incoming
          remove  iterable positional index integers and or keyword key names
                  to remove from incoming positional and or keyword arguments
          merge   dictionary of positional index integers and or keyword key
                  names mapped to updated or new argument values
        """
        errors = []
        if not callable(call):
            errors.append('First argument must be callable.')
        for sym in ('before', 'after', 'remove'):
            if not hasattr(locals()[sym], '__iter__'):
                errors.append('"%s" must be iterable.' % sym)
        if not hasattr(merge, '__getitem__'):
            errors.append('"merge" must be a dictionary."')
        if errors:
            raise TypeError('Tweak constructor errors: %s' % ' '.join(errors))
        self.call   = call
        self.before = tuple(before)
        self.after  = tuple(after)
        self.remove = set(remove)
        self.merge  = dict(merge)

    def prepare_args(self, args):
        cargs = chain(self.before, (args[i] for i in range(len(args)) if i not in self.remove), self.after)
        return tuple(cargs)

    def prepare_kwargs(self, kwargs):
        ckwargs = {k: kwargs[k] for k in kwargs if k not in self.remove}
        ckwargs.update(self.merge)
        return ckwargs


class Before(Tweak):
    def __init__(self, call, *before):
        Tweak.__init__(self, call, before=before)


class After(Tweak):
    def __init__(self, call, *after):
        Tweak.__init__(self, call, after=after)


class Remove(Tweak):
    def __init__(self, call, *remove):
        Tweak.__init__(self, call, remove=remove)


class Merge(Tweak):
    def __init__(self, call, **merge):
        Tweak.__init__(self, call, merge=merge)
