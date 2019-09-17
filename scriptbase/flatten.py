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

"""List flattening functions."""

def _format(sin, **symbols):
    sout = sin
    if symbols:
        for i in range(10):
            try:
                # Support old and new formatting syntax
                sout = (sin % symbols).format(**symbols)
                break
            except KeyError as exc:
                if i == 0:
                    symbols = symbols.copy()
                symbols[exc] = '???'
    return sout

def flatten(items, symbols=None, level=0, split_strings_on=None, as_string=False):
    """
    Flatten and yield level/item pairs from a potentially nested list.

    If split_strings_on is specified splits all strings on it.
    If vars has dictionary entries, formats all strings with it.
    If as_string is True converts items to strings.
    """
    if symbols is None:
        symbols = {}
    for item in items:
        if item is not None:
            try:
                test_string = item + '' #pylint: disable=unused-variable
                # It's a string
                if split_strings_on:
                    for substring in item.split(split_strings_on):
                        yield level, _format(substring, **symbols)
                else:
                    yield level, _format(item, **symbols)
            except TypeError:
                # Exceptions appear to be iterable. Return them without iterating.
                if issubclass(item.__class__, Exception):
                    yield level, str(item) if as_string else item
                else:
                    try:
                        test_iter = iter(item)  #pylint: disable=unused-variable
                        # Use recursion in case it's nested further.
                        for subitem in item:
                            for sublevel, subsubitem in flatten([subitem],
                                                                symbols=symbols,
                                                                level=level+1,
                                                                split_strings_on=split_strings_on,
                                                                as_string=as_string):
                                yield sublevel, subsubitem
                    except TypeError:
                        # It's a non-iterable non-string.
                        # Convert to string if as_string is True.
                        yield level, str(item) if as_string else item

def flatten_items(*items, **symbols):
    """Flatten nested items and yield iterable items."""
    for level, item in flatten(items, symbols=symbols):   #pylint: disable=unused-variable
        yield item

def flatten_split_strings(split_strings_on, *items, **symbols):
    """Flatten and split strings and yield iterable strings."""
    for level, item in flatten(items,      #pylint: disable=unused-variable
                               symbols=symbols,
                               split_strings_on=split_strings_on,
                               as_string=True):
        yield item

def flatten_strings(*items, **symbols):
    """Flatten items and yield iterable strings."""
    for level, item in flatten(items, symbols=symbols, as_string=True):   #pylint: disable=unused-variable
        yield item
