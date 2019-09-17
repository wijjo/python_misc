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
pspace -- Property storage and access through scoped spaces.

Description
===========

Provides storage and access to property values addressed by dot-separated
compound keys.

Properties
==========

Properties are an abstract concept defined as a value stored at an address in a
property store, and accessed through property spaces (see next section).

A property value can be an arbitrary data type, including None.

Property Stores
===============

A property store contains properties. The property store class must be derived
from PropertyStoreBase and implement the required methods.

The default property store class (PropertyStoreBase derivative) is
SortedDictPropertyStore. Its implementation uses a dict with a separate sorted
key list that gets create on demand when needed for ordered iteration.

Property Spaces
===============

A property space, or simply "space", is a viewport into all or part of a
property store. It has a base address that can restrict it to a subset of
property addresses. Addresses passed to a space are treated as relative
addresses that get appended to the base address. It can further restrict the
visible subset through the application of optional filters.

Property spaces are implemented as PSpace objects. PSpace objects provide
convenient syntax through overloaded indexing, attribute, iteration, deletion,
and call operators for manipulating properties.

Space Property Operations
=========================

The examples below use the following property store data.

=======  =====
Address  Value
=======  =====
a.b      1
a.b.c    2
a.b.c.d  3
a.b.c.e  4
=======  =====

Code examples will use the the following PSpace object variables.

=======  ============
Name     Base Address
=======  ============
sp_root  (root)
sp_ab    a.b
=======  ============

Property Indexed Access
-----------------------

Address parts can be specified as PSpace indexes using the "[]" operator and
chained together for access to deeper properties. Individual indexes can also
be compound keys that specify more than one level of an address.

Indexed access examples:

=====================  ============================
Expression             Returned PSpace base address
=====================  ============================
sp_ab['c']             a.b.c
sp_ab['c.d']           a.b.c.d
sp_ab['c']['d']        a.b.c.d
sp_root['a.b']['c.d']  a.b.c.d
=====================  ============================

Property Pseudo-Attribute Access
--------------------------------

Address parts that are valid Python symbols can be specified as PSpace
pseudo-attributes using the "." operator and chained together for access to
deeper properties.

Attribute access examples:

===============  ============================
Expression       Returned PSpace base address
===============  ============================
sp_ab.c          a.b.c
sp_ab.c.d        a.b.c.d
sp_ab.c.d        a.b.c.d
sp_root.a.b.c.d  a.b.c.d
===============  ============================

Property Deletion
-----------------

Using the del operator on a PSpace deletes any value associated with the
PSpace's base address, effectively deleting the property itself. Deletion is
useful for controlling what properties get iterated. Properties with None
values are still iterated, but deleted properties are not.

The following deletes the value at the address "a.b.c.d", hiding that address
from future iteration::

    del sp_ab.c.d

Property Iteration
------------------

The following iteration::

    for address, value in sp_ab.c:
        ...

yields the following (address,value) pair sequence::

    (("a.b.c", 2), ("a.b.c.d", 3), ("a.b.c.e", 4))

Reading Property Values
-----------------------

Calling a PSpace object with no arguments returns the property value for the
space's base address. None is returned when no property value exists.

Examples:

===================  ======  =================
Expression           Result  Read-From Address
===================  ======  =================
sp_root.a.b()        1       a.b
sp_root['a.b.c']()   2       a.b.c
sp_ab()              1       a.b
sp_ab.c              2       a.b.c
===================  ======  =================

Writing Property Values
-----------------------

Calling a PSpace object with a single value argument assigns that value to
the PSpace base address.

Property space write call examples:

=====================  =====  ===================
Expression             Value  Assigned-To Address
=====================  =====  ===================
sp_root.a.b(11)        11     a.b
sp_root['a']['b'](11)  11     a.b
sp_root['a.b.c'](12)   12     a.b.c
sp_ab(11)              11     a.b
sp_ab.c(12)            12     a.b.c
sp_ab['c.d'](13)       13     a.b.c.d
=====================  =====  ===================

The assignment operator "=" can also be used to write a property value to a
sub-space addressed by an attribute or an index.

WARNING: Assignment does not work as expected when assigning directly to a
space variable without using an attribute or an index to address a sub-space.
Python just changes that variable to reference the value, rather than the
original PSpace. The assignment won't be handled by the overloaded PSpace
attribute or indexed set methods __setattr__() or __setitem__().

Property assignment examples:

======================  =====  ===================
Expression              Value  Assigned-To Address
======================  =====  ===================
sp_root.a.b = 11        11     a.b
sp_root['a']['b'] = 11  11     a.b
sp_root['a.b.c'] = 12   12     a.b.c
sp_ab = 11                     *BAD: see above*
sp_ab.c = 12            12     a.b.c
sp_ab['c.d'] = 13       13     a.b.c.d
======================  =====  ===================

Copying Properties Using Operators
----------------------------------

If a space call argument or an assignment right hand side is another (source)
space the property data is copied. Addresses are constructed by appending the
source relative addresses to the target base address. The source space can
either be a variable or a sub-space obtained from an attributes or an index.

API Functions
=============

Public functions are summarized in the following table. Please refer to
individual function documentation for more details.

Space and Property Functions
----------------------------

+=================================+==================================+
| Synopsis                        | Description                      |
+=================================+==================================+
| create() -> PSpace              | Create a new store and return    |
|                                 | the root space.                  |
+---------------------------------+----------------------------------+
| descend(sp, addr) -> PSpace     | Descend to a sub-space of *sp*   |
|                                 | at the relative address *addr*.  |
+---------------------------------+----------------------------------+
| set_value(sp, value)            | Set the property value of the    |
|                                 | base address of space *sp*.      |
+---------------------------------+----------------------------------+
| copy_from_space(sp1, sp1)       | Copy properties from space *sp2* |
|                                 | into space *sp1*.                |
+---------------------------------+----------------------------------+
| update_from_sequence(sp, seq)   | Set space *sp* properties from   |
|                                 | (address,value) sequence *seq*.  |
+---------------------------------+----------------------------------+
| update_from_dictionary(         | Set properties in space *sp*     |
|     sp, prop_dict)              | from dictionary *prop_dict*.     |
+---------------------------------+----------------------------------+
| walk(sp, ...)                   | Iterate (address,value) pairs in |
|                                 | space *sp*.                      |
+---------------------------------+----------------------------------+
| delete(sp, ...)                 | Delete properties in space *sp*  |
|                                 | with optional restrictions.      |
+---------------------------------+----------------------------------+
| dump(sp)                        | Dump space *sp* data for         |
|                                 | debugging.                       |
+---------------------------------+----------------------------------+
| to_string(sp) -> string         | Convert space *sp* data to a     |
|                                 | human-readable string.           |
+=================================+==================================+

Utility Functions
-----------------

+=================================+==================================+
| Synopsis                        | Description                      |
+=================================+==================================+
| build_address(*parts) -> string | Concatenate and separate address |
|                                 | parts to build a new address.    |
+---------------------------------+----------------------------------+
| dict_flatten(prop_dict) -> dict | Flatten nested dictionary        |
|                                 | *prop_dict*.                     |
+---------------------------------+----------------------------------+
| dict_flatten_items(prop_dict)   | Flatten dictionary *prop_dict*   |
|     -> sequence                 | to an (address, value) sequence. |
+=================================+==================================+
"""

import sys
import os
import bisect

from . import utility


class PSpace(object):
    """
    Provide scoped access to property data given a base address.

    To avoid conflicts with property pseudo-attribute names there are no public
    attributes or methods. The only methods are the overloaded "[]", ".", "()",
    and iteration operators.
    """

    class _NoValue:
        pass

    __slots__ = ['_store_', '_address_']

    def __init__(self, store, address):
        """Construct with a store and an address."""
        object.__setattr__(self, '_store_', store)
        object.__setattr__(self, '_address_', str(address))

    def __getitem__(self, index):
        """
        Indexed getter.

        Return a PSpace for accessing children and properties.
        """
        return descend(self, index)

    def __setitem__(self, index, input_data):
        """
        Indexed assignment.

        Updates one or more properties at and or below the relative address
        specified by the index. It copies multiple property values using
        relative addressing if input_data is a PSpace object. Otherwise a
        single property value is assumed.
        """
        if isinstance(input_data, PSpace):
            copy_from_space(descend(self, index), input_data)
        else:
            set_value(descend(self, index), input_data)

    def __delitem__(self, index):
        """
        Indexed deletion.

        Deletes any assigned property value or does nothing if there isn't an
        assigned value. It also cleans up the address space so that addresses
        that have become empty, i.e. they no longer contain any property
        values, are not visited by iterators.
        """
        delete(descend(self, index), max_depth=0)

    def __getattr__(self, name):
        """
        Attribute getter.

        Return a PSpace for accessing children and properties.
        """
        return descend(self, name)

    def __setattr__(self, name, input_data):
        """
        Attribute assignment.

        Updates one or more properties at and or below the relative address
        specified by the attribute name. It copies multiple property values
        using relative addressing if input_data is a PSpace object. Otherwise a
        single property value is assumed.
        """
        if isinstance(input_data, PSpace):
            copy_from_space(descend(self, name), input_data)
        else:
            set_value(descend(self, name), input_data)

    def __delattr__(self, name):
        """
        Attribute deletion.

        Deletes any assigned property value or does nothing if there isn't an
        assigned value. It also cleans up the address space so that addresses
        that have become empty, i.e. they no longer contain any property
        values, are not visited by iterators.
        """
        delete(descend(self, name), max_depth=0)

    def __iter__(self):
        """Generate address/value pairs for all properties in this space."""
        return walk(self)

    def __call__(self, value=_NoValue):
        """
        Call magic method.

        Call with no arguments returns a property value or None if the property
        doesn't exist.

        Call with one argument (only) updates one or more properties at and or
        below the base address of the space. It copies multiple property values
        using relative addressing if value is a PSpace object. Otherwise a
        single property value is assumed.
        """
        if value is PSpace._NoValue:
            # Get the value.
            key_value = utility.generate_one_or_none(walk(self, max_depth=0))
            return key_value[1] if key_value else None
        # Set the value
        if isinstance(value, PSpace):
            copy_from_space(self, value)
        else:
            set_value(self, value)

    def __str__(self):
        """String conversion magic method."""
        return to_string(self)


class PropertyStoreBase(object):
    """
    Abstract property store interface.

    Note that bulk operations are preferred to allow for optimized
    implementations.
    """

    def set_properties(self, address, sub_address_value_pair_sequence):
        """
        Required property value setter.

        Stores property values from an input sub_address/value pair sequence.
        """
        raise NotImplementedError('%s class must implement set_properties().'
                                  % self.__class__.__name__)

    def get_properties(self, address, min_depth=0, max_depth=None):
        """
        Required generator.

        Yields property address/value pairs sorted by address for all addresses
        where a value is assigned.
        """
        raise NotImplementedError('%s class must implement get_properties().'
                                  % self.__class__.__name__)

    def delete_properties(self, address, min_depth=0, max_depth=None, deleted=None):
        """Required property value deleter."""
        raise NotImplementedError('%s class must implement delete_properties().'
                                  % self.__class__.__name__)


class SortedDictPropertyStore(PropertyStoreBase):
    """
    Sorted dictionary property store.

    A property store implementation that stores property data in an ordered
    dictionary that gets sorted only when needed for iteration.
    """

    def __init__(self):
        """Construct with an empty dictionary."""
        self.all_properties = dict()
        # Populated as-needed for iteration. For efficiency deleted keys are
        # not removed and must be skipped.
        self.sorted_keys = None

    def set_properties(self, address, sub_address_value_pair_sequence):
        """
        Required property value setter.

        Stores property values from an input sub_address/value pair sequence.
        """
        for key, value in sub_address_value_pair_sequence:
            full_key = build_address(address, key)
            self.all_properties[full_key] = value
        # Assume added properties are unsorted.
        self.sorted_keys = None

    def get_properties(self, address, min_depth=0, max_depth=None):
        """
        Required generator.

        Yields property address/value pairs sorted by address for all addresses
        where a value is assigned.
        """
        for key in self._populated_keys(address, min_depth=min_depth, max_depth=max_depth):
            yield key, self.all_properties[key]

    def delete_properties(self, address, min_depth=0, max_depth=None, deleted=None):
        """Required property value deleter."""
        # Can optimize deleting everything and the caller doesn't need to
        # know what was deleted.
        if not address and min_depth == 0 and max_depth is None and deleted is None:
            count = len(self.all_properties)
            self.all_properties.clear()
            self.sorted_keys = None
            return count
        # Otherwise iterate the affected keys before deleting the properties
        # outside of the iteration.
        count = 0
        keys = list(self._populated_keys(address, min_depth=min_depth, max_depth=max_depth))
        count = len(keys)
        for key in keys:
            if deleted:
                deleted.append((key, self.all_properties[key]))
            del self.all_properties[key]
        return count

    def _populated_keys(self, address, min_depth=0, max_depth=None):
        if self.sorted_keys is None:
            self.sorted_keys = sorted(self.all_properties.keys())
        prefix_len = len(address)
        # Use a binary search to find the starting position.
        pos = bisect.bisect_left(self.sorted_keys, address, 0, len(self.sorted_keys))
        for key in self.sorted_keys[pos:]:
            if not key.startswith(address):
                break
            if key not in self.all_properties:
                continue
            if len(key) == prefix_len:
                if min_depth == 0:
                    yield key
            else:
                if prefix_len > 0 and key[prefix_len] != '.':
                    break
                depth = key.count('.')
                if depth >= min_depth and (max_depth is None or depth <= max_depth):
                    yield key


#===== Public functions


def build_address(*parts):
    """
    Create a fully-qualified address from one or more address parts.

    Specifically, skip None or '' parts, convert non-string parts to strings,
    and insert '.' separators between non-empty parts.
    """
    return '.'.join([str(part) for part in parts if part is not None and part != ''])


def dict_flatten_items(nested_dict):
    """
    Convert a nested dictionary to a flat name/value pair iterable sequence.

    For example:
         input: {'a': 1, 'b': {'c': 2, 'd': 3}}
        output: ('a', 1) ('b.c', 2) ('b.d', 3)
    """
    for key, value in utility.six.iteritems(nested_dict):
        if hasattr(value, '__setitem__') and hasattr(value, 'keys'):
            for sub_key, sub_value in dict_flatten_items(value):
                yield build_address(str(key), sub_key), sub_value
        else:
            yield str(key), value


def dict_flatten(nested_dict):
    """
    Convert a nested dictionary to a flat dictionary.

    For example:
         input: {'a': 1, 'b': {'c': 2, 'd': 3}}
        output: {'a': 1, 'b.c': 2, 'b.d': 3}
    """
    return dict(dict_flatten_items(nested_dict))


def create(store_class=None):
    """
    Create a property store and provide a space representing the root.

    The optional property store class must inherit from PropertyStoreBase.

    Optional keyword arguments:
        store_class  property store class (default=SortedDictPropertyStore)

    Returns a PSpace object.
    """
    if store_class is None:
        return PSpace(SortedDictPropertyStore(), '')
    if not issubclass(PropertyStoreBase, store_class):
        raise TypeError('%s is not derived from PropertyStoreBase.' % store_class.__name__)
    return PSpace(store_class(), '')


def descend(space, sub_address):
    """
    Descend to a relative address within a space and provide a child space.

    Positional arguments:
        space        constraining property space
        sub_address  relative sub-address within the space

    Returns a PSpace object.
    """
    return PSpace(space._store_, build_address(space._address_, sub_address))       #pylint: disable=protected-access


def copy_from_space(target_space, source_space):
    """
    Copy property values from one space to another.

    Uses relative addressing. The target and source spaces can share the same
    property store, but do not have to.

    This copies all properties. To copy filtered properties use walk(space,
    <filters>) and pass the results to update_from_sequence().

    Positional arguments:
        target_space  target space
        source_space  source space for input properties
    """
    target_space._store_.set_properties(target_space._address_, walk(source_space)) #pylint: disable=protected-access


def update_from_sequence(space, name_value_pair_sequence):
    """
    Update properties from a name/value pair sequence.

    Positional arguments:
        space                     target space
        name_value_pair_sequence  input name/value pairs for properties
    """
    space._store_.set_properties(space._address_, name_value_pair_sequence)         #pylint: disable=protected-access


def update_from_dictionary(space, data_dict):
    """
    Update properties in a space from flat or nested dictionary-like object.

    It updates properties at the relative addresses defined by the dictionary
    keys. Dictionary-like objects can be nested, in which case compound keys
    are constructed by joining the nested names with '.'.

    Positional arguments:
        space      target space
        data_dict  input dictionary with property data
    """
    space._store_.set_properties(space._address_, dict_flatten_items(data_dict))    #pylint: disable=protected-access

def set_value(space, value):
    """
    Set a property value at the base address of the space.

    Positional arguments:
        space  target space
        value  new value for property
    """
    space._store_.set_properties(space._address_, [('', value)])                    #pylint: disable=protected-access


def walk(space, min_depth=0, max_depth=None, filter_func=None, relative=False):
    """
    Recursively generate address/value pairs.

    Generate for all populated properties within a space.

    Optionally limit the traversal based on depth constraints.

    Positional arguments:
        space  constraining property space

    Optional keyword arguments:
        min_depth    minimum depth for properties yielded to caller (default=0)
        max_depth    0     only generate the base property, if there is one
                     1-n   descend up to n levels
                     None  descends to all populated levels (default)
        filter_func  optional callable that takes (address, value) arguments
                     and returns True or False to yield or skip the property
        relative     provides relative addresses if True, otherwise they are
                     absolute (default=False)

    Yields (address, value) pairs.
    """
    if min_depth < 0:
        raise ValueError('min_depth (%d) must not be negative' % min_depth)
    if max_depth is not None and max_depth < min_depth:
        raise ValueError('max_depth (%d) must be greater than min_depth (%d)'
                         % (max_depth, min_depth))
    skip_count = len(space._address_) if relative else 0                            #pylint: disable=protected-access
    for address, value in space._store_.get_properties(space._address_,             #pylint: disable=protected-access
                                                       min_depth=min_depth,
                                                       max_depth=max_depth):
        if not filter_func or filter_func(address, value):
            if skip_count > 0:
                ret_address = address[skip_count + 1:]
            else:
                ret_address = address
            yield ret_address, value


def delete(space, min_depth=0, max_depth=None, deleted=None):
    """
    Recursively delete properties from a space.

    Optionally limit the traversal based on depth constraints.

    Positional arguments:
        space  constraining property space

    Optional keyword arguments:
        min_depth  minimum depth for deleting property values (default=0)
        max_depth  0     only delete the base property
                   1-n   deletes from up to n sub-address levels
                   None  deletes from all populated sub-address levels
                   (default=None)
        deleted    list to populate with deleted (name, value) pairs
                   (default=None)

    Returns the number of deleted property values.
    """
    if min_depth < 0:
        raise ValueError('min_depth (%d) must not be negative' % min_depth)
    if max_depth is not None and max_depth < min_depth:
        raise ValueError('max_depth (%d) must be greater than min_depth (%d)'
                         % (max_depth, min_depth))
    return space._store_.delete_properties(space._address_,                         #pylint: disable=protected-access
                                           min_depth=min_depth,
                                           max_depth=max_depth,
                                           deleted=deleted)


def dump(space, stream=sys.stderr):
    """Dump the contents of a PSpace to an output stream for debugging."""
    stream.write('%s::: begin PSpace dump from base address "%s" :::%s'
                 % (os.linesep, space._address_, os.linesep))                       #pylint: disable=protected-access
    for key, value in walk(space, ''):
        stream.write('%s = %s%s' % (key, str(value), os.linesep))
    stream.write('::: end PSpace dump from base address "%s" :::%s'
                 % (space._address_, os.linesep))                                   #pylint: disable=protected-access


def to_string(space):
    """Format the space properties as a human-readable string."""
    lines = ['PSpace[%s]:' % space._address_]                                       #pylint: disable=protected-access
    for address, value in walk(space):
        lines.append('  %s = %s' % (address, str(value)))
    return os.linesep.join(lines)
