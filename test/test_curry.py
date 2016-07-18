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

from scriptbase.curry import Before, After, Remove, Tweak
import unittest

class TestCurry(unittest.TestCase):

    def test_positional_args(self):
        def foo(a, b, c):
            return a, b, c
        self.assertEqual(foo(1, 2, 3), (1, 2, 3))
        self.assertRaises(TypeError, Tweak, foo, 9)
        self.assertRaises(TypeError, Tweak, foo, before=9)
        self.assertEqual(Tweak(foo, before=(1, 2))(3), (1, 2, 3))
        self.assertEqual(Tweak(foo, after=(1, 2))(3), (3, 1, 2))
        self.assertEqual(Tweak(foo, before=(1,), after=(2,))(3), (1, 3, 2))

    def test_before(self):
        def foo(*a):
            return a
        self.assertEqual(Before(foo, 1, 2, 3)(4, 5, 6), (1, 2, 3, 4, 5, 6))

    def test_after(self):
        def foo(*a):
            return a
        self.assertEqual(After(foo, 1, 2, 3)(4, 5, 6), (4, 5, 6, 1, 2, 3))

    def test_remove(self):
        def foo(*a):
            return a
        self.assertEqual(Remove(foo, 1, 2)('a', 'b', 'c', 'd'), ('a', 'd'))

    def test_combination(self):
        def foo(*a):
            return a
        self.assertEqual(Remove(Before(foo, 'a', 'b'), 0)('c', 'd'), ('a', 'b', 'd'))
        self.assertEqual(Remove(Before(After(foo, 'x', 'y'), 'a', 'b'), 1, 3)('h', 'i', 'j', 'k'),
                         ('a', 'b', 'h', 'j', 'x', 'y'))

    def test_positional_and_keyword_args(self):
        def foo(*a, **k):
            return a, k
        a, k = foo(1, 2, 3, a=1, b=2, c=3)
        self.assertEqual(a, (1, 2, 3))
        self.assertEqual(k, dict(a=1, b=2, c=3))
        cfoo1 = Tweak(foo, after=(10, 11, 12), merge=dict(n=11, o=12, p=13))
        a, k = cfoo1(1, 2, 3, a=1, b=2, c=3)
        self.assertEqual(a, (1, 2, 3, 10, 11, 12))
        self.assertEqual(k, dict(a=1, b=2, c=3, n=11, o=12, p=13))
        cfoo2 = Tweak(cfoo1, before=(100, 101, 102), merge=dict(x=101, y=102, z=103))
        a, k = cfoo2(1, 2, 3, a=1, b=2, c=3)
        self.assertEqual(a, (100, 101, 102, 1, 2, 3, 10, 11, 12))
        self.assertEqual(k, dict(a=1, b=2, c=3, n=11, o=12, p=13, x=101, y=102, z=103))

if __name__ == '__main__':
    unittest.main()
