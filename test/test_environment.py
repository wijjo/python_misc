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
import unittest
from scriptbase.environment import Environment

class TestEnvironment(unittest.TestCase):

    def test_import_export(self):
        test_name = 't_e_s_t_v_a_r'
        test_value = 'a_b_c_d'
        env_dict = lambda e: {n: e[n] for n in e if n[0].isalpha() and n not in ['SHLVL']}
        etest = Environment.import_from_shell()
        eshell = env_dict(os.environ)
        self.assertEqual(etest.vars, eshell)
        self.assertTrue(test_name not in os.environ or os.environ[test_name] != test_value)
        etest.vars[test_name] = test_value
        etest.export_to_shell()
        eshell = env_dict(os.environ)
        self.assertTrue(test_name in eshell)
        self.assertEqual(eshell[test_name], test_value)
        self.assertEqual(etest.vars, eshell)

    def test_attribute_access(self):
        e = Environment()
        e.vars.a = 1
        e.vars['b'] = 2
        self.assertEqual(e.vars['a'], 1)
        self.assertEqual(e.vars.b, 2)

    def test_clone(self):
        e1 = Environment(a=1, b=2)
        e2 = e1.clone()
        self.assertEqual(e1.vars, e2.vars)
        self.assertEqual(e1, e2)

    def test_diff(self):
        e1 = Environment(a=1, b=2, c=3, d=4, e=5)
        e2 = Environment(a=0, b=1, d=3, f=6, g=7)
        d = e2.diff(e1)
        self.assertEqual(d.added, [('f', 6), ('g', 7)])
        self.assertEqual(d.modified, [('a', 1, 0), ('b', 2, 1), ('d', 4, 3)])
        self.assertEqual(d.removed, [('c', 3), ('e', 5)])

    def test_paths(self):
        # Use os.pathsep so that the test is OS-neutral.
        e = Environment(p=os.pathsep.join(['/a/b', '/c/d/e', '/c/d/f', '/g/h']))
        e.prepend_to_path('p', '/m/n', '/c/d/f')
        self.assertEqual(e.vars.p, os.pathsep.join(['/m/n', '/c/d/f', '/a/b', '/c/d/e', '/g/h']))
        e.remove_from_path('p', '/a/b', '/x/y', '/c/d')
        self.assertEqual(e.vars.p, os.pathsep.join(['/m/n', '/g/h']))
        e.append_to_path('p', '/m/n', '/c/d/f')
        self.assertEqual(e.vars.p, os.pathsep.join(['/m/n', '/g/h', '/c/d/f']))

    def test_substitute(self):
        e = Environment(a='a12defghia1xdefghia12defghi')
        e.substitute_value('a', r'a(\d)[^C]', r'a\1C', count=2)
        self.assertEqual(e.vars.a, 'a1Cdefghia1Cdefghia12defghi')

if __name__ == '__main__':
    unittest.main()
