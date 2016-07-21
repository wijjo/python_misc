#!/usr/bin/env python
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

import sys
import os
import copy
import inspect

from . import command
from . import utility
from . import console

try:
    import argparse
except ImportError:
    from .python import argparse

"""
==========
CLI Module
==========

Introduction
------------
This module wraps argparse to make it easier to define a command line
interface, a.k.a. CLI, that supports multi-level commands, options, and help.
It adapts argparse's procedural interface with a declarative wrapper theat
brings the CLI metadata closer to the implementation.

Decorators declare the main program, along with the individual commands and
sub-commands. Once the implementation functions are declared using the
decorators a single call to cli.main() runs the program after parsing the
command line options.

Note that the decorated functions can have any name, but if no "name" attribute
is specified the function names are used as the command names. The optional
"name" attribute is particularly useful when command names are invalid Python
symbols, e.g. when using a digit as the first charactor of the command name.

Sample
------
There is no user guide yet. The sample program below will hopefully help to get
you started. More advanced features may be discovered in doc strings, comments,
and the code itself. Better documentation is planned.

Sample code::

  from scriptbase import cli

  TIMEOUT = 60

  @cli.Main('Access remote web pages', support_dryrun=True, args=[
      cli.Integer('timeout', 'time-out in seconds', '--timeout', default=TIMEOUT)])
  def main(runner):
      global TIMEOUT
      TIMEOUT = runner.cmdargs.timeout

  @cli.Command(description='download page', args=[
      cli.String('url', 'URL of page to download'),
      cli.Boolean('pdf', 'convert to a PDF', '--pdf')])
  def download(runner):
      if runner.cmdargs.dryrun:
          print('Download(dryrun): %s' % runner.cmdargs.url)
      elif runner.cmdargs.pdf:
          print('Download(PDF): %s' % runner.cmdargs.url)
      else:
          print('Download(HTML): %s' % runner.cmdargs.url)

  @cli.Command(description='display various statistics', args=[
      cli.String('url', 'URL of page to download')])
  def show(runner):
      print('show')

  @cli.Command(description='display route to host', parent=show)
  def route(runner):
      print('show_route(%s)' % runner.cmdargs.url)

  @cli.Command(description='display latency to host', parent=show)
  def latency(runner):
      print('show_latency(%s)' % runner.cmdargs.url)

  if __name__ == '__main__':
      cli.main()

The sample is runnable, e.g. save it as sample.py and make sure scriptbase
is in your PYTHONPATH.

Compatibility
-------------
Python 2.7 or 3.5 and later.
"""

# Future features:
# - YAML configuration
# - Saved option sets
# - Wrap existing external commands with DSL

#===============================================================================
class ArgumentSpec(object):
    """
    ArgumentSpec class is used to declare typed arguments and options.
    """
#===============================================================================
    def __init__(self, dest, help, *args, **kwargs):
        self.args   = args
        self.kwargs = kwargs
        self.kwargs['dest'] = dest
        self.kwargs['help'] = help
        if 'default' in self.kwargs and 'help' in self.kwargs:
            self.kwargs['help'] += ' (default=%s)' % str(self.kwargs['default'])

    def __str__(self):
        return 'ArgumentSpec:%s(%s)' % (self.kwargs['dest'], self.__class__.__name__)

#===============================================================================
class String(ArgumentSpec):
    """
    String type ArgumentSpec subclass.
    """
#===============================================================================
    def __init__(self, dest, help, *args, **kwargs):
        kwargs['action'] = 'store'
        ArgumentSpec.__init__(self, dest, help, *args, **kwargs)

#===============================================================================
class Boolean(ArgumentSpec):
    """
    Boolean type ArgumentSpec subclass.
    """
#===============================================================================
    def __init__(self, dest, help, *args, **kwargs):
        kwargs['action'] = 'store_true'
        ArgumentSpec.__init__(self, dest, help, *args, **kwargs)

#===============================================================================
class Integer(ArgumentSpec):
    """
    Integer type ArgumentSpec subclass.
    """
#===============================================================================
    def __init__(self, dest, help, *args, **kwargs):
        kwargs['action'] = 'store'
        kwargs['type'] = int
        ArgumentSpec.__init__(self, dest, help, *args, **kwargs)

#===============================================================================
class Verb(object):
    """
    Verb class defines commands and sub-commands, including their options,
    arguments, and implementation functions.
    """
#===============================================================================

    root = None
    parser = None
    verbs_by_function_ref = {}

    def __init__(self, name=None,
                       description=None,
                       is_root=False,
                       parent=None,
                       function=None,
                       args=[],
                       aliases=[]):
        if not is_root and not Verb.root:
            Verb.root = Verb(is_root=True)
        self.name = name
        if description is None:
            self.description = '(no description provided)'
        else:
            self.description = description
        self.is_root = is_root
        self.function = function
        self.arg_specs = []
        self.child_verbs = []
        self.dirty = True
        self.aliases = aliases
        badargs = []
        for arg_spec in args:
            if isinstance(arg_spec, Verb):
                self.child_verbs.append(arg_spec)
            elif isinstance(arg_spec, ArgumentSpec):
                self.arg_specs.append(arg_spec)
            else:
                badargs.append(arg_spec)
        for badarg in badargs:
            sys.stderr.write('* CLI: ignoring bad argument specification: %s*\n' % repr(badarg))
        if not self.is_root:
            if parent is None:
                Verb.root.add_verb(self)
            elif isinstance(parent, Verb):
                parent.add_verb(self)
            elif inspect.isfunction(parent) and parent in Verb.verbs_by_function_ref:
                Verb.verbs_by_function_ref[parent].add_verb(self)
            else:
                console.abort('Parent is not a known command function.')

    def configure_parser(self, parser):
        self._update()
        verb_builder = VerbBuilder(parser, self)
        verb_builder.build(add_help=self.is_root)

    def set_function(self, function):
        Verb.verbs_by_function_ref[function] = self
        # Fall back to using the function name if no explicit name was given.
        if not self.name:
            self.name = function.__name__
        self.function = function
        # Returning the function is a convenience for decorator implementations.
        return self.function

    def add_verb(self, verb):
        self.child_verbs.append(verb)
        self.dirty = True

    def get_verbs(self):
        self._update()
        return self.child_verbs

    def __str__(self):
        self._update()
        sargs = '(%s)' % ', '.join([str(a) for a in self.arg_specs])
        sverb_list = [str(verb).replace('\n', '\n      ') for verb in self.child_verbs]
        sverbs = '\n'.join(sverb_list)
        return '''Verb:%s%s:
   description: %s
   function: %s
   verbs:
      %s''' % (self.name, sargs, self.description, self.function, sverbs)

    def _update(self):
        if self.dirty:
            self.child_verbs = sorted(self.child_verbs, key=lambda x: x.name)
            self.dirty = False

    @classmethod
    def get_parser(cls, description, add_arg_specs):
        """
        Parse all arguments and options.
        """
        # Support tests with multiple command lines run against one specification.
        if cls.parser:
            return cls.parser
        cls.root.description = description
        if add_arg_specs:
            cls.root.arg_specs.extend(add_arg_specs)
        cls.parser = argparse.ArgumentParser(
            description='  %s' % '\n  '.join(cls._description_lines()),
            formatter_class=argparse.RawDescriptionHelpFormatter)
        cls.root.configure_parser(cls.parser)
        return cls.parser

    @classmethod
    def _description_lines(cls):
        lines = ['%(prog)s [OPTION ...] SUBCOMMAND [SUBOPTION ...] [ARG ...]', '']
        prog = os.path.basename(sys.argv[0])
        verb_usage_pairs = [
            ('%s help' % prog, 'Display general help.'),
            ('%s help SUBCOMMAND' % prog, 'Display sub-command help.'),
        ] + [('%s %s ...' % (prog, verb.name), verb.description) for verb in cls.root.get_verbs()]
        verb_usage_pairs = sorted(verb_usage_pairs, key=lambda x: x[0])
        width = 0
        for verb_usage_pair in verb_usage_pairs:
            if len(verb_usage_pair[0]) > width:
                width = len(verb_usage_pair[0])
        fmt = '%%-%ds  %%s' % width
        lines.extend([fmt % (p[0], p[1]) for p in verb_usage_pairs])
        return lines

#===============================================================================
class VerbBuilder(object):
    """
    CLI builder for verb sub-command.
    """
#===============================================================================

    def __init__(self, parser, verb):
        self.parser = parser
        self.verb = verb

    def build(self, add_help=False):
        for arg_spec in self.verb.arg_specs:
            self.parser.add_argument(*arg_spec.args, **arg_spec.kwargs)
        if self.verb.function:
            self.parser.set_defaults(func=self.verb.function)
        if self.verb.get_verbs():
            help = '"help SUBCOMMAND" for details'
            # For some reason Python 3 needs dest set in order to get the
            # correct function that was saved by set_defaults(func=...).  Note
            # that nested sub-commands with this use of set_defaults() is
            # broken in Python 3 versions before 3.5.
            subparsers = self.parser.add_subparsers(dest='subcommand', help=help)
            subparsers.required = True
            parsers_by_name = {'_': self.parser}
            for verb in self.verb.get_verbs():
                subparser = subparsers.add_parser(verb.name, description=verb.description)
                parsers_by_name[verb.name] = subparser
                for alias in verb.aliases:
                    subparser = subparsers.add_parser(alias, description=verb.description)
                    parsers_by_name[alias] = subparser
                verb.configure_parser(subparser)
            if add_help:
                helpparser = subparsers.add_parser('help', description='display command or verb help')
                helpparser.add_argument('verbs', help='optional verb list', nargs='*')
                helpparser.set_defaults(func=VerbHelp(parsers_by_name))

#===============================================================================
class VerbHelp(object):
    """
    Callable class for providing verb-specific help.
    """
#===============================================================================

    def __init__(self, parsers_by_name):
        self.parsers_by_name = parsers_by_name

    def __call__(self, runner):
        names = runner.cmdargs.verbs
        if not names:
            names = ['_']
        i = 0
        for verbname in names:
            if i > 0:
                sys.stdout.write('\n')
            i += 1
            if verbname in self.parsers_by_name:
                self.parsers_by_name[verbname].print_help()
            else:
                sys.stderr.write('* "%s" is not a supported verb. *\n' % verbname)

#===============================================================================
class Main(object):
    """
    Function decorator class used to declare the main setup function.
    """
#===============================================================================

    instance = None

    def __init__(self, description=None,
                       args=[],
                       support_verbose=False,
                       support_dryrun=False,
                       support_pause=False):
        self.description = description
        self.arg_specs = args
        self.support_verbose = support_verbose
        self.support_dryrun = support_dryrun
        self.support_pause = support_pause
        self.function = None

    def __call__(self, function):
        if Main.instance:
            console.abort('Only one @cli.Main() is allowed.')
        self.function = function
        Main.instance = self

#===============================================================================
def main(command_line=sys.argv[1:]):
    """
    Main CLI function to parse the arguments and invoke the appropriate command
    function. Returns any result provided by the command function, which should
    be a system exit code, i.e. 0 for success or non-zero for failure.
    """
#===============================================================================
    if not Main.instance:
        console.abort('No @cli.Main() was found.')
    add_arg_specs = copy.copy(list(Main.instance.arg_specs))
    if Main.instance.support_verbose:
        add_arg_specs.append(Boolean('verbose', "display verbose messages", '-v', '--verbose'))
    if Main.instance.support_dryrun:
        add_arg_specs.append(Boolean('dryrun', "display commands without executing them", '--dry-run'))
    if Main.instance.support_pause:
        add_arg_specs.append(Boolean('pause', "pause before executing each command", '--pause'))
    parser = Verb.get_parser(Main.instance.description, add_arg_specs)
    cmdargs = parser.parse_args(args=command_line)
    runner = command.Runner(cmdargs)
    try:
        # Invoke main function (frequently does little or nothing).
        Main.instance.function(runner)
        # Invoke command implementation function.
        if hasattr(runner.cmdargs, 'func'):
            return runner.cmdargs.func(runner)
    except KeyboardInterrupt:
        sys.exit(255)

#===============================================================================
class Command(Verb):
    """
    Function decorator class used to declare a command or sub-command (if
    parent is specified) verb functions and their options and arguments.

    Keyword arguments (all are optional):

      name         primary command name the user has to type
                   (defaults to the function name)
      description  one line help text describing the command
      parent       sub-commands need a reference to the parent command function
      args         argument and option type list (sequence), e.g.
                   [cli.String(...), cli.Boolean(...), cli.Integer(...), ...]
      aliases      list of alternative names (sequence)
    """
#===============================================================================

    def __init__(self, name=None, description=None, parent=None, args=[], aliases=[]):
        Verb.__init__(self, name=name,
                            description=description,
                            args=args,
                            parent=parent,
                            aliases=aliases)

    def __call__(self, function):
        return self.set_function(function)
