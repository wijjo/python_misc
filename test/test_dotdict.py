# Copyright 2017 Steven Cooper
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

import unittest

from scriptbase.dotdict import DotDict

class TestDotDict(unittest.TestCase):

    def setUp(self):
        self.dd = DotDict()

    def test_one_level(self):
        self.dd.a = 111
        self.dd['b'] = 222
        self.dd.c(333)
        self.dd['d'](444)
        self.assertIsInstance(self.dd['a'], DotDict)
        self.assertIsInstance(self.dd['b'], DotDict)
        self.assertIsInstance(self.dd['c'], DotDict)
        self.assertIsInstance(self.dd['d'], DotDict)
        self.assertIsInstance(self.dd.a, DotDict)
        self.assertIsInstance(self.dd.b, DotDict)
        self.assertIsInstance(self.dd.c, DotDict)
        self.assertIsInstance(self.dd.d, DotDict)
        self.assertEqual(self.dd['a'](), 111)
        self.assertEqual(self.dd['b'](), 222)
        self.assertEqual(self.dd['c'](), 333)
        self.assertEqual(self.dd['d'](), 444)
        self.assertEqual(self.dd.a(), 111)
        self.assertEqual(self.dd.b(), 222)
        self.assertEqual(self.dd.c(), 333)
        self.assertEqual(self.dd.d(), 444)
        # Non-existent entries are still DotDict's.
        self.assertIsInstance(self.dd.x, DotDict)
        self.assertIsInstance(self.dd['y'], DotDict)

    def test_multi_level(self):
        self.dd.a = 111
        self.dd.a.b.c = 222
        self.dd[11](1011)
        self.dd[11][12](1012)
        self.dd[11][12][13](1013)
        self.assertIsInstance(self.dd.a, DotDict)
        self.assertIsInstance(self.dd.a.b, DotDict)
        self.assertIsInstance(self.dd.a.b.c, DotDict)
        self.assertIsInstance(self.dd[11], DotDict)
        self.assertIsInstance(self.dd[11][12], DotDict)
        self.assertIsInstance(self.dd[11][12][13], DotDict)
        self.assertEqual(self.dd.a(), 111)
        self.assertEqual(self.dd.a.b(), None)
        self.assertEqual(self.dd.a.b.c(), 222)
        self.assertEqual(self.dd[11](), 1011)
        self.assertEqual(self.dd[11][12](), 1012)
        self.assertEqual(self.dd[11][12][13](), 1013)

if __name__ == '__main__':
    unittest.main()
