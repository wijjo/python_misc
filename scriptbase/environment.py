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

"""Environment variable utility classes."""

import os
import re
import copy


class Environment(object):
    """
    Hold a dictionary of named values for the shell environment.

    Provide various features to help work with environment variables, including
    attribute-style access, path manipulation, iteration, and change analysis.

    The vars member provides read/write access to variables using either
    attribute-style or dictionary-style access, i.e. by specifying the key
    after '.' as if it is a member as a string inside square brackets.
    """

    @classmethod
    def is_special_variable(cls, name):
        """Return True if the named variable is a special shell built-in."""
        return not name or name == 'SHLVL' or not name[0].isalpha()

    @classmethod
    def remove_from_path_string(cls, path_string, *directories_to_remove):
        """
        Remove individual elements of a path string.

        Specifically, remove any of the path elements from "path_string" that
        start with any of the filesystem paths in "directories_to_remove".
        """
        def _need_to_remove(path_dir):
            for to_remove in directories_to_remove:
                if path_dir.startswith(to_remove):
                    return True
            return False
        return os.pathsep.join([path_dir for path_dir in path_string.split(os.pathsep)
                                if not _need_to_remove(path_dir)])

    @classmethod
    def prepend_to_path_string(cls, path_string, *directories_to_prepend):
        """
        Prepend elements to a path string.

        Specifically, insert the "directories_to_prepend" filesystem paths in
        front of "path_string" and remove those directories when they are
        repeated later in the path string.

        Potentially, this can be used two ways, to inject new directories into
        a path and to elevate the priority of ones that are already there.
        """
        new = list(copy.copy(directories_to_prepend))
        for old in path_string.split(os.pathsep):
            if old not in new:
                new.append(old)
        return os.pathsep.join(new)

    @classmethod
    def append_to_path_string(cls, path_string, *directories_to_append):
        """
        Append elements to a path string.

        Specifically, append the "directories_to_append" filesystem paths to
        the end of "path_string" when not already present in that string.
        """
        directories_in_path_string = path_string.split(os.pathsep)
        for directory in directories_to_append:
            if directory and directory not in directories_in_path_string:
                directories_in_path_string.append(directory)
        return os.pathsep.join(directories_in_path_string)

    @classmethod
    def import_from_shell(cls):
        """
        Incorporate variables and values from the shell environment.

        Filter out internal/special shell environment variables.
        """
        env_dict = {name: os.environ[name]
                    for name in os.environ
                    if not cls.is_special_variable(name)}
        return Environment(**env_dict)

    def export_to_shell(self):
        """
        Copy variables and values to the shell environment.

        Filter out internal/special shell environment variables.
        """
        for name in self.vars:
            if (not self.is_special_variable(name) and (
                    name not in os.environ or
                    self.vars[name] != os.environ[name])):
                os.environ[name] = self.vars[name]

    def __init__(self, **kwargs):
        """Construct with an optional initial set of variables as keywords."""
        class _Vars(dict):
            def __getattr__(self, name):
                return self.get(name, None)
            def __setattr__(self, name, value):
                self[name] = value
        self.vars = _Vars(**kwargs)

    def clone(self):
        """Clone a copy of the environment variables/values."""
        return Environment(**self.vars)

    def diff(self, other):
        """
        Compare to another Environment object.

        Return an object with added, modified, and removed lists that specify
        all the changes that happened to the other Environment.

        The added list has (name, value) tuples. The modified list has (name,
        old_value, new_value) tuples. The removed list has (name, old_value)
        tuples.

        All returned lists are sorted by name.
        """
        class _Result(object):
            def __init__(self):
                self.added = []
                self.modified = []
                self.removed = []
            def __str__(self):
                return os.linesep.join(['added=%s' % self.added,
                                        'modified=%s' % self.modified,
                                        'removed=%s' % self.removed])
        result = _Result()
        for name in sorted(self.vars.keys()):
            if name not in other.vars:
                result.added.append((name, self.vars[name]))
            elif self.vars[name] != other.vars[name]:
                result.modified.append((name, other.vars[name], self.vars[name]))
        for name in sorted(other.vars.keys()):
            if name not in self.vars:
                result.removed.append((name, other.vars[name]))
        return result

    def remove_from_path(self, name, *directories_to_remove):
        """
        Remove elements from a path environment variable.

        Remove any of the path elements from the "name" path variable that
        start with any of the filesystem paths in "directories_to_remove".

        Does nothing if the named variable does not exist.
        """
        if name in self.vars:
            self.vars[name] = self.remove_from_path_string(self.vars[name],
                                                           *directories_to_remove)

    def prepend_to_path(self, name, *directories_to_prepend):
        """
        Prepend elements to a path environment variable.

        Insert the "directories_to_prepend" filesystem paths in front of the
        "name" path variable and remove those directories when they are
        repeated later in the path string.

        If the "name" variable does not yet exist initialize it with the
        specified directories.

        Potentially, this can be used two ways, to inject new directories into
        a path and to elevate the priority of ones that are already there.
        """
        if name in self.vars:
            self.vars[name] = self.prepend_to_path_string(self.vars[name],
                                                          *directories_to_prepend)
        else:
            self.vars[name] = os.pathsep.join(directories_to_prepend)

    def append_to_path(self, name, *directories_to_append):
        """
        Append elements to a path environment variable.

        Append the "directories_to_append" filesystem paths to the end of the
        "name" path variable when they are not already present in the path.

        If the "name" variable does not yet exist initialize it with the
        specified directories.
        """
        if name in self.vars:
            self.vars[name] = self.append_to_path_string(self.vars[name],
                                                         *directories_to_append)
        else:
            self.vars[name] = os.pathsep.join(directories_to_append)

    def substitute_value(self, name, pattern, replacement, count=0):
        r"""
        Perform regular expression substitution on the "name" variable.

        If the variable exists replace the regular expression "pattern" with
        the "replacement" string. If specified, "count" can limit the number of
        pattern repetitions that get replaced.

        It is worth mentioning that patterns and replacement strings can take
        advantage of regular expression groups to bring across portions of the
        original string, by using parentheses to specify a group in the pattern
        and \N insert group #N (1-N) into the text.

        Does nothing if the named variable does not exist.
        """
        if name in self.vars:
            self.vars[name] = re.sub(pattern, replacement, self.vars[name], count)

    def __str__(self):
        """
        Convert to a string.

        Return a linefeed-separated sorted list of NAME=VALUE pairs.
        """
        return os.linesep.join(['='.join([k, self.vars[k]]) for k in sorted(self.vars.keys())])

    def __eq__(self, other):
        """Compare contained variables/values."""
        return self.vars == other.vars
