#!/usr/bin/env python

import sys
import os
import run
import utility
try:
    import argparse
except ImportError:
    from python import argparse


class G:
    """
    Namespace class for global data.
    """

    # There is only one CLI spec per application!
    # Stub (non-None) Verb created at the bottom of this file.
    # Fully populated by main() call and @Command decorators.
    clispec = None

    # String argument names. Populated during CLI initialization.
    argument_names = set()


class Argument(object):
    """
    Argument class used to declare typed arguments and options.
    """

    def __init__(self, dest, help, *args, **kwargs):
        self.args   = args
        self.kwargs = kwargs
        self.kwargs['dest'] = dest
        self.kwargs['help'] = help
        if 'default' in self.kwargs and 'help' in self.kwargs:
            self.kwargs['help'] += ' (default=%s)' % str(self.kwargs['default'])

    def __str__(self):
        return 'Argument:%s(%s)' % (self.kwargs['dest'], self.__class__.__name__)


class String(Argument):
    """
    String type Argument subclass.
    """

    def __init__(self, dest, help, *args, **kwargs):
        G.argument_names.add(dest)
        kwargs['action'] = 'store'
        Argument.__init__(self, dest, help, *args, **kwargs)


class Boolean(Argument):
    """
    Boolean type Argument subclass.
    """

    def __init__(self, dest, help, *args, **kwargs):
        kwargs['action'] = 'store_true'
        Argument.__init__(self, dest, help, *args, **kwargs)


class Integer(Argument):
    """
    Integer type Argument subclass.
    """

    def __init__(self, dest, help, *args, **kwargs):
        kwargs['action'] = 'store'
        kwargs['type'] = int
        Argument.__init__(self, dest, help, *args, **kwargs)


class Verb(object):
    """
    Verb class defines commands and sub-commands, including their options,
    arguments, and implementation functions.
    """

    def __init__(self, name=None,
                       description=None,
                       root=False,
                       parent=None,
                       function=None,
                       args=[],
                       aliases=[]):
        self.name = name
        if description is None:
            self.description = '(no description provided)'
        else:
            self.description = description
        self.root = root
        self.function = function
        self.arguments = []
        self.child_verbs = []
        self.dirty = True
        self.aliases = aliases
        badargs = []
        for arg in args:
            if isinstance(arg, Verb):
                self.child_verbs.append(arg)
            elif isinstance(arg, Argument):
                self.arguments.append(arg)
            else:
                badargs.append(arg)
        for badarg in badargs:
            sys.stderr.write('* CLI: ignoring bad element: %s*\n' % repr(badarg))
        if not root:
            if parent is None:
                G.clispec.add_verb(self)
            else:
                parent.add_verb(self)

    def prepare(self, parser):
        self._update()
        verbparser = VerbPreparer(parser, self)
        verbparser.prepare(add_help=(self.root==True))

    def set_function(self, function):
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
        sargs = '(%s)' % ', '.join([str(a) for a in self.arguments])
        sverb_list = [str(verb).replace('\n', '\n      ') for verb in self.child_verbs]
        sverbs = '\n'.join(sverb_list)
        return '''Verb:%s%s:
   description: %s
   function: %s
   verbs:
      %s''' % (self.name, sargs, self.description, self.function, sverbs)

    def _update(self):
        if self.dirty:
            self.child_verbs.sort(cmp=lambda x,y:cmp(x.name, y.name))
            self.dirty = False


class VerbPreparer(object):
    """
    CLI parser for verb sub-command.
    """

    def __init__(self, parser, clispec):
        self.parser = parser
        self.clispec = clispec

    def prepare(self, add_help=False):
        for arg in self.clispec.arguments:
            self.parser.add_argument(*arg.args, **arg.kwargs)
        if self.clispec.function:
            self.parser.set_defaults(func=self.clispec.function)
        if self.clispec.get_verbs():
            help = '"help SUBCOMMAND" for details'
            verbparsers = self.parser.add_subparsers(help=help)
            parsers_by_name = {'_': self.parser}
            for verb in self.clispec.get_verbs():
                verbparser = verbparsers.add_parser(verb.name, description=verb.description)
                parsers_by_name[verb.name] = verbparser
                for alias in verb.aliases:
                    verbparser = verbparsers.add_parser(alias, description=verb.description)
                    parsers_by_name[alias] = verbparser
                verb.prepare(parser=verbparser)
            if add_help:
                helpparser = verbparsers.add_parser('help',
                                                    description='display command or verb help')
                helpparser.add_argument('verbs', help='optional verb list', nargs='*')
                helpparser.set_defaults(func=VerbHelp(parsers_by_name))


class VerbHelp(object):
    """
    Callable class for providing verb-specific help.
    """

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


class Command(Verb):
    """
    Function decorator class used to declare command verb functions and their
    options and arguments.
    """

    def __init__(self, name, description, parent=None, args=[], aliases=[]):
        Verb.__init__(self, name=name,
                            description=description,
                            parent=parent,
                            args=args,
                            aliases=aliases)

    def __call__(self, function):
        return self.set_function(function)


class Parser(object):
    """
    CLI parser.
    """

    def __init__(self, description, *args):
        """
        Initialize the CLI parser.
        """
        self.description = description
        self.args = args
        self.parser = None
        self.cmdargs = None
        self.kwargs = None

    def parse(self):
        """
        Parse CLI arguments and options.
        """
        G.clispec.description = self.description
        G.clispec.arguments.extend(self.args)
        self.parser = argparse.ArgumentParser(
                description='  %s' % '\n  '.join(self._description_lines()),
                formatter_class=argparse.RawDescriptionHelpFormatter)
        G.clispec.prepare(self.parser)
        self.cmdargs = self.parser.parse_args()
        self.kwargs = {}
        for name in G.argument_names:
            if hasattr(self.cmdargs, name):
                self.kwargs[name] = getattr(self.cmdargs, name)

    def go(self, *args, **kwargs):
        """
        Invoke command function with provided arguments and keywords.
        """
        if not self.cmdargs:
            self.parse()
        self.cmdargs.func(*args, **kwargs)

    def run(self):
        """
        Invoke command function with parsed arguments and keywords.
        """
        self.go(run.Runner(self.cmdargs, **self.kwargs))

    def _description_lines(self):
        lines = ['%(prog)s [OPTION ...] SUBCOMMAND [SUBOPTION ...] [ARG ...]', '']
        prog = os.path.basename(sys.argv[0])
        verb_usage_pairs = [
            ('%s help' % prog, 'Display general help.'),
            ('%s help SUBCOMMAND' % prog, 'Display sub-command help.'),
        ] + [('%s %s ...' % (prog, verb.name), verb.description) for verb in G.clispec.get_verbs()]
        verb_usage_pairs.sort(cmp=lambda x, y: cmp(x[0], y[0]))
        width = 0
        for verb_usage_pair in verb_usage_pairs:
            if len(verb_usage_pair[0]) > width:
                width = len(verb_usage_pair[0])
        fmt = '%%-%ds  %%s' % width
        lines.extend([fmt % (p[0], p[1]) for p in verb_usage_pairs])
        return lines

# Make stub global CLI spec.
G.clispec = Verb(root=True)
