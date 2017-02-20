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
from copy import copy

from scriptbase import pspace

def wrap_space_test(num_spaces):
    def decorator(test_func):
        def wrapper(test_case):
            try:
                spaces = [pspace.create() for n in range(num_spaces)]
                test_func(test_case, *spaces)
            except AssertionError:
                print('\n*** dump (due to assertion error) ***')
                for n in range(num_spaces):
                    print('space[%d]: %s' % (n, spaces[n]._store_.all_properties))
                raise
        return wrapper
    return decorator

DICT_1 = {
    'a': {
        'b': 111,
        'c': 222,
        'd': {
            'e': 333,
            'f': 444,
        },
    },
    'g': 555,
    'h': 666,
}

DICT_1_PAIRS = [
    ('a.b', 111),
    ('a.c', 222),
    ('a.d.e', 333),
    ('a.d.f', 444),
    ('g', 555),
    ('h', 666),
]

DICT_1_FLAT = dict(DICT_1_PAIRS)

DICT_2_FLAT = {
    'p': 123,
    'p.q': 456,
    'p.q.r': 789,
    'x': 'abc',
    'x.y': 'def',
    'x.y.z': 'ghi',
}

def splice_dicts(dtgt, ktgt, dsrc, ksrc):
    dret = copy(dtgt)
    num_parts = ksrc.count('.') + 1
    for key, value in dsrc.items():
        if '.'.join(key.split('.')[:num_parts]) == ksrc:
            dret['.'.join([ktgt, key])] = value
    return dret

def prefix_dict(d, prefix):
    return dict([('.'.join([prefix, n]), v) for n, v in d.items()])

class TestPSpace(unittest.TestCase):

    @wrap_space_test(1)
    def test_root(self, sp):
        self.assertEqual(sp(), None)
        sp(1)
        self.assertEqual(sp(), 1)
        sp(2)
        self.assertEqual(sp(), 2)

    @wrap_space_test(1)
    def test_one_level(self, sp):
        sp.a = 111
        sp['b'] = 222
        sp.c(333)
        sp['d'](444)
        self.assertEqual(sp['a'](), 111)
        self.assertEqual(sp['b'](), 222)
        self.assertEqual(sp['c'](), 333)
        self.assertEqual(sp['d'](), 444)
        self.assertEqual(sp.a(), 111)
        self.assertEqual(sp.b(), 222)
        self.assertEqual(sp.c(), 333)
        self.assertEqual(sp.d(), 444)

    @wrap_space_test(1)
    def test_multi_level(self, sp):
        sp.a = 111
        sp.a.b.c = 222
        sp[11](1011)
        sp[11][12](1012)
        sp[11][12][13](1013)
        self.assertEqual(sp.a(), 111)
        self.assertEqual(sp.a.b(), None)
        self.assertEqual(sp.a.b.c(), 222)
        self.assertEqual(sp[11](), 1011)
        self.assertEqual(sp[11][12](), 1012)
        self.assertEqual(sp[11][12][13](), 1013)

    @wrap_space_test(1)
    def test_iterate_space(self, sp):
        pspace.update_from_dictionary(sp, DICT_1)
        actual = dict([(n, v) for n, v in sp])
        self.assertEqual(actual, DICT_1_FLAT)

    @wrap_space_test(1)
    def test_iterate_sub_space(self, sp):
        pspace.update_from_dictionary(sp, DICT_1)
        actual = dict([(n, v) for n, v in sp.a])
        expect = pspace.dict_flatten(prefix_dict(DICT_1['a'], 'a'))
        self.assertEqual(actual, expect)

    @wrap_space_test(1)
    def test_write_update_from_dictionary_nested(self, sp):
        pspace.update_from_dictionary(sp, DICT_1)
        sp_dict = dict(pspace.walk(sp))
        self.assertEqual(sp_dict, DICT_1_FLAT)

    @wrap_space_test(1)
    def test_write_update_from_dictionary_flat(self, sp):
        pspace.update_from_dictionary(sp, DICT_1_FLAT)
        sp_dict = dict(pspace.walk(sp))
        self.assertEqual(sp_dict, DICT_1_FLAT)

    @wrap_space_test(1)
    def test_update_from_sequence(self, sp):
        pspace.update_from_sequence(sp, DICT_1_PAIRS)
        sp_dict = dict(pspace.walk(sp))
        self.assertEqual(sp_dict, DICT_1_FLAT)

    @wrap_space_test(2)
    def test_copy_from_space(self, sp1, sp2):
        pspace.update_from_dictionary(sp1, DICT_1_FLAT)
        pspace.update_from_dictionary(sp2, DICT_2_FLAT)
        pspace.copy_from_space(sp2, sp1)
        sp2_dict = dict(pspace.walk(sp2))
        sp2_dict_expect = copy(DICT_2_FLAT)
        sp2_dict_expect.update(DICT_1_FLAT)
        self.assertEqual(sp2_dict, sp2_dict_expect)

    @wrap_space_test(2)
    def test_copy_from_sub_space(self, sp1, sp2):
        pspace.update_from_dictionary(sp1, DICT_1_FLAT)
        pspace.update_from_dictionary(sp2, DICT_2_FLAT)
        pspace.copy_from_space(sp2.x, sp1.a)
        actual = dict(pspace.walk(sp2))
        expect = splice_dicts(DICT_2_FLAT, 'x', DICT_1_FLAT, 'a')
        self.assertEqual(actual, expect)

    @wrap_space_test(2)
    def test_assign_sub_space(self, sp1, sp2):
        pspace.update_from_dictionary(sp1, DICT_1_FLAT)
        pspace.update_from_dictionary(sp2, DICT_2_FLAT)
        sp2.x = sp1.a
        actual = dict(pspace.walk(sp2))
        expect = splice_dicts(DICT_2_FLAT, 'x', DICT_1_FLAT, 'a')
        self.assertEqual(actual, expect)

    @wrap_space_test(1)
    def test_descend(self, sp):
        pspace.descend(sp, 'a')(111)
        pspace.descend(pspace.descend(pspace.descend(sp, 'a'), 'b'), 'c')(222)
        self.assertEqual(sp.a(), 111)
        self.assertEqual(sp.a.b(), None)
        self.assertEqual(sp.a.b.c(), 222)

    @wrap_space_test(1)
    def test_set_value(self, sp):
        pspace.descend(sp, 'a')(111)
        pspace.descend(pspace.descend(pspace.descend(sp, 'a'), 'b'), 'c')(222)
        pspace.set_value(sp.a, 111)
        pspace.set_value(sp.a.b.c, 222)
        self.assertEqual(sp.a(), 111)
        self.assertEqual(sp.a.b(), None)
        self.assertEqual(sp.a.b.c(), 222)

    @wrap_space_test(1)
    def test_walk(self, sp):
        pspace.update_from_dictionary(sp, DICT_1)
        actual = dict(pspace.walk(sp))
        self.assertEqual(actual, DICT_1_FLAT)

    @wrap_space_test(1)
    def test_walk_partial(self, sp):
        pspace.update_from_dictionary(sp, DICT_1)
        actual = dict(pspace.walk(sp, min_depth=1, max_depth=2))
        expect = dict([(k, v) for k, v in DICT_1_FLAT.items() if k.count('.') in [1, 2]])
        self.assertEqual(actual, expect)

    @wrap_space_test(1)
    def test_walk_filtered(self, sp):
        pspace.update_from_dictionary(sp, DICT_1)
        actual = dict(pspace.walk(sp, min_depth=1, max_depth=2, filter_func=lambda k, v: v < 400))
        expect = dict([(k, v) for k, v in DICT_1_FLAT.items() if k.count('.') in [1, 2] and v < 400])
        self.assertEqual(actual, expect)

    @wrap_space_test(1)
    def test_walk_relative_root(self, sp):
        pspace.update_from_dictionary(sp, DICT_1)
        actual = dict(pspace.walk(sp, min_depth=1, max_depth=2, relative=True))
        expect = dict([(k, v) for k, v in DICT_1_FLAT.items() if k.count('.') in [1, 2]])
        self.assertEqual(actual, expect)

    @wrap_space_test(1)
    def test_walk_relative_sub_space(self, sp):
        pspace.update_from_dictionary(sp, DICT_1)
        actual = dict(pspace.walk(sp.a, min_depth=2, max_depth=2, relative=True))
        expect = dict([(k[2:], v) for k, v in DICT_1_FLAT.items() if k.count('.') > 1])
        self.assertEqual(actual, expect)

    @wrap_space_test(1)
    def test_del_operator(self, sp):
        pspace.update_from_dictionary(sp, DICT_1)
        del sp.g
        del sp['a.d.e']
        actual = dict(pspace.walk(sp))
        expect = dict([(k, v) for k, v in DICT_1_FLAT.items() if k not in ['g', 'a.d.e']])
        self.assertEqual(actual, expect)

    @wrap_space_test(1)
    def test_delete(self, sp):
        pspace.update_from_dictionary(sp, DICT_1)
        pspace.delete(sp.g)
        pspace.delete(sp.a.d)
        actual = dict(pspace.walk(sp))
        expect = dict([(k, v) for k, v in DICT_1_FLAT.items() if k != 'g' and not k.startswith('a.d.')])
        self.assertEqual(actual, expect)

    @wrap_space_test(1)
    def test_delete_partial(self, sp):
        pspace.update_from_dictionary(sp, DICT_1)
        pspace.delete(sp.a, min_depth=1, max_depth=1)
        actual = dict(pspace.walk(sp))
        expect = dict([(k, v) for k, v in DICT_1_FLAT.items() if k.count('.') != 1 or not k.startswith('a.')])
        self.assertEqual(actual, expect)

    def test_build_address(self):
        for pair, combined in (
            ((None, None), ''),
            (('', None), ''),
            ((None, ''), ''),
            (('', ''), ''),
            ((False, False), 'False.False'),
            (('', False), 'False'),
            ((False, ''), 'False'),
            ((0, 0), '0.0'),
            (('', 0), '0'),
            ((0, ''), '0'),
            (('a', ''), 'a'),
            (('a.b', ''), 'a.b'),
            (('', 'a'), 'a'),
            (('', 'a.b'), 'a.b'),
            (('a', 'b'), 'a.b'),
            (('a.b', 'c'), 'a.b.c'),
            (('a', 'b.c'), 'a.b.c'),
            (('a.b', 'c.d'), 'a.b.c.d'),
        ):
            self.assertEqual(pspace.build_address(*pair), combined)

    def test_dict_flatten_items(self):
        actual = dict(pspace.dict_flatten_items(DICT_1))
        self.assertEqual(actual, DICT_1_FLAT)

    def test_dict_flatten(self):
        actual = pspace.dict_flatten(DICT_1)
        self.assertEqual(actual, DICT_1_FLAT)

if __name__ == '__main__':
    unittest.main()
