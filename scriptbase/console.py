#!/usr/bin/env python
#===============================================================================
#===============================================================================
# console
#
# Various console utilities
#
# 02/28/10 - Steve Cooper - author
#===============================================================================
#===============================================================================

import sys, copy
from . import listutil

def _display(f, tag, indent, *msgs, **vars):
    if tag:
        pre = '%s: ' % tag
    else:
        pre = ''
    if indent > 0:
        sindent = ' ' * indent
    else:
        sindent = ''
    for msg in listutil.flatten_split_strings('\n', *msgs, **vars):
        if type(msg) is Exception:
            f.write('%s%s%s Exception: %s' % (pre, sindent, msg.__class__.__name__, str(msg)))
        else:
            f.write('%s%s%s\n' % (pre, sindent, msg))

def info(*msgs, **vars):
    _display(sys.stdout, None, 0, *msgs, **vars)

def warning(*msgs, **vars):
    _display(sys.stdout, 'WARNING', 0, *msgs, **vars)

def error(*msgs, **vars):
    _display(sys.stdout, 'ERROR', 0, *msgs, **vars)

def abort(*msgs, **vars):
    error(*msgs, **vars)
    sys.stderr.write('ABORT\n')
    sys.exit(1)

def header(*msgs, **vars):
    ul = '=' * 70
    _display(sys.stdout, None, 0, '', ul)
    _display(sys.stdout, None, 1, *msgs, **vars)
    _display(sys.stdout, None, 0, ul, '')

def pause(*msgs, **vars):
    _display(sys.stdout, None, 0, '', *msgs, **vars)
    response = '?'
    while response and response not in ('y', 'yes', 'n', 'no'):
        sys.stdout.write('>>> Continue? (Y|n) ')
        response = sys.stdin.readline().strip().lower()
    if response and response[:1] != 'y':
        abort('Quit')

def input(prompt):
    sys.stdout.write('>>> %s: ' % prompt)
    try:
        return sys.stdin.readline().strip()
    except ValueError:
        pass
    except KeyboardInterrupt:
        sys.stderr.write('\n<BREAK>\n')
        raise

def menu(fixed_choices,
         message = None,
         default = None,
         other   = None,
         test    = None,
         prompt  = 'Choice'):
    if not message:
        message = 'Menu'
    print('\n::: %s :::' % message)
    choices = copy.copy(fixed_choices)
    imax = len(choices)
    iother = None
    if default is not None and isinstance(default, int):
        idefault = default
        default = None
    else:
        idefault = None
    if other is not None:
        choices.append(other + ' ...')
        iother = len(choices)
    if len(choices) == 0:
        abort('No choices available')
    if len(choices) == 1:
        prompt += ' [1]'
        if default is None:
            idefault = 1
    else:
        prompt += ' [1-%d]' % len(choices)
    for i in range(len(choices)):
        choice = choices[i]
        if i+1 == idefault:
            default  = choice
            print('  [%d]*%s' % (i+1, choice))
        elif choice == default:
            idefault = i+1
            print('  [%d]*%s' % (i+1, choice))
        else:
            print('  [%d] %s' % (i+1, choice))
    if idefault is not None:
        prompt += ' (default=%s)' % idefault
    while True:
        s = input(prompt)
        if s:
            try:
                i = int(s)
            except:
                i = -1
            if i > 0 and i <= imax:
                return choices[i-1]
            if i == iother:
                s = input(other)
                if s:
                    other_dir = os.path.realpath(os.path.expanduser(s))
                    if test is None or test(other_dir):
                        return other_dir
        else:
            if default is not None:
                return default
        error('Bad selection')

