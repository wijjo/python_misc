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

"""Scriptbase command.py tests."""

import sys
import tempfile
import unittest

from scriptbase.command import Command

class TestCommand(unittest.TestCase):
    """Test suite."""

    def test_full_iteration(self):
        """Fully iterate command output."""
        with Command('bash', '-c', 'for i in 111 222 333; do echo $i; done') as test_cmd:
            lines = [line for line in test_cmd]
        self.assertEqual(lines, ['111', '222', '333'])
        self.assertEqual(len(test_cmd.output_lines), 0)
        self.assertEqual(test_cmd.return_code, 0)

    def test_partial_iteration(self):
        """Partially iterate command output."""
        lines = []
        with Command('bash', '-c', 'for i in 111 222 333; do echo $i; done') as test_cmd:
            for line in test_cmd:
                lines.append(line)
                break
        self.assertEqual(lines, ['111'])
        self.assertEqual(len(test_cmd.output_lines), 0)

    def test_captured_on_close(self):
        """Capture output after closing the command."""
        with Command('bash', '-c', 'for i in 111 222 333; do echo $i; done') as test_cmd:
            pass
        self.assertEqual(test_cmd.output_lines, ['111', '222', '333'])
        self.assertEqual(test_cmd.return_code, 0)

    def test_all_at_once(self):
        """Use read_lines() to get all the output at once."""
        with Command('bash', '-c', 'for i in 111 222 333; do echo $i; done') as test_cmd:
            lines = test_cmd.read_lines()
        self.assertEqual(lines, ['111', '222', '333'])
        self.assertEqual(len(test_cmd.output_lines), 0)
        self.assertEqual(test_cmd.return_code, 0)

    def test_console(self):
        """Empty console output."""
        with Command('bash', '-c', 'ls -l /tmp > /dev/null') as test_cmd:
            test_cmd.run()
        self.assertEqual(len(test_cmd.output_lines), 0)
        self.assertEqual(test_cmd.return_code, 0)

    def test_with_block_exception(self):
        """Exception raised if not in with block."""
        test_cmd = Command('bash', '-c', 'for i in 111 222 333; do echo $i; done')
        self.assertRaises(Command.NotInWithBlock, test_cmd.read_lines)

    def test_output_pipe(self):
        """Pipe output to another command."""
        lines = []
        with Command('bash', '-c', 'for i in a b c d e; do echo $i; done') as test_cmd:
            with test_cmd.pipe_out('grep', '[bd]') as grep_cmd:
                lines = [line for line in grep_cmd]
            self.assertEqual(len(test_cmd.output_lines), 0)
            self.assertEqual(grep_cmd.return_code, 0)
        self.assertEqual(lines, ['b', 'd'])
        self.assertEqual(len(test_cmd.output_lines), 0)
        self.assertEqual(test_cmd.return_code, 0)

    def test_input_pipe(self):
        """Pipe input to command."""
        lines = []
        with Command('bash', '-c', 'for i in a b c d e; do echo $i; done') as test_cmd:
            with Command('grep', '[bd]').pipe_in(test_cmd) as grep_cmd:
                lines = [line for line in grep_cmd]
            self.assertEqual(len(grep_cmd.output_lines), 0)
            self.assertEqual(grep_cmd.return_code, 0)
        self.assertEqual(lines, ['b', 'd'])
        self.assertEqual(len(test_cmd.output_lines), 0)
        self.assertEqual(test_cmd.return_code, 0)

    def test_input_bytes(self):
        """Input byte string."""
        lines = []
        with Command('grep', '[bd]').pipe_in(b'a\nb\n\c\nd\n\e\n') as test_cmd: #pylint: disable=anomalous-backslash-in-string
            lines = [line for line in test_cmd]
        self.assertEqual(lines, ['b', 'd'])
        self.assertEqual(len(test_cmd.output_lines), 0)
        self.assertEqual(test_cmd.return_code, 0)

    def test_input_string(self):
        """Input normal string."""
        lines = []
        with Command('grep', '[bd]').pipe_in('a\nb\n\c\nd\n\e\n') as test_cmd:  #pylint: disable=anomalous-backslash-in-string
            lines = [line for line in test_cmd]
        self.assertEqual(lines, ['b', 'd'])
        self.assertEqual(len(test_cmd.output_lines), 0)
        self.assertEqual(test_cmd.return_code, 0)

    def test_input_list(self):
        """Input string list."""
        lines = []
        with Command('grep', '[bd]').pipe_in(['a', 'b', 'c', 'd', 'e']) as test_cmd:
            lines = [line for line in test_cmd]
        self.assertEqual(lines, ['b', 'd'])
        self.assertEqual(len(test_cmd.output_lines), 0)
        self.assertEqual(test_cmd.return_code, 0)

    def test_input_stream(self):
        """Input stream."""
        lines = []
        tmp = tempfile.SpooledTemporaryFile()
        tmp.write(b'a\nb\n\c\nd\n\e\n')                                         #pylint: disable=anomalous-backslash-in-string
        tmp.seek(0)
        with Command('grep', '[bd]').pipe_in(tmp) as test_cmd:
            lines = [line for line in test_cmd]
        self.assertEqual(lines, ['b', 'd'])
        self.assertEqual(len(test_cmd.output_lines), 0)
        self.assertEqual(test_cmd.return_code, 0)

def demo_realtime():
    """Demonstrate real-time output from sub-process."""
    with Command('bash', '-c', 'for i in 111 222 333; do echo $i; sleep 1; done') as test_cmd:
        for line in test_cmd:
            print(line)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'demo':
            demo_realtime()
        else:
            sys.stderr.write('Unknown sub-command: %s\n' % sys.argv[1])
    else:
        unittest.main()
