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
import yaml
from . import console
from . import flatten


#===============================================================================
class ConfigSpec(object):
#===============================================================================
    '''
    Specifies a named configuration entry.
    '''

    def __init__(self, name, value, desc, *children):
        self.name = name
        self.value = value
        self.desc = desc
        self.children = children


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
class SyntaxBase(object):
    '''
    Base class for syntax-specific data and logic.
    '''
#===============================================================================

    @classmethod
    def _iter_specs(cls, specs):
        for key in sorted(specs.keys()):
            yield specs[key]


#===============================================================================
class ConfigurationWriter(object):
    '''
    Writes configuration files for multiple syntaxes.
    Only supports line-oriented comments, not comment blocks.
    '''
#===============================================================================

    def __init__(self, stream, comment_prefix, commented_out):
        self.stream = stream
        self.comment_prefix = '%s ' % comment_prefix
        self.commented_out = commented_out

    def lines(self, is_comment, lines):
        comment_prefix = self.comment_prefix if self.commented_out or is_comment else ''
        for line in lines:
            if line:
                self.stream.write(''.join([indent, comment_prefix, line]))
            self.stream.write(os.linesep)

    def code(*lines):
        self.lines(False, lines)

    def comment(*lines):
        self.lines(True, lines)

#===============================================================================
class ConfigurationReader(object):
    '''
    Reads configuration files for multiple syntaxes.
    For now it provides no added value except for symmetry with
    ConfigurationWriter.
    '''
#===============================================================================

    def __init__(self, stream):
        self.stream = stream

    def read_all(self):
        return self.stream.read()

#===============================================================================
class YAMLSyntax(SyntaxBase):
    '''
    Provides syntax-specific data and logic for YAML configuration files.

    The read_configuration() method builds a a flat dictionary indexed by
    compound key names. The flat structure of the configuration dictionary
    implies that lists musts be terminal values. A top level YAML list results
    in a single configuration entry with an empty ("") key.

    No valid YAML is rejected and no data is lost, but the configuration
    dictionary won't provide direct access to complex data nested inside lists.
    '''
#===============================================================================

    name = 'YAML'
    comment_prefix = '#'

    def write_configuration(self, writer, specs, header_lines):
        indent = ''
        writer.comment(*header_lines)
        writer.code('')
        for spec in self._iter_specs(specs):
            indent = '  ' * spec.name.count('.')
            if spec.desc:
                writer.comment(spec.desc)
            value_type = type(spec.value)
            if value_type is tuple or value_type is list:
                writer.code('%s:' % spec.name)
                if len(spec.value) > 0:
                    for value in spec.value:
                        writer.code('  - %s' % str(value))
                else:
                    writer.code('  -')
            else:
                writer.code('%s: %s' % (spec.name, str(spec.value)))

    def read_configuration(self, reader, specs, config):
        def process_data(data, parent_key=''):
            if type(data) is dict:
                for key, item in data.items():
                    sub_key = '.'.join([parent_key, item.name])
                    process_data(item, sub_key)
            else:
                # Only deal with the keys we know about.
                #TODO: Check other things?
                if parent_key in specs:
                    config[parent_key] = item
        data = yaml.load(reader.read_all())
        process_data(data, '')


#===============================================================================
class PythonSyntax(SyntaxBase):
    '''
    Provides syntax-specific data and logic for Python configuration files.
    Only simple variables are supported for now, not objects and attributes.
    '''
#===============================================================================

    name = 'Python'
    comment_prefix = '#'

    def write_configuration(self, writer, specs, header_lines):
        writer.comment(*header_lines)
        for spec in self._iter_specs(specs):
            writer.code('')
            if spec.desc:
                writer.comment(spec.desc)
            if type(spec.value) is str:
                writer.code("%s = '%s'" % (spec.name, spec.value))
            else:
                writer.code("%s = %s" % (spec.name, spec.value))

    def read_configuration(self, reader, spec_dict, config):
        # Grab configuration data and ignore other configuration file
        # symbols from local Python code.
        globals_tmp = {}
        locals_tmp = {}
        for spec in self._iter_specs(spec_dict):
            locals_tmp[spec.name] = config.get(spec.name, None)
        exec(reader.read_all(), globals_tmp, locals_tmp)
        for spec in self._iter_specs(spec_dict):
            config[spec.name] = locals_tmp[spec.name]

    @classmethod
    def _iter_specs(cls, spec_dict):
        for spec in SyntaxBase._iter_specs(spec_dict):
            if key != spec.name:
                raise ValueError("Python configurations do not support multiple levels")
            yield spec


#===============================================================================
class Config(object):
    '''
    Manages a dictionary of configuration data.
    '''
#===============================================================================

    def __init__(self, file_name, *specs, **kwargs):
        # Specification metadata is kept as full clone of the original tree of
        # nested specification items.
        # Data is a dictionary mapping compound keys, e.g. "a.b.c", to values,
        # where compound key segments correspond to nested specification item
        # names.
        # This arrangement allows for both direct access to data dictionary
        # values using the full compound keys or indirect, e.g. hierarchical,
        # access through the metadata tree.
        self.file_name = file_name
        self.specs = copy.deepcopy(specs)
        self.spec_dict = {}
        self.data = ConfigDict()
        bad_keys = sorted([key for key in kwargs.keys() if key != 'syntax'])
        if bad_keys:
            raise ValueError('Unrecognized keyword argument(s) for Config: %s' % ' '.join(bad_keys))
        syntax_name = kwargs.get('syntax', 'yaml').lower()
        if syntax_name == 'yaml':
            self.syntax = YAMLSyntax()
        elif syntax_name == 'python':
            self.syntax = PythonSyntax()
        else:
            raise ValueError('Config syntax is not "yaml" or "python": %s' % syntax_name)
        self._initialize(specs, None)

    def _initialize(self, specs, parent_key):
        for spec in specs:
            key = '.'.join([parent_key, spec.name]) if parent_key else spec.name
            self.data[key] = spec.value
            self.spec_dict[key] = spec
            if spec.children:
                self._initialize(spec.children, key)

    def generate(self, commented_out=True):
        try:
            if os.path.exists(self.file_name):
                console.abort('Configuration file already exists: %s' % self.file_name)
            header = []
            if commented_out:
                header.append('Un-comment and edit below to change default configuration settings.')
            else:
                header.append('Edit below to change default configuration settings.')
            header.append('File format: %s' % self.syntax.name)
            with open(self.file_name, 'w') as f:
                writer = ConfigurationWriter(f, self.syntax.comment_prefix, commented_out)
                self.syntax.write_configuration(writer, self.spec_dict, header)
            console.info('Configuration file saved: %s' % self.file_name)
        except (IOError, OSError) as e:
            console.abort('Unable to save configuration file: %s' % self.file_name, e)

    def load_for_paths(self, *paths):
        config_dirs = []
        for path in flatten.flatten_strings(paths):
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
        self._dump(self.specs)

    def _dump(self, specs, level=0):
        for spec in specs:
            console.verbose_info('%s%s=%s' % ('  ' * level, spec.name, str(self.data[spec.name])))
            if spec.children:
                self._dump(spec.children, level + 1)

    def _load_directory_config(self, directory):
        path = os.path.expanduser(os.path.expandvars(os.path.join(directory, self.file_name)))
        if not os.path.isfile(path):
            return
        try:
            console.verbose_info('Reading configuration file: %s' % path)
            with open(path) as f:
                reader = ConfigurationReader(f)
                self.syntax.read_configuration(reader, self.spec_dict, self.data)
        except Exception as e:
            console.abort('Error reading configuration file: %s' % path, e)
