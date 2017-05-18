# Copyright 2016-17 Steven Cooper
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

"""Password Hasher module."""

# Author: Steve Cooper
# Created: 01/04/11
#
# SHA1 code based on:
# A JavaScript implementation of the Secure Hash Algorithm, SHA-1, as defined
# in FIPS PUB 180-1
# Version 2.1a Copyright Paul Johnston 2000 - 2002.
# Other contributors: Greg Holt, Andrew Kepert, Ydnar, Lostinet
# Distributed under the BSD License
# See http://pajhome.org.uk/crypt/md5 for details.

import sys
import re
import ctypes

from . import utility

# This code was converted from legacy Javascript code.
# Python style suffers a bit.
#pylint: disable=invalid-name,too-many-locals,too-many-arguments

RE_NON_NUMERIC = re.compile('[^0-9]+')
RE_NON_ALPHA_NUMERIC = re.compile('[^a-z0-9]+', re.IGNORECASE)

HEX_UPPER_CASE = False  # hex uppercase format?
BASE_64_PADDING = ''    # base-64 pad character. "=" for strict RFC compliance
BITS_PER_CHARACTER = 8  # bits per input character. 8 - ASCII; 16 - Unicode

HEX_CHARACTERS = "0123456789ABCDEF" if HEX_UPPER_CASE else "0123456789abcdef"

BASE_64_CHARACTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _core_sha1(x, size):
    log.dump_hex(3, x=x)
    log.dump(3, size=size)
    i = (size >> 5)
    if i >= len(x):
        x.extend([0]*(i-len(x)+1))
    x[i] |= 0x80 << (24 - size % 32)
    j = ((size + 64 >> 9) << 4) + 15
    if len(x) <= j:
        x.extend([0]*(j-len(x)+1))
    x[j] = size
    w = [0] * 80
    a = 1732584193
    b = -271733879
    c = -1732584194
    d = 271733878
    e = -1009589776

    def _sha1_ft(t, b, c, d):
        if t < 20:
            return (b & c) | ((~b) & d)
        if t < 40:
            return b ^ c ^ d
        if t < 60:
            return (b & c) | (b & d) | (c & d)
        return b ^ c ^ d

    def _sha1_kt(t):
        if t < 20:
            return 1518500249
        if t < 40:
            return 1859775393
        if t < 60:
            return -1894007588
        return -899497514

    for i in range(0, len(x), 16):
        olda = a
        oldb = b
        oldc = c
        oldd = d
        olde = e
        for j in range(80):
            log.dump_hex(3, {"(%d,%d):a,b,c,d,e" % (i, j): [a, b, c, d, e]})
            if j < 16:
                w[j] = x[i + j]
            else:
                w[j] = _rol(w[j-3] ^ w[j-8] ^ w[j-14] ^ w[j-16], 1)
            log.dump_hex(3, w=w)
            t = _safe_add(_safe_add(_rol(a, 5), _sha1_ft(j, b, c, d)),
                          _safe_add(_safe_add(e, w[j]), _sha1_kt(j)))
            e = d
            d = c
            c = _rol(b, 30)
            b = a
            a = t
        log.dump_hex(3, {"(%d):a,b,c,d,e" % i: [a, b, c, d, e]})
        a = _safe_add(a, olda)
        b = _safe_add(b, oldb)
        c = _safe_add(c, oldc)
        d = _safe_add(d, oldd)
        e = _safe_add(e, olde)
    return [a, b, c, d, e]


def _core_hmac_sha1(key, data):
    log.dump(2, key=key)
    log.dump(2, data=data)

    class _NumArray(object):
        def __init__(self, a):
            self.a = a

        def __getitem__(self, i):
            try:
                return self.a[i]
            except IndexError:
                return 0

        def __iter__(self):
            for i in self.a:
                yield i

        def __len__(self):
            return len(self.a)

    bkey = _NumArray(_str2binb(key))
    if len(bkey) > 16:
        bkey = _core_sha1(bkey, len(key) * BITS_PER_CHARACTER)
    log.dump_hex(2, bkey=bkey)
    ipad = [(bkey[i] ^ 0x36363636) for i in range(16)]
    opad = [(bkey[i] ^ 0x5C5C5C5C) for i in range(16)]
    log.dump_hex(2, ipad=ipad)
    log.dump_hex(2, opad=opad)
    hash_code = _core_sha1(ipad + _str2binb(data), 512 + (len(data) * BITS_PER_CHARACTER))
    log.dump_hex(2, hash_code=hash_code)
    res = _core_sha1(opad + hash_code, 512 + 160)
    log.dump_hex(2, core_hmac_sha1=res)
    return res


def _left_shift(num, cnt):
    return ctypes.c_int32(ctypes.c_uint32(num).value << cnt).value


def _right_shift(num, cnt):
    return ctypes.c_int32(ctypes.c_int32(num).value >> cnt).value


def _right_shift_zero_fill(num, cnt):
    return ctypes.c_int32(ctypes.c_uint32(num).value >> cnt).value


def _safe_add(x, y):
    lsw = (x & 0xFFFF) + (y & 0xFFFF)
    msw = _right_shift(x, 16) + _right_shift(y, 16) + _right_shift(lsw, 16)
    res = _left_shift(msw, 16) | (lsw & 0xFFFF)
    log.dump_hex(3, safe_add=[x, y, res])
    return res


def _rol(num, cnt):
    n1 = _left_shift(num, cnt)
    n2 = _right_shift_zero_fill(num, 32 - cnt)
    res = n1 | n2
    log.dump(3, rol=[num, cnt, n1, n2, res])
    return res


def _str2binb(str_value):
    bin_value_list = [0] * (((len(str_value) * BITS_PER_CHARACTER) >> 5) + 1)
    mask = (1 << BITS_PER_CHARACTER) - 1
    for char_index, char_value in enumerate(str_value):
        bin_value_index = (char_index * BITS_PER_CHARACTER) >> 5
        bin_value = (ord(char_value) & mask) << (
            32 - BITS_PER_CHARACTER - (char_index * BITS_PER_CHARACTER) % 32)
        bin_value_list[bin_value_index] |= bin_value
    log.dump_hex(3, {'str2binb(%s)' % str_value:  bin_value_list})
    return bin_value_list


def _binb2b64(binarray):
    str_value = ''
    def _chop(a, i, s):
        if i >> 2 >= len(a):
            return 0
        return ((a[i >> 2] >> 8 * (3 - i%4)) & 0xFF) << s
    log.dump_hex(3, binarray=binarray)
    for i in range(0, len(binarray) * 4, 3):
        b1 = _chop(binarray, i, 16)
        b2 = _chop(binarray, i+1, 8)
        b3 = _chop(binarray, i+2, 0)
        triplet = b1 | b2 | b3
        log.dump_hex(3, {'i,b1,b2,b3,triplet': [i, b1, b2, b3, triplet]})
        for j in range(4):
            if i * 8 + j * 6 > len(binarray) * 32:
                str_value += BASE_64_PADDING
            else:
                str_value += BASE_64_CHARACTERS[(triplet >> 6*(3-j)) & 0x3F]
    return str_value


class Log(object):
    """Logger for password hasher."""

    class _Entry(object):
        def __init__(self, tag, typ, msg):
            self.tag = tag
            self.typ = typ
            self.msg = msg

    def __init__(self):
        """Log constructor."""
        self.entries = []
        self.verbosity = 0

    def __del__(self):
        """Flush log before logger goes away."""
        self.flush()

    def dump(self, level, *args, **kwargs):
        """Dump args and keyword args."""
        if level <= self.verbosity:
            if '_hex' in kwargs:
                hex_value = kwargs['_hex']
                del kwargs['_hex']
            else:
                hex_value = False
            self._dump(args, kwargs, hex_value)

    def dump_hex(self, level, *args, **kwargs):
        """Dump args and keyword args in hex."""
        if level <= self.verbosity:
            self._dump(args, kwargs, True)

    def _dump(self, args, kwargs, hex_value):
        for arg in args:
            if hasattr(arg, '__getitem__') and hasattr(arg, 'keys'):
                for kw in arg:
                    tv = get_type_value(arg[kw], hex_value)
                    self.entries.append(Log._Entry(kw, tv.type_name, tv.value))
            else:
                tv = get_type_value(arg, hex_value)
                self.entries.append(Log._Entry('', tv.type_name, tv.value))
        for kw in kwargs:
            tv = get_type_value(kwargs[kw], hex_value)
            self.entries.append(Log._Entry(kw, tv.type_name, tv.value))

    def flush(self):
        """Flush log."""
        try:
            if self.entries:
                if self.verbosity > 0:
                    width = max([(len(entry.tag) + len(entry.typ) + 3) for entry in self.entries])
                else:
                    width = max([len(entry.tag) for entry in self.entries])
                format_string = '%%-%ds: %%s' % width
                for entry in self.entries:
                    if self.verbosity > 0:
                        tag = '%s (%s)' % (entry.tag, entry.typ)
                    else:
                        tag = entry.tag
                    print(format_string % (tag, entry.msg))
            self.entries = []
        except IOError:
            sys.stderr.write('* Output interrupted *')
            sys.exit(255)


log = Log()


def get_type_value(value, as_hex=False):
    """
    Return (type, string) pair for any value.

    Optionally use hex number format.
    """
    class _TypeValue(object):
        def __init__(self, type_name, value):
            self.type_name = type_name
            self.value = value

    def _check_integer():
        if not isinstance(value, int):
            return None
        if as_hex:
            return _TypeValue('Integer', '#%08X' % value)
        return _TypeValue('Integer', str(value))

    def _check_string():
        if utility.is_string(value):
            return _TypeValue('String[%d]' % len(value), value)
        return None

    def _check_dict():
        if not hasattr(value, '__getitem__') or not hasattr(value, 'keys'):
            return None
        keys = value.keys()
        keys.sort()
        s = ''
        for key in keys:
            if s:
                s += ', '
            s += '%s: %s' % (get_type_value(key).value, get_type_value(value[key], as_hex).value)
        return _TypeValue('Dict[%d]' % len(keys), s)

    def _check_list():
        if not hasattr(value, '__getitem__'):
            return None
        s = ''
        for char_value in value:
            if s:
                s += ', '
            s += get_type_value(char_value, as_hex).value
        return _TypeValue('List[%d]' % len(value), s)

    def _get_other():
        return _TypeValue(type(value).__name__, str(value))

    # Run the gauntlet of type checks
    tv = _check_integer()
    if tv is None:
        tv = _check_string()
    if tv is None:
        tv = _check_dict()
    if tv is None:
        tv = _check_list()
    if tv is None:
        tv = _get_other()
    return tv


def generate_hash_word(
        site_tag,
        master_key,
        hash_word_size=8,
        require_digit=False,
        require_punctuation=False,
        require_mixed_case=False,
        restrict_special=False,
        restrict_digits=False
):
    """Generate the hash word based on the specified options."""
    # Start with the SHA1-encrypted master key/site tag.
    s = _binb2b64(_core_hmac_sha1(master_key, site_tag))
    log.dump(1, sha1=s)
    # Use the checksum of all characters as a pseudo-randomizing seed to
    # avoid making the injected characters easy to guess.  Note that it
    # isn't random in the sense of not being deterministic (i.e.
    # repeatable).  Must share the same seed between all injected
    # characters so that they are guaranteed unique positions based on
    # their offsets.
    char_sum = 0
    for char_value in s:
        char_sum += ord(char_value)
    # Restrict digits just does a mod 10 of all the characters
    if restrict_digits:
        s = convert_to_digits(s, char_sum, hash_word_size)
    else:
        # Inject digit, punctuation, and mixed case as needed.
        if require_digit:
            s = inject_special_character(s, 0, 4, char_sum, hash_word_size, 48, 10)
        if require_punctuation and not restrict_special:
            s = inject_special_character(s, 1, 4, char_sum, hash_word_size, 33, 15)
        if require_mixed_case:
            s = inject_special_character(s, 2, 4, char_sum, hash_word_size, 65, 26)
            s = inject_special_character(s, 3, 4, char_sum, hash_word_size, 97, 26)
        # Strip out special characters as needed.
        if restrict_special:
            s = remove_special_characters(s, char_sum, hash_word_size)
    # Trim it to size.
    s = s[:hash_word_size]
    log.dump(1, final=s)
    return s


def inject_special_character(
        str_input,
        offset,
        reserved,
        seed,
        len_out,
        char_start,
        char_num
):
    """
    Inject a special character.

    This is a very specialized method to inject a character chosen from a range
    of character codes into a block at the front of a string if one of those
    characters is not already present.

    Parameters:
      str_input  = input string
      offset     = offset for position of injected character
      reserved   = # of offsets reserved for special characters
      seed       = seed for pseudo-randomizing the position and injected character
      len_out    = length of head of string that will eventually survive truncation.
      char_start = character code for first valid injected character.
      char_num   = number of valid character codes starting from char_start.
    """
    pos0 = seed % len_out
    pos = (pos0 + offset) % len_out
    # Check if a qualified character is already present
    # Write the loop so that the reserved block is ignored.
    for i in range(len_out - reserved):
        i2 = (pos0 + reserved + i) % len_out
        c = ord(str_input[i2])
        if c >= char_start and c < char_start + char_num:
            return str_input   # Already present - nothing to do
    if pos > 0:
        sHead = str_input[:pos]
    else:
        sHead = ""
    sInject = chr(((seed + ord(str_input[pos])) % char_num) + char_start)
    if pos + 1 < len(str_input):
        sTail = str_input[pos+1:]
    else:
        sTail = ""
    return (sHead + sInject + sTail)

def remove_special_characters(str_input, seed, len_out):
    """
    Remove/replace special characters.

    Another specialized method to replace a class of character, e.g.
    punctuation, with plain letters and numbers.

    Parameters:
      str_input = input string
      seed      = seed for pseudo-randomizing the position and injected character
      len_out   = length of head of string that will eventually survive truncation.
    """
    s = ''
    i = 0
    while i < len_out:
        m = RE_NON_ALPHA_NUMERIC.search(str_input, i)
        if m is None:
            break
        (p1, p2) = m.span()
        if p1 > i:
            s += str_input[i:p1]
        for j in range(p1, p2):
            s += chr((seed + i+j-p1) % 26 + 65)   # duplicates weird use of seed with i
        i = p2
    if i < len(str_input):
        s += str_input[i:]
    return s

def convert_to_digits(str_input, seed, len_out):
    """
    Convert input string to digits-only.

    Parameters:
      str_input = input string
      seed      = seed for pseudo-randomizing the position and injected character
     len_out    = length of head of string that will eventually survive truncation
    """
    s = ''
    i = 0
    while i < len_out:
        m = RE_NON_NUMERIC.search(str_input, i)
        if not m:
            break
        j = m.start() - i
        if j > 0:
            s += str_input[i : i + j]
        s += chr((seed + ord(str_input[i])) % 10 + 48)
        i += (j + 1)
    if i < len(str_input):
        s += str_input[i:]
    return s
