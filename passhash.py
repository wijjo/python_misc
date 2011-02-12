#!/usr/bin/env python
################################################################################
################################################################################
# Password Hasher module and runnable script
#
# Author: Steve Cooper
# License: Mozilla
# Created: 01/04/11
#
# SHA1 code based on:
# A JavaScript implementation of the Secure Hash Algorithm, SHA-1, as defined
# in FIPS PUB 180-1
# Version 2.1a Copyright Paul Johnston 2000 - 2002.
# Other contributors: Greg Holt, Andrew Kepert, Ydnar, Lostinet
# Distributed under the BSD License
# See http://pajhome.org.uk/crypt/md5 for details.
################################################################################
################################################################################

import sys
import os
import optparse
import re
import ctypes

reNonNumeric = re.compile('[^0-9]+')
reNonAlphaNumeric = re.compile('[^a-z0-9]+', re.IGNORECASE)

hexupper = False    # hex uppercase format?
b64pad  = ''        # base-64 pad character. "=" for strict RFC compliance
chrsz   = 8         # bits per input character. 8 - ASCII; 16 - Unicode

if hexupper:
    hex_tab = "0123456789ABCDEF"
else:
    hex_tab = "0123456789abcdef"

b64_tab = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def hex_sha1(s):
    return binb2hex(core_sha1(str2binb(s),len(s) * chrsz))

def b64_sha1(s):
    return binb2b64(core_sha1(str2binb(s),len(s) * chrsz))

def str_sha1(s):
    return binb2str(core_sha1(str2binb(s),len(s) * chrsz))

def hex_hmac_sha1(key, data):
    return binb2hex(core_hmac_sha1(key, data))

def b64_hmac_sha1(key, data):
    return binb2b64(core_hmac_sha1(key, data))

def str_hmac_sha1(key, data):
    return binb2str(core_hmac_sha1(key, data))

def core_sha1(x, size):
    log.dump_hex(3, x = x)
    log.dump(3, size = size)
    i = (size >> 5)
    if i >= len(x):
        x.extend([0]*(i-len(x)+1))
    x[i] |= 0x80 << (24 - size % 32)
    j = ((size + 64 >> 9) << 4) + 15
    if len(x) <= j:
        x.extend([0]*(j-len(x)+1))
    x[j] = size
    w = [0] * 80
    a =  1732584193
    b = -271733879
    c = -1732584194
    d =  271733878
    e = -1009589776
    for i in range(0, len(x), 16):
        olda = a
        oldb = b
        oldc = c
        oldd = d
        olde = e
        for j in range(80):
            log.dump_hex(3, {"(%d,%d):a,b,c,d,e" % (i, j): [a,b,c,d,e]})
            if j < 16:
                w[j] = x[i + j]
            else:
                w[j] = rol(w[j-3] ^ w[j-8] ^ w[j-14] ^ w[j-16], 1)
            log.dump_hex(3, w = w)
            t = safe_add(safe_add(rol(a, 5), sha1_ft(j, b, c, d)),
                         safe_add(safe_add(e, w[j]), sha1_kt(j)))
            e = d
            d = c
            c = rol(b, 30)
            b = a
            a = t
        log.dump_hex(3, {"(%d):a,b,c,d,e" % i: [a,b,c,d,e]})
        a = safe_add(a, olda)
        b = safe_add(b, oldb)
        c = safe_add(c, oldc)
        d = safe_add(d, oldd)
        e = safe_add(e, olde)
    return [a, b, c, d, e]

def sha1_ft(t, b, c, d):
    if t < 20:
        return (b & c) | ((~b) & d)
    if t < 40:
        return b ^ c ^ d
    if t < 60:
        return (b & c) | (b & d) | (c & d)
    return b ^ c ^ d

def sha1_kt(t):
    if t < 20:
        return 1518500249
    if t < 40:
        return 1859775393
    if t < 60:
        return -1894007588
    return -899497514

class NumArray(object):
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

def core_hmac_sha1(key, data):
    log.dump(2, key = key)
    log.dump(2, data = data)
    bkey = NumArray(str2binb(key))
    if len(bkey) > 16:
        bkey = core_sha1(bkey, len(key) * chrsz)
    log.dump_hex(2, bkey = bkey)
    ipad = [(bkey[i] ^ 0x36363636) for i in range(16)]
    opad = [(bkey[i] ^ 0x5C5C5C5C) for i in range(16)]
    log.dump_hex(2, ipad = ipad)
    log.dump_hex(2, opad = opad)
    hash = core_sha1(ipad + str2binb(data), 512 + (len(data) * chrsz))
    log.dump_hex(2, hash = hash)
    res = core_sha1(opad + hash, 512 + 160)
    log.dump_hex(2, core_hmac_sha1 = res)
    return res

def left_shift(num, cnt):
    return ctypes.c_int32(ctypes.c_uint32(num).value << cnt).value

def right_shift(num, cnt):
    return ctypes.c_int32(ctypes.c_int32(num).value >> cnt).value

def right_shift_zero_fill(num, cnt):
    return ctypes.c_int32(ctypes.c_uint32(num).value >> cnt).value

def safe_add(x, y):
    lsw = (x & 0xFFFF) + (y & 0xFFFF)
    msw = right_shift(x, 16) + right_shift(y, 16) + right_shift(lsw, 16)
    res = left_shift(msw, 16) | (lsw & 0xFFFF)
    log.dump_hex(3, safe_add = [x, y, res])
    return res

def rol(num, cnt):
    n1 = left_shift(num, cnt)
    n2 = right_shift_zero_fill(num, 32 - cnt)
    res = n1 | n2
    log.dump(3, rol = [num, cnt, n1, n2, res]);
    return res

def str2binb(str):
    bin = [0] * (((len(str)*chrsz)>>5)+1)
    mask = (1 << chrsz) - 1
    for i in range(len(str)):
        bin[(i*chrsz)>>5] |= (ord(str[i]) & mask) << (32 - chrsz - (i*chrsz)%32)
    log.dump_hex(3, {'str2binb(%s)' % str:  bin})
    return bin

def binb2str(bin):
    str = ""
    mask = (1 << chrsz) - 1
    for i in range(0, len(bin)*32, chrsz):
        str += chr(right_shift_zero_fill(bin[i>>5], 32-chrsz-(i%32)) & mask)
    return str

def binb2hex(binarray):
    str = ""
    for i in range(len(binarray)*4):
        str += (hex_tab[(binarray[i>>2] >> ((3 - i%4)*8+4)) & 0xF] +
                hex_tab[(binarray[i>>2] >> ((3 - i%4)*8  )) & 0xF])
    return str

def binb2b64(binarray):
    str = ''
    def chop(a, i, s):
        if i >> 2 >= len(a):
            return 0
        return ((a[i >> 2] >> 8 * (3 - i%4)) & 0xFF) << s
    log.dump_hex(3, binarray = binarray)
    for i in range(0, len(binarray) * 4, 3):
        b1 = chop(binarray, i,  16)
        b2 = chop(binarray, i+1, 8)
        b3 = chop(binarray, i+2, 0)
        triplet = b1 | b2 | b3
        log.dump_hex(3, {'i,b1,b2,b3,triplet': [i, b1, b2, b3, triplet]})
        for j in range(4):
            if i * 8 + j * 6 > len(binarray) * 32:
                str += b64pad
            else:
                str += b64_tab[(triplet >> 6*(3-j)) & 0x3F]
    return str
class Log(object):
    class Entry(object):
        def __init__(self, tag, typ, msg):
            self.tag = tag
            self.typ = typ
            self.msg = msg
    def __init__(self):
        self.entries = []
        self.verbosity = 0
    def __del__(self):
        self.flush()
    def dump(self, level, *args, **kwargs):
        if level <= self.verbosity:
            if '_hex' in kwargs:
                hex = kwargs['_hex']
                del kwargs['_hex']
            else:
                hex = False
            self._dump(args, kwargs, hex)
    def dump_hex(self, level, *args, **kwargs):
        if level <= self.verbosity:
            self._dump(args, kwargs, True)
    def _dump(self, args, kwargs, hex):
        for arg in args:
            if hasattr(arg, '__getitem__') and hasattr(arg, 'keys'):
                for kw in arg:
                    tv = get_type_value(arg[kw], hex)
                    self.entries.append(Log.Entry(kw, tv.type, tv.value))
            else:
                tv = get_type_value(arg, hex)
                self.entries.append(Log.Entry('', tv.type, tv.value))
        for kw in kwargs:
            tv = get_type_value(kwargs[kw], hex)
            self.entries.append(Log.Entry(kw, tv.type, tv.value))
    def flush(self):
        try:
            if len(self.entries) > 0:
                if self.verbosity > 0:
                    width = max([(len(entry.tag) + len(entry.typ) + 3) for entry in self.entries])
                else:
                    width = max([len(entry.tag) for entry in self.entries])
                format = '%%-%ds: %%s' % width
                for entry in self.entries:
                    if self.verbosity > 0:
                        tag = '%s (%s)' % (entry.tag, entry.typ)
                    else:
                        tag = entry.tag
                    print format % (tag, entry.msg)
            self.entries = []
        except IOError:
            sys.stderr.write('* Output interrupted *')
            os._exit(1)

def get_type_value(value, hex = False):
    '''Return (type, string) pair for any value.  Optionally use hex number format.'''
    class TypeValue(object):
        def __init__(self, type, value):
            self.type = type
            self.value = value
    def check_integer():
        if not isinstance(value, int) and not isinstance(value, long):
            return None
        if hex:
            return TypeValue('Integer', '#%08X' % value)
        return TypeValue('Integer', str(value))
    def check_string():
        try:
            value + ''
            return TypeValue('String[%d]' % len(value), value)
        except:
            return None
    def check_dict():
        if not hasattr(value, '__getitem__') or not hasattr(value, 'keys'):
            return None
        keys = value.keys()
        keys.sort()
        s = ''
        for key in keys:
            if s:
                s += ', '
            s += '%s: %s' % (get_type_value(key).value, get_type_value(value[key], hex).value)
        return TypeValue('Dict[%d]' % len(keys), s)
    def check_list():
        if not hasattr(value, '__getitem__'):
            return None
        s = ''
        for i in range(len(value)):
            if s:
                s += ', '
            s += get_type_value(value[i], hex).value
        return TypeValue('List[%d]' % len(value), s)
    def get_other():
        return TypeValue(type(value).__name__, str(value))
    # Run the gauntlet of type checks
    tv = check_integer()
    if tv is None:
        tv = check_string()
    if tv is None:
        tv = check_dict()
    if tv is None:
        tv = check_list()
    if tv is None:
        tv = get_other()
    return tv

log = Log()

def generateHashWord(
    siteTag,
    masterKey,
    hashWordSize       = 8,
    requireDigit       = False,
    requirePunctuation = False,
    requireMixedCase   = False,
    restrictSpecial    = False,
    restrictDigits     = False
):
    # Start with the SHA1-encrypted master key/site tag.
    s = b64_hmac_sha1(masterKey, siteTag)
    log.dump(1, sha1 = s)
    # Use the checksum of all characters as a pseudo-randomizing seed to
    # avoid making the injected characters easy to guess.  Note that it
    # isn't random in the sense of not being deterministic (i.e.
    # repeatable).  Must share the same seed between all injected
    # characters so that they are guaranteed unique positions based on
    # their offsets.
    sum = 0
    for i in range(len(s)):
        sum += ord(s[i])
    # Restrict digits just does a mod 10 of all the characters
    if restrictDigits:
        s = convertToDigits(s, sum, hashWordSize)
    else:
        # Inject digit, punctuation, and mixed case as needed.
        if requireDigit:
            s = injectSpecialCharacter(s, 0, 4, sum, hashWordSize, 48, 10)
        if requirePunctuation and not restrictSpecial:
            s = injectSpecialCharacter(s, 1, 4, sum, hashWordSize, 33, 15)
        if requireMixedCase:
            s = injectSpecialCharacter(s, 2, 4, sum, hashWordSize, 65, 26)
            s = injectSpecialCharacter(s, 3, 4, sum, hashWordSize, 97, 26)
        # Strip out special characters as needed.
        if restrictSpecial:
            s = removeSpecialCharacters(s, sum, hashWordSize)
    # Trim it to size.
    s = s[:hashWordSize]
    log.dump(1, final = s)
    return s

# This is a very specialized method to inject a character chosen from a
# range of character codes into a block at the front of a string if one of
# those characters is not already present.
# Parameters:
#  sInput   = input string
#  offset   = offset for position of injected character
#  reserved = # of offsets reserved for special characters
#  seed     = seed for pseudo-randomizing the position and injected character
#  lenOut   = length of head of string that will eventually survive truncation.
#  cStart   = character code for first valid injected character.
#  cNum     = number of valid character codes starting from cStart.
def injectSpecialCharacter(sInput, offset, reserved, seed, lenOut, cStart, cNum):
    pos0 = seed % lenOut
    pos = (pos0 + offset) % lenOut
    # Check if a qualified character is already present
    # Write the loop so that the reserved block is ignored.
    for i in range(lenOut - reserved):
        i2 = (pos0 + reserved + i) % lenOut
        c = ord(sInput[i2])
        if c >= cStart and c < cStart + cNum:
            return sInput;  # Already present - nothing to do
    if pos > 0:
        sHead = sInput[:pos]
    else:
        sHead = ""
    sInject = chr(((seed + ord(sInput[pos])) % cNum) + cStart)
    if pos + 1 < len(sInput):
        sTail = sInput[pos+1:]
    else:
        sTail = ""
    return (sHead + sInject + sTail)

# Another specialized method to replace a class of character, e.g.
# punctuation, with plain letters and numbers.
# Parameters:
#  sInput = input string
#  seed   = seed for pseudo-randomizing the position and injected character
#  lenOut = length of head of string that will eventually survive truncation.
def removeSpecialCharacters(sInput, seed, lenOut):
    s = ''
    i = 0
    while i < lenOut:
        m = reNonAlphaNumeric.search(sInput, i)
        if m is None:
            break
        (p1, p2) = m.span()
        if p1 > i:
            s += sInput[i:p1]
        for j in range(p1, p2):
            s += chr((seed + i+j-p1) % 26 + 65)   # duplicates weird use of seed with i
        i = p2
    if i < len(sInput):
        s += sInput[i:]
    return s

# Convert input string to digits-only.
# Parameters:
#  sInput = input string
#  seed   = seed for pseudo-randomizing the position and injected character
#  lenOut = length of head of string that will eventually survive truncation.
def convertToDigits(sInput, seed, lenOut):
    s = ''
    i = 0
    while i < lenOut:
        m = reNonNumeric.search(sInput, i)
        if not m:
            break
        j = m.start() - i
        if j > 0:
            s += sInput[i : i + j]
        s += chr((seed + ord(sInput[i])) % 10 + 48)
        i += (j + 1)
    if i < len(sInput):
        s += sInput[i:]
    return s

class TestResults(object):
    def __init__(self):
        self.total = self.passed = self.failed = 0

testResults = TestResults()

def runTest(
    siteTag,
    masterKey,
    hashWordSize,
    requireDigit,
    requirePunctuation,
    requireMixedCase,
    restrictSpecial,
    restrictDigits,
    expect
):
    testResults.total += 1
    print '=== Test %d ===' % testResults.total
    log.dump(0, {"tag,key,options": (siteTag,
                                     masterKey,
                                     requireDigit,
                                     requirePunctuation,
                                     requireMixedCase,
                                     restrictSpecial,
                                     restrictDigits,
                                     hashWordSize)})
    result = generateHashWord(siteTag,
                              masterKey,
                              hashWordSize,
                              requireDigit,
                              requirePunctuation,
                              requireMixedCase,
                              restrictSpecial,
                              restrictDigits);
    if result == expect:
        log.dump(0, {"result *PASS*": result})
        testResults.passed += 1
    else:
        log.dump(0, {"result *FAIL*": (result, "expect=" + expect)})
        testResults.failed += 1
    log.flush()

def test():
    log.verbosity = 1
    runTest("abcdef"  , "ghijkl"   ,  8, 0, 0, 0, 0, 0, "2T0SYXf1")
    runTest("abcdefgh", "987654321", 16, 0, 0, 0, 0, 0, "DiLlvt4zp8KtHoFY")
    runTest("aaaa"    , "bbbb"     ,  6, 0, 0, 1, 0, 0, "DCi393")
    runTest("aaaa"    , "bbbb"     ,  6, 0, 1, 1, 0, 0, '"Ci393')
    runTest("cccc"    , "bbbb"     ,  4, 0, 0, 0, 0, 0, 'pNKi')
    runTest("cccc"    , "bbbb"     ,  4, 1, 0, 0, 0, 0, 'pNK2')
    runTest("zyxwvuts", "abcdefghi", 12, 0, 0, 0, 0, 0, 'T5eB8F/J2ghv')
    runTest("zyxwvuts", "abcdefghi", 12, 0, 0, 0, 1, 0, 'T5eB8FOJ2ghv')
    runTest("zyxwvuts", "abcdefghi", 12, 0, 0, 0, 0, 1, '857080182482')
    print '=== Summary ==='
    log.dump(0, Total  = testResults.total);
    log.dump(0, Passed = testResults.passed);
    log.dump(0, Failed = testResults.failed);

#===============================================================================
if __name__ == '__main__':
#===============================================================================

    parser = optparse.OptionParser()
    parser.set_usage('%prog [OPTIONS] domain password')
    parser.add_option('-a', '--alphanumeric' , dest = 'alphanumeric', action = 'store_true',
                      help = 'allow only alpha-numeric characters'),
    parser.add_option('-d', '--digit' , dest = 'digit', action = 'store_true',
                      help = 'require at least one digit'),
    parser.add_option('-l', '--length' , dest = 'length', action = 'store', type = 'int',
                      help = 'length of generated hash word'),
    parser.add_option('-m', '--mixedcase', dest = 'mixedcase', action = 'store_true',
                      help = 'require a mix of upper and lower case'),
    parser.add_option('-n', '--numeric', dest = 'numeric', action = 'store_true',
                      help = 'create numeric code, e.g. for PIN'),
    parser.add_option('-p', '--punctuation', dest = 'punctuation', action = 'store_true',
                      help = 'require at least one punctuation character'),
    parser.add_option('-t', '--test', dest = 'test', action = 'store_true',
                      help = 'run self test sequence'),
    (options, args) = parser.parse_args()
    if len(args) != 2 and not options.test:
        parser.error('Exactly 2 arguments are required for domain and password unless -t is used')
    if not options.length:
        options.length = 8
    if options.test:
        test()
    else:
        result = generateHashWord(args[0],
                                  args[1],
                                  options.length,
                                  options.digit,
                                  options.punctuation,
                                  options.mixedcase,
                                  options.alphanumeric,
                                  options.numeric);
        print result
