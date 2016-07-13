#!/usr/bin/env python

import sys, os, os.path

is_text = ('DISPLAY' not in os.environ or int(os.environ.get('SHLVL', 0)) > 0)
verbose = False

def set_verbose(value):
    global verbose
    verbose = value

def in_path(prog):
    for dir in os.environ['PATH'].split(':'):
        path = os.path.join(dir, prog)
        if os.path.exists(path):
            return path

def choose(*clss):
    for cls in clss:
        needs_gui = getattr(cls, 'gui', False)
        if not needs_gui or not is_text and hasattr(cls, 'program') and in_path(cls.program):
            return cls()
    programs = '|'.join([cls.program for cls in clss])
    sys.stderr.write('ERROR: program not found (%s)\n' % programs)
    sys.exit(1)

class DialogBase(object):
    def info(self, func_info = None, func_error = None):
        self.func_info  = func_info
        self.func_error = func_error
    def info(self, msg):
        self.dialog_info(msg)
        print msg
    def error(self, msg):
        self.dialog_error(msg)
        sys.stderr.write('ERROR: %s\n' % msg)
    def abort(self, msg):
        self.error('%s\n\nABORT' % msg)
        sys.exit(1)
    def get_password(self, title = 'Enter Password', prompt = 'Password'):
        return self.dialog_password(title, prompt)
    def dialog_info(self, msg):
        pass
    def dialog_error(self, msg):
        pass

class Dialog(DialogBase):
    program = 'dialog'
    def dialog_password(self, title, prompt):
        return os.popen('dialog --stdout --title "%s" --insecure --passwordbox "%s:" 8 50'
                            % (title, title)).readline().strip()

class Zenity(DialogBase):
    program = 'zenity'
    gui = True
    def dialog_info(self, msg):
        os.system('zenity --info --text="%s"' % msg)
    def dialog_error(self, msg):
        os.system('zenity --error --text="%s"' % msg)
    def dialog_password(self, title, prompt):
        return os.popen('zenity --width=400 --title="%s" --hide-text --entry --text="%s:"'
                            % (title, title)).readline().strip()

class Kdialog(DialogBase):
    program = 'kdialog'
    gui = True
    def dialog_info(self, msg):
        os.system('kdialog --msgbox "%s"' % msg)
    def dialog_error(self, msg):
        os.system('kdialog --error "%s"' % msg)
    def dialog_password(self, title, prompt):
        return os.popen('kdialog --title="%s" --password "%s:"'
                            % (title, title)).readline().strip()

class SudoBase(object):
    def run(self, cmd):
        if verbose:
            print('SUDO: %s' % cmd)
        return self.dialog_run(cmd)

class Sudo(SudoBase):
    program = 'sudo'
    def dialog_run(self, cmd):
        return os.system('sudo %s' % cmd)

class GkSudo(SudoBase):
    program = 'gksudo'
    gui = True
    def dialog_run(self, cmd):
        return os.system('gksudo -- %s' % cmd)

class KdeSudo(SudoBase):
    program = 'kdesudo'
    gui = True
    def dialog_run(self, cmd):
        return os.system('kdesudo %s' % cmd)

dialog_general = choose(Kdialog, Zenity, Dialog)
dialog_sudo    = choose(KdeSudo, GkSudo, Sudo)

def info(*args, **kwargs):
    return dialog_general.info(*args, **kwargs)

def error(*args, **kwargs):
    return dialog_general.error(*args, **kwargs)

def abort(*args, **kwargs):
    return dialog_general.abort(*args, **kwargs)

def get_password(*args, **kwargs):
    return dialog_general.get_password(*args, **kwargs)

def sudo(*args, **kwargs):
    return dialog_sudo.run(*args, **kwargs)
