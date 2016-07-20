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

import os
import copy
from . import console
from . import listutil


#===============================================================================
class ConfigSpec(object):
#===============================================================================
    '''
    Specifies a named configuration entry.
    '''

    def __init__(self, name, value, desc):
        self.name = name
        self.value = value
        self.desc = desc

    def name_value_string(self):
        quote = "'" if type(self.value) is str else ''
        name = self.name
        value = self.value
        return '%(name)s = %(quote)s%(value)s%(quote)s' % locals()


#===============================================================================
class ConfigDict(dict):
#===============================================================================

    def __init__(self, **kwargs):
        dict.__init__(self, **kwargs)

    def __getattr__(self, name):
        return self.get(name, None)

    def __setattr__(self, name, value):
        self[name] = value


#===============================================================================
class Config(object):
    '''
    Manages a dictionary of configuration data from a Python-syntax file.
    '''
#===============================================================================

    def __init__(self, file_name, *specs):
        self.file_name = file_name
        self.specs = specs
        self.data = ConfigDict()
        for spec in self.specs:
            self.data[spec.name] = spec.value

    def generate(self, commented_out=True):
        comment = '#' if commented_out else ''
        try:
            if os.path.exists(self.file_name):
                console.abort('Configuration file already exists: %s' % self.file_name)
            with open(self.file_name, 'w') as f:
                f.write('''\
# Un-comment and edit below to change default configuration settings.
# Full Python syntax is supported, including strings, lists, imports, etc..
''')
                for spec in self.specs:
                    f.write('\n')
                    if spec.desc:
                        f.write('# %s\n' % spec.desc)
                    f.write('%s%s\n' % (comment, spec.name_value_string()))
            console.info('Configuration file saved: %s' % self.file_name)
        except (IOError, OSError) as e:
            console.abort('Unable to save configuration file: %s' % self.file_name, e)

    def load_for_paths(self, *paths):
        config_dirs = []
        for path in listutil.flatten(paths):
            if path:
                config_dir = os.path.realpath(
                    path if os.path.isdir(path) else os.path.dirname(path))
                if config_dir not in config_dirs:
                    config_dirs.append(config_dir)
        for config_dir in config_dirs:
            self._load_directory_config(config_dir)
        if console.is_verbose():
            self.dump()

    def dump(self):
        console.verbose_info('=== Configuration ===')
        for spec in self.specs:
            console.verbose_info('%s=%s' % (spec.name, str(self.data[spec.name])))

    def _load_directory_config(self, directory):
        path = os.path.expanduser(os.path.expandvars(os.path.join(directory, self.file_name)))
        if not os.path.isfile(path):
            return
        try:
            console.verbose_info('Reading configuration file: %s' % path)
            # Grab configuration data and ignore other configuration file
            # symbols from local Python code.
            globals_tmp = {}
            locals_tmp = {}
            for spec in self.specs:
                locals_tmp[spec.name] = self.data.get(spec.name, None)
            execfile(path, globals_tmp, locals_tmp)
            for spec in self.specs:
                if spec.name in locals_tmp:
                    self.data[spec.name] = locals_tmp[spec.name]
        except Exception as e:
            console.abort('Error reading configuration file: %s' % path, e)
