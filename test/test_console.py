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

import os
import unittest
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from scriptbase import console

def expect(self, *lines):
    return os.linesep.join(lines)

class TestConsole(unittest.TestCase):

    def setUp(self):
        self.stdout = StringIO()
        self.stderr = StringIO()
        console.set_streams(self.stdout, self.stderr)
        self.set_verbose(False)
        self.set_debug(False)
        console.set_indentation('.')

    def set_verbose(self, verbose):
        self.verbose = verbose
        console.set_verbose(verbose)

    def set_debug(self, debug):
        self.debug = debug
        console.set_debug(debug)

    def finish(self, truncate=None):
        self.stdout.seek(0)
        self.stderr.seek(0)
        def get_strings(stream):
            return [s[:truncate] if truncate else s for s in stream.read().rstrip().split(os.linesep)]
        out = get_strings(self.stdout)
        err = get_strings(self.stderr)
        self.stdout.truncate()
        self.stderr.truncate()
        return out, err

    def test_simple(self):
        console.info('info')
        console.verbose_info('verbose-')
        self.set_verbose(True)
        console.verbose_info('verbose+')
        console.debug('debug-')
        self.set_debug(True)
        console.debug('debug+')
        console.warning('warning')
        console.error('error')
        out, err = self.finish()
        self.assertEqual(out, ['info', 'INFO2: verbose+'])
        self.assertEqual(err, ['DEBUG: debug+', 'WARNING: warning', 'ERROR: error'])

    def test_nested(self):
        console.info('1', ['1a', ['1b1', '1b2']])
        out, err = self.finish()
        self.assertEqual(out, ['1', '.1a', '..1b1', '..1b2'])

    def test_exception(self):
        try:
            1 + ''
        except Exception as e:
            console.error('oh no!', e)
            out, err = self.finish(truncate=40)
            self.assertEqual(err, ['ERROR: oh no!', 'ERROR: Exception[TypeError]: unsupported'])

    def test_substitution(self):
        console.info('The {weather} in {country}', 'falls mainly on the {area}',
                     weather='rain', country='Spain', area='plain')
        out, err = self.finish()
        self.assertEqual(out, ['The rain in Spain', 'falls mainly on the plain'])

if __name__ == '__main__':
    unittest.main()
