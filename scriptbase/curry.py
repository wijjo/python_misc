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

"""
Call argument currying helper.

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

import os

# Import six if available globally or locally from scriptbase/python
# Python2-3 compatibility helper library.
try:
    import six
except ImportError:
    from .python import six


class CurryBase(object):
    """Call argument currying base class."""

    def __init__(self, call):
        """Construct with a callable."""
        self.call = call

    def curry_positional_arguments(self, call_time_args):                     #pylint: disable=no-self-use
        """
        Required method to prepare positional arguments for currying.

        Produce the final positional arguments based on the before, after, and
        remove information specified during construction.

        Override to support custom generation of positional arguments.
        """
        return tuple(call_time_args)

    def curry_keyword_arguments(self, call_time_kwargs):                 #pylint: disable=no-self-use
        """
        Required method to prepare keyword arguments for currying.

        Produce the final keyword arguments based on the merge and delete
        information specified during construction.

        Override to support custom generation of keyword arguments.
        """
        return dict(call_time_kwargs)

    def __call__(self, *call_time_args, **call_time_kwargs):
        """
        Make the final curried call.

        First manipulate the positional and keyword arguments as specified
        during construction.
        """
        return self.call(*self.curry_positional_arguments(call_time_args),
                         **self.curry_keyword_arguments(call_time_kwargs))


class Tweak(CurryBase):
    """
    Flexible manipulation of call arguments.

    Serves as the base class for simpler one-tweak-at-a-time classes. This
    class is more verbose, but can handle any combination of manipulations with
    one object.

    Tweak usage example:

    def foo(*args, **kwargs):
        print args, kwargs
    curry_foo = (curry.Tweak(foo)
                 .before(-2, -1)
                 .after(998, 999)
                 .remove(1, 'x')
                 .merge({2: 'two'})
                 .merge(y='yes','z='no'))
    curry_foo(1, 'oopsy', 2, x=42, a='aaa', b='bbb')

    Output: (-2, -1, 1, 'two', 998, 999) {'a': 'aaa', 'b': 'bbb', 'y': 'yes',
    'z': 'no'}
    """

    def __init__(self, call):
        """
        Tweak constructor.

        The call argument may be a function, method, or other callable,
        including a layered Tweak-drived object, to invoke after manipulating
        positional/keyword arguments
        """
        self.to_prepend = []
        self.to_append = []
        self.to_remove = set()
        self.to_merge = {}
        CurryBase.__init__(self, call)

    def before(self, *args_to_prepend):
        """Add arguments to be prepended at call time."""
        self.to_prepend.extend(args_to_prepend)
        # Chainable call.
        return self

    def after(self, *args_to_append):
        """Add arguments to be appended at call time."""
        self.to_append.extend(args_to_append)
        # Chainable call.
        return self

    def remove(self, *arg_ids_to_remove):
        """
        Specify argument numbers to be removed at call time.

        The arg_ids_to_remove variable argument list can have zero-based
        positional call-time argument indexes or keyword argument names.
        """
        for arg_id in arg_ids_to_remove:
            self.to_remove.add(arg_id)
        # Chainable call.
        return self

    def merge(self, *dict_args_to_merge, **kwargs_to_merge):
        """
        Add keyword arguments to be merged at call time.

        It supports arguments that are similar to dict.update(), except that
        instead of a single optional dictionary initializer it accepts any
        number of dictionary initializers.

        Like dict.update(), it also accepts any number of keyword arguments.

        The dictionary initializer positional arguments are useful for passing
        entire dictionaries without the "**" operator and for inline
        dictionaries with key names that are not valid Python identifiers.
        Numeric keys are treated as positional argument indexes.

        Multiple positional dictionary initializer arguments are merged in
        order. Keyword arguments are merged last. The last merged value for a
        particular key is the one that is finally used.
        """
        for dict_arg in dict_args_to_merge:
            self.to_merge.update(dict_arg, **kwargs_to_merge)
        if kwargs_to_merge:
            self.to_merge.update(**kwargs_to_merge)
        # Chainable call.
        return self

    def curry_positional_arguments(self, call_time_args):
        """Prepare curried positional arguments."""
        def _prepare():
            for arg in self.to_prepend:
                yield arg
            for arg_index, arg in enumerate(call_time_args):
                if arg_index not in self.to_remove:
                    yield arg
            for arg in self.to_append:
                yield arg
        return tuple(_prepare())

    def curry_keyword_arguments(self, call_time_kwargs):
        """Prepare curried keyword arguments."""
        ret_kwargs = {
            key: value
            for key, value in six.iteritems(call_time_kwargs)
            if key not in self.to_remove
        }
        ret_kwargs.update({
            key: value
            for key, value in six.iteritems(self.to_merge)
        })
        return ret_kwargs

    def __str__(self):
        """String conversion magic method for debugging."""
        return (os.linesep.join([
            '::%s::' % self.__class__.__name__,
            '  to_prepend=%s' % self.to_prepend,
            '  to_append=%s' % self.to_append,
            '  to_remove=%s' % self.to_remove,
            '  to_merge=%s' % self.to_merge,
        ]))


class Before(Tweak):
    """Tweak call by inserting arguments before."""

    def __init__(self, call, *args_to_prepend):
        """Constructor."""
        Tweak.__init__(self, call)
        self.before(*args_to_prepend)


class After(Tweak):
    """Tweak call by inserting arguments after."""

    def __init__(self, call, *args_to_append):
        """Constructor."""
        Tweak.__init__(self, call)
        self.after(*args_to_append)


class Remove(Tweak):
    """Tweak call by removing arguments."""

    def __init__(self, call, *arg_ids_to_remove):
        """Constructor."""
        Tweak.__init__(self, call)
        self.remove(*arg_ids_to_remove)


class Merge(Tweak):
    """Tweak call by merging keyword arguments."""

    def __init__(self, call, *dict_args_to_merge, **kwargs_to_merge):
        """Constructor."""
        Tweak.__init__(self, call)
        self.merge(*dict_args_to_merge, **kwargs_to_merge)
