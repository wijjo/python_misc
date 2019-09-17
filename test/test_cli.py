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

"""Scriptbase cli module unit tests."""

import sys
import unittest
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from contextlib import contextmanager

from scriptbase import cli
from scriptbase import console

DEFAULT_TIMEOUT = 60

@cli.Main('Access remote web pages', support_dry_run=True, args=[
    cli.Integer('timeout', 'time-out in seconds', '--timeout', default=DEFAULT_TIMEOUT)])
def main(runner):   #pylint: disable=unused-argument
    """Test main."""
    pass

@cli.Command(description='download page', args=[
    cli.String('URL', 'URL of page to download'),
    cli.Boolean('PDF', 'convert to a PDF', '--pdf')])
def download(runner):
    """Test download command."""
    if runner.arg.DRY_RUN:
        print('Download(dry-run): %s' % runner.arg.URL)
    elif runner.arg.PDF:
        print('Download(PDF): %s' % runner.arg.URL)
    else:
        print('Download(HTML): %s' % runner.arg.URL)

@cli.Command(description='display various statistics', args=[
    cli.String('URL', 'URL of page to download')])
def show(runner):   #pylint: disable=unused-argument
    """Test show base command."""
    print('show')

@cli.Command(name='route', description='display route to host', parent=show)
def route(runner):
    """Test show route command."""
    print('show_route(%s)' % runner.arg.URL)

@cli.Command(description='display latency to host', parent=show)
def latency(runner):
    """Test show latency command."""
    print('show_latency(%s)' % runner.arg.URL)

@contextmanager
def cli_main(*command_line):
    """CLI main."""
    stdout_stream = StringIO()
    stderr_stream = StringIO()
    out, sys.stdout = sys.stdout, stdout_stream
    err, sys.stderr = sys.stderr, stderr_stream
    console.set_streams(stdout_stream, stderr_stream)
    cmd_args = ['test_cli'] + list(command_line)
    cli.main(command_line=cmd_args)
    sys.stdout.seek(0)
    sys.stderr.seek(0)
    class _Outputs(object):
        def __init__(self):
            self.out = sys.stdout.read().strip()
            self.err = sys.stderr.read().strip()
        def __str__(self):
            return '\n%s%s===' % ('=== STDOUT ===\n%s\n' % self.out if self.out else '',
                                  '=== STDERR ===\n%s\n' % self.err if self.err else '')
    yield _Outputs()
    sys.stdout = out
    sys.stderr = err
    console.set_streams(out, err)

class TestCLI(unittest.TestCase):
    """CLI test case."""

    def __init__(self, name):
        """CLI test case constructor."""
        unittest.TestCase.__init__(self, name)

    def xtest_no_command(self):
        """Test handling of no command being declared."""
        with self.assertRaises(SystemExit):
            with cli_main() as result:
                self.fail(msg=result)

    def xtest_help(self):
        """Test CLI help."""
        with cli_main('help') as result:
            self.assertTrue(result.out.startswith('usage: '), msg=result)

    def xtest_download(self):
        """Test command with options and arguments."""
        with cli_main('download', 'aa') as o:
            self.assertTrue(o.out.startswith('Download(HTML): aa'), msg=o)
        with cli_main('download', '--pdf', 'aa') as o:
            self.assertTrue(o.out.startswith('Download(PDF): aa'), msg=o)
        with cli_main('--dry-run', 'download', 'aa') as o:
            self.assertTrue(o.out.startswith('Download(dry-run): aa'), msg=o)

    def test_show(self):
        """Test command with sub-commands."""
        with self.assertRaises(SystemExit):
            with cli_main('show') as result:
                self.fail(msg=result)
        with self.assertRaises(SystemExit):
            with cli_main('show', 'glorp') as result:
                self.fail(msg=result)
        with cli_main('show', 'aa', 'latency') as result:
            self.assertEqual('show_latency(aa)', result.out, msg=result)
        with cli_main('show', 'aa', 'route') as result:
            self.assertEqual('show_route(aa)', result.out, msg=result)

if __name__ == '__main__':
    unittest.main()
