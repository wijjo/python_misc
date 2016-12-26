#!/usr/bin/env python
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

from scriptbase import cli

import sys
import unittest
import re
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from contextlib import contextmanager


STDERR = sys.stderr
TIMEOUT = 60

@cli.Main('Access remote web pages', support_dryrun=True, args=[
    cli.Integer('timeout', 'time-out in seconds', '--timeout', default=TIMEOUT)])
def main(runner):
    global TIMEOUT
    TIMEOUT = runner.arg.timeout

@cli.Command(description='download page', args=[
    cli.String('url', 'URL of page to download'),
    cli.Boolean('pdf', 'convert to a PDF', '--pdf')])
def download(runner):
    if runner.arg.dryrun:
        print('Download(dryrun): %s' % runner.arg.url)
    elif runner.arg.pdf:
        print('Download(PDF): %s' % runner.arg.url)
    else:
        print('Download(HTML): %s' % runner.arg.url)

@cli.Command(description='display various statistics', args=[
    cli.String('url', 'URL of page to download')])
def show(runner):
    print('show')

@cli.Command(description='display route to host', parent=show)
def route(runner):
    print('show_route(%s)' % runner.arg.url)

@cli.Command(description='display latency to host', parent=show)
def latency(runner):
    print('show_latency(%s)' % runner.arg.url)

class TestStream(object):
    def __init__(self, tag=''):
        self.output = []
    def write(self, s):
        self.output.append(s)
    def has_line(self, s):
        for line in output:
            if line.startswith(s):
                return True
        return False
    def __str__(self):
        return '\n'.join(['%s%s' % (self.tag, o) for o in self.output])

@contextmanager
def cli_main(*command_line):
    out, sys.stdout = sys.stdout, StringIO()
    err, sys.stderr = sys.stderr, StringIO()
    cli.main(command_line=(['test_cli'] + list(command_line)))
    sys.stdout.seek(0)
    sys.stderr.seek(0)
    class Outputs(object):
        def __init__(self):
            self.out = sys.stdout.read().strip()
            self.err = sys.stderr.read().strip()
        def __str__(self):
            return '\n%s%s===' % ('=== STDOUT ===\n%s\n' % self.out if self.out else '',
                                  '=== STDERR ===\n%s\n' % self.err if self.err else '')
    yield Outputs()
    sys.stdout = out
    sys.stderr = err

class TestCLI(unittest.TestCase):

    def __init__(self, name):
        unittest.TestCase.__init__(self, name)

    def test_no_command(self):
        with self.assertRaises(SystemExit):
            with cli_main() as o:
                self.fail(msg=o)

    def test_help(self):
        with cli_main('help') as o:
            self.assertTrue(o.out.startswith('usage: '), msg=o)

    def test_download(self):
        with cli_main('download', 'aa') as o:
            self.assertTrue(o.out.startswith('Download(HTML): aa'), msg=o)
        with cli_main('download', '--pdf', 'aa') as o:
            self.assertTrue(o.out.startswith('Download(PDF): aa'), msg=o)
        with cli_main('--dry-run', 'download', 'aa') as o:
            self.assertTrue(o.out.startswith('Download(dryrun): aa'), msg=o)

    def test_show(self):
        with self.assertRaises(SystemExit):
            with cli_main('show') as o:
                self.fail(msg=o)
        with self.assertRaises(SystemExit):
            with cli_main('show', 'glorp') as o:
                self.fail(msg=o)
        with cli_main('show', 'aa', 'latency') as o:
            self.assertEquals('show_latency(aa)', o.out, msg=o)
        with cli_main('show', 'aa', 'route') as o:
            self.assertEquals('show_route(aa)', o.out, msg=o)

if __name__ == '__main__':
    unittest.main()
