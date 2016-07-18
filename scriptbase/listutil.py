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

#===============================================================================
#===============================================================================
# listutil
#
# Various list utilities
#
# 08/22/10 - Steve Cooper - author
#===============================================================================
#===============================================================================

def _format(sin, **vars):
    sout = sin
    if vars:
        for i in range(10):
            try:
                # Support old and new formatting syntax
                sout = (sin % vars).format(**vars)
                break
            except KeyError as e:
                if i == 0:
                    vars = vars.copy()
                vars[e] = '???'
    return sout

def _flatten(split_on, *items, **vars):
    '''Flatten and yield individual items from a potentially nested list.
       If split_on is specified splits all strings on it.
       If vars has dictionary entries, formats all strings with it.'''
    for item in items:
        if item is not None:
            try:
                test_string = item + ''
                # It's a string
                if split_on:
                    for substring in item.split(split_on):
                        yield _format(substring, **vars)
                else:
                    yield _format(item, **vars)
            except TypeError:
                try:
                    test_iter = iter(item)
                    # Use recursion in case it's nested further.
                    for subitem in item:
                        for subsubitem in _flatten(split_on, subitem, **vars):
                            yield subsubitem
                except TypeError:
                    # It's a non-iterable non-string
                    yield item

def flatten(*items, **vars):
    for item in _flatten(None, *items, **vars):
        yield item

def flatten_strings(*items, **vars):
    for item in _flatten(None, *items, **vars):
        yield str(item)

def flatten_split_strings(split_on, *items, **vars):
    for item in _flatten(split_on, *items, **vars):
        yield str(item)
