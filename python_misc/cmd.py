#!/usr/bin/env python

import sys
import subprocess

class Cmd(object):
    """
    Run a single command with various methods for accessing results.

    A Cmd object must be used in a "with" statement to assure proper clean-up.
    Once inside the "with" statement methods can be called to pipe output, run
    to completion with output on the console, or read output lines into a list.

    For now stdout and stderr are merged into one line-buffered output stream.

    The return code rc member is None until outside the "with" block.
    """

    class NotInWithStatement(RuntimeError):
        def __init__(self):
            RuntimeError.__init__(self, 'Illegal use of Cmd object outside of a "with" statement.')

    def __init__(self, *args):
        self.args = args
        self.p = None
        self.done = False
        self.lines = []
        self.capture_on_exit = True
        self.rc = None

    def __enter__(self):
        self.p = subprocess.Popen(
                self.args,
                bufsize=1,
                stdin=None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
        return self

    def __exit__(self, type, value, traceback):
        if self.p is not None:
            if self.capture_on_exit:
                self.lines.extend([line for line in self.pipe()])
            self.rc = self.p.wait()

    def _check(self):
        if self.p is None:
            raise Cmd.NotInWithStatement()

    def run(self):
        self._check()
        for line in self.pipe():
            sys.stdout.write('%s\n' % line)

    def read_lines(self):
        return [line for line in self.pipe()]

    def pipe(self):
        self._check()
        self.capture_on_exit = False
        while self.p.poll() == None:
            line = self.p.stdout.readline()
            if line == '':
                break
            yield line.rstrip()

def test():

    print('===== Pipe real-time output =====')
    with Cmd('bash', '-c', 'for i in 111 222 333; do echo $i; sleep 1; done') as r:
        for line in r.pipe():
            print('>>> %s' % line)
    print('Remaining lines: %s' % str(r.lines))
    print('Returned: %d' % r.rc)

    print('===== Pipe incomplete output =====')
    with Cmd('bash', '-c', 'for i in 111 222 333; do echo $i; done') as r:
        for line in r.pipe():
            print(line)
            break
    print('Remaining lines: %s' % str(r.lines))
    print('Returned: %d' % r.rc)

    print('===== Pipe ignored output =====')
    with Cmd('bash', '-c', 'for i in 111 222 333; do echo $i; done') as r:
        pass
    print('Remaining lines: %s' % str(r.lines))
    print('Returned: %d' % r.rc)

    print('===== Read first line =====')
    with Cmd('bash', '-c', 'for i in 111 222 333; do echo $i; done') as r:
        print('First line: %s' % r.read_lines()[0])
    print('Remaining lines: %s' % str(r.lines))
    print('Returned: %d' % r.rc)

    print('===== Run with unpiped output =====')
    with Cmd('bash', '-c', 'for i in 111 222 333; do echo $i; done') as r:
        r.run()
    print('Remaining lines: %s' % str(r.lines))
    print('Returned: %d' % r.rc)

    print('===== Test exception =====')
    r = Cmd('bash', '-c', 'for i in 111 222 333; do echo $i; done')
    try:
        r.read_lines()
        assert(False)
    except Cmd.NotInWithStatement, e:
        print('Received expected %s exception' % e.__class__.__name__)

if __name__ == '__main__':
    test()
