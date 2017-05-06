# Copyright 2016-17 Steven Cooper
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

from .textfile import TextFile

class DEFAULT:
    # DOCTYPE can have multiple arguments
    doctype = ('HTML', 'PUBLIC', '-//W3C//DTD XHTML 1.0 Transitional//EN',
                       'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd')
    title = 'No Title'
    # Meta information is name/value pairs
    http_equiv = [('Content-Type', 'text/html; charset=utf-8')]
    meta = []

def escape_attribute_value(value):
    #TODO: Handle escaping, etc.
    return value

def format_attribute(name, value):
    return '%s="%s"' % (name, escape_attribute_value(value))

class XHTMLWriter(TextFile):
    def __init__(self, file_or_path, indent_by  = 2):
        TextFile.__init__(self, file_or_path, indent_by = indent_by)
    def write_xhtml(self, xhtml):
        self._write_block(xhtml)
    def _write_block(self, block):
        for element in block:
            lines = self._start_element(element)
            with self.indented():
                pass
    def _start_element(self, element):
        lines = ['<%s' % element.tag]
        if element.attrs:
            attr_lines = []
            for (name, value) in element.iteritems():
                attr_lines.append(format_attribute(name, value))
            if (len(''.join(element.attrs.values())) + (len(element.attrs.values()) * 4)) < 40:
                lines[0] = '%s %s' % (lines[0], ' '.join([lines[0]] + attr_lines))
            else:
                lines.extend(attr_lines)
        if len(element.textlines) == 0:
            <D-k>



class XHTMLDocument(TextFile):
    def __init__(self,
                 indent_by  = 2,
                 title      = DEFAULT.title,
                 doctype    = DEFAULT.doctype,
                 http_equiv = DEFAULT.http_equiv,
                 meta       = DEFAULT.meta):
        self.title       = title
        self.doctype     = doctype
        self.http_equiv  = http_equiv
        self.meta        = meta
        self.need_header = True

class Element(object):
    def __init__(self, writer, tag, *textlines, **attrs):
        self.writer    = writer
        self.tag       = tag
        self.textlines = textlines
        self.attrs     = attrs
    def __enter__(self):
        if self.attrs:
            self.write('<%s' % self.tag)
            with self.writer.indented():
                names = self.attrs.keys()
                for name in names:
                    self.write('%s="%s"' % (name, escape_attribute_value(self.attrs[names])))
            self.write('>')
        else:
            self.write('<%s>' % self.tag)
    def __exit__(self, exc_type, exc_value, traceback):
        self.write('</%s>' % self.tag)
    def write(self, *lines_and_sublists):
        self.writer.write(*lines_and_sublists)

class TITLE(Element):
    def __init__(self, writer, **attrs):
        Element.__init__(self, writer, 'TITLE', **attrs)

class HEAD(Element):
    def __init__(self, writer, **attrs):
        Element.__init__(self, writer, 'HEAD', **attrs)
    def __enter__(self):
        self.write('<!DOCTYPE %s>' % self.writer.doctype)
        Element.__enter__(self)
        with self.writer.indented():
            for name, content in self.writer.http_equiv:
                self.write('<META HTTP-EQUIV="%s" CONTENT="%s">' % (name, content))
            for name, content in self.writer.meta:
                self.write('<META NAME="%s" CONTENT="%s">' % (name, content))
            with TITLE(self.writer):
                self.write(self.title)

class BODY(Element):
    def __init__(self, writer, **attrs):
        Element.__init__(self, writer, 'BODY', **attrs)

class H1(Element):
    def __init__(self, writer, **attrs):
        Element.__init__(self, writer, 'H1', **attrs)

class H2(Element):
    def __init__(self, writer, **attrs):
        Element.__init__(self, writer, 'H2', **attrs)

class H3(Element):
    def __init__(self, writer, **attrs):
        Element.__init__(self, writer, 'H3', **attrs)

class H4(Element):
    def __init__(self, writer, **attrs):
        Element.__init__(self, writer, 'H4', **attrs)

class H5(Element):
    def __init__(self, writer, **attrs):
        Element.__init__(self, writer, 'H5', **attrs)

class H6(Element):
    def __init__(self, writer, **attrs):
        Element.__init__(self, writer, 'H6', **attrs)

class DL(Element):
    def __init__(self, writer, **attrs):
        Element.__init__(self, writer, 'DL', **attrs)

class A(Element):
    def __init__(self, writer, **attrs):
        Element.__init__(self, writer, 'A', **attrs)
