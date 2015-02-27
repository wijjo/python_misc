#!/usr/bin/env python
#===============================================================================
#===============================================================================
# configmapper
#
# ConfigParser enhancement:
#   - section entry inheritance
#   - section reference traversal
#
# 02/28/10 - Steve Cooper - author
#===============================================================================
#===============================================================================

import sys
import os
from ConfigParser import SafeConfigParser

class ConfigException(Exception):
    pass

class NameValue(object):
    def __init__(self, name, value):
        self.name  = name
        self.value = value
    def __str__(self):
        return '%s = %s' % (self.name, self.value)

#===============================================================================
class Config(object):
#===============================================================================

    # Name of entry used to include other sections, possibly recursively.
    include_entry = 'sections'

    class Section(object):
        def __init__(self, name, meta):
            self.name   = name
            self.meta   = meta
            self.errors = []
            self.user   = os.environ['LOGNAME']
            self.a      = {}
        def __iter__(self):
            '''Default iterator iterates NameValue's for all attributes sorted by name.'''
            for item in self.iter_items():
                yield item
        def __cmp__(self, other):
            '''Default comparison is by name.'''
            return cmp(self.name, other.name)
        def has(self, *names):
            '''Checks for attribute existence.'''
            for name in names:
                if name not in self.a:
                    return False
            return True
        def get(self, name, default = None):
            '''Returns attribute value if it is found.
               Returns None if it is missing, not a list and not required.
               Returns [] if it is missing, a list, and not required.
               Raises ConfigException if it is missing and required.'''
            if name not in self.a:
                if default is not None:
                    return default
                if name in self.meta.required:
                    raise ConfigException('Required attribute "%s" missing from section "%s"'
                                          % (name, self.name))
                if name in self.meta.lists:
                    return []
                return None
            value = self.a[name]
            if value is None and default is not None:
                return default
            return value
        def names(self):
            '''Returns sorted list of attribute names.'''
            names = self.a.keys()
            names.sort()
            return names
        def items(self):
            '''Returns list of NameValue's sorted by name.'''
            return [item for item in self.iter_items()]
        def iter_items(self):
            '''Iterate NameValue's for all attributes sorted by name.'''
            for name in self.names():
                yield NameValue(name, self.a[name])
        def __str__(self):
            s = ['[%s]' % self.name]
            for key in sorted(self.a.keys()):
                if self.a[key]:
                    s.append(str(NameValue(key, self.a[key])))
            return '\n'.join(s)

    class Meta(object):
        def __init__(self, required, numbers, lists, keywords):
            self.required = required
            self.numbers  = numbers
            self.lists    = lists
            self.keywords = keywords
        def __str__(self):
            return '{required=%(required)s, numbers=%(numbers)s, lists=%(lists)s, keywords=%(keywords)s}' % self.__dict__

    @staticmethod
    def load(configpath, required = [], numbers = [], lists = [], keywords = []):
        parser = SafeConfigParser()
        try:
            parser.read(configpath)
        except Exception, e:
            raise ConfigException('Failed to load configuration from "%s"' % configpath, str(e))
        meta   = Config.Meta(required, numbers, lists, keywords)
        config = Config(meta)
        for section_name in parser.sections():
            section_name = section_name.lower()
            section = Config.Section(section_name, meta)
            config.add_section(section_name, section)
            for (attr_name, attr_value) in parser.items(section_name):
                config.set_section_entry(section, attr_name, attr_value)
        for section_name in parser.sections():
            config.process_includes(section_name)
        return config

    def __init__(self, meta):
        self.meta = meta
        self.section_map = {}

    def add_section(self, section_name, section):
        # Lists and keywords are both implemented as Python lists, except
        # that keywords enforce uniqueness (while maintaining order).
        for name in self.meta.lists:
            section.a[name] = []
        for name in self.meta.keywords:
            section.a[name] = []
        # Start with an empty include entry
        section.a[Config.include_entry] = []
        # Add to section map using lowercase name
        self.section_map[section_name.lower()] = section

    def get_section(self, section_name):
        return self.section_map[section_name.lower()]

    def has_section(self, section_name):
        return section_name.lower() in self.section_map

    def set_section_entry(self, section, name, value):
        # Split lists and across lines and using ':' separator
        if name in self.meta.lists:
            for s1 in value.strip().split('\n'):
                for s2 in s1.strip().split(':'):
                    section.a[name].append(s2.strip())
        # Split keywords and across lines and using whitespace separator
        elif name in self.meta.keywords or name == Config.include_entry:
            for s1 in value.strip().split('\n'):
                for s2 in s1.strip().split():
                    section.a[name].append(s2)
        elif name in self.meta.numbers:
            try:
                section.a[name] = int(value)
            except ValueError:
                raise ConfigException('Value for "%s" in section "%s" must be a number'
                                            % (name, self.name))
        else:
            section.a[name] = value

    def process_includes(self, section_name):
        processed = set()
        self._process_includes(section_name, processed)

    def iter_sections(self, names = None, reference = None):
        if names:
            missing = [name for name in names if not self.has_section(name)]
            if missing:
                raise ConfigException('Not found in configuration: %s' % ' '.join(missing))
        else:
            names = self.section_map.keys()
        names.sort()
        yielded = set()
        # No need for recursion, because references should have already been
        # consolidated by include processing.
        for name in names:
            if name not in yielded:
                yielded.add(name)
                section = self.get_section(name)
                if reference and reference in section.a:
                    for name_ref in section.a[reference]:
                        if name_ref not in self.section_map:
                            raise ConfigException('Reference not found in configuration: %s'
                                                        % name_ref)
                        if name_ref not in yielded:
                            yielded.add(name_ref)
                            yield self.get_section(name_ref)
                yield section

    def _process_includes(self, section_name, processed):
        section = self.section_map[section_name.lower()]
        if section.name not in processed:
            processed.add(section.name)
            name = section.name.lower()
            for name_inc in section.a[Config.include_entry]:
                name_inc = name_inc.lower()
                if name_inc in self.section_map:
                    section_inc = self.section_map[name_inc]
                    print '[%s] => %s' % (section_name, section_inc)
                    self._process_includes(name_inc, processed)
                    self._copy_section(section_inc, section)

    def _copy_section(self, section_src, section_dst):
        for attr_name in section_src.a:
            if attr_name != Config.include_entry:
                if attr_name in self.meta.lists:
                    if section_src.a[attr_name]:
                        print '##### SRC[%s]=%s' % (attr_name, section_src.a[attr_name])
                        print '##### DST1[%s]=%s' % (attr_name, section_dst.a[attr_name])
                        section_dst.a[attr_name].extend(section_src.a[attr_name])
                        print '##### DST2[%s]=%s' % (attr_name, section_dst.a[attr_name])
                elif attr_name in self.meta.keywords:
                    for keyword in section_src.a[attr_name]:
                        if keyword not in section_dst.a[attr_name]:
                            section_dst.a[attr_name].append(keyword)
                elif attr_name not in section_dst.a:
                    section_dst.a[attr_name] = section_src.a[attr_name]
