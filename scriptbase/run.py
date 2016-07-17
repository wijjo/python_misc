#!/usr/bin/env python

import sys
import os
import subprocess
import tempfile
import scriptbase.logger as logger

### DEPRECATED ###
# Use command module instead.

def pipe_cmd(*args, **kwargs):
    """
    Run shell command, capture output, and yield output lines for iteration.
    """
    verbose = kwargs.get('verbose', False)
    try:
        if verbose:
            logger.verbose_info(' '.join(args))
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            for line in iter(proc.stdout.readline, ''):
                yield line.rstrip()
        finally:
            proc.stdout.close()
            proc.wait()
    except Exception as e:
        logger.warning('Exception running command: %s' % ' '.join(args), e)


def pipe_cmd_one(*args, **kwargs):
    """
    Run shell command and return one line of output.
    """
    ret_line = None
    for line in pipe_cmd(*args, **kwargs):
        if not ret_line:
            ret_line = line
    return ret_line


class Command(object):
    """
    Class that can be used to run a command, iterate its output, and access the
    return code.
    """

    def __init__(self, *args, **kwargs):
        self.retcode = 0
        self.dryrun = kwargs.get('dryrun', False)
        args2 = [str(a) for a in args]
        self.cmd_text = ' '.join(args2)
        self.input = kwargs.get('input', None)
        self.stdin = None
        popen_keywords = dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if not self.input is None:
            try:
                '' + self.input
                f = tempfile.SpooledTemporaryFile()
                f.write(self.input)
                f.seek(0)
                popen_keywords['stdin'] = f
            except TypeError:
                popen_keywords['stdin'] = self.input
        try:
            self.proc = subprocess.Popen(args2, **popen_keywords)
        except Exception as e:
            logger.abort('Error opening command:', [self.cmd_text, e])
            self.proc = None

    def pipe(self):
        """
        Pipe output on the fly to allow iteration.
        """
        if self.dryrun:
            logger.info('Command: %s' % self.cmd_text)
            return
        if self.proc is not None:
            try:
                for line in iter(self.proc.stdout.readline, ''):
                    yield line.rstrip()
            except Exception as e:
                logger.warning('Error processing command output:', [self.cmd_text, e])
            self.proc.stdout.close()
            if not self.stdin is None:
                self.stdin.close()
            self.retcode = self.proc.wait()
        else:
            logger.abort('Attempt to read output after command startup failed:',
                         [self.cmd_text])

    def run(self, echo=False):
        """
        Process the command synchronously and return a list of output lines.
        """
        if self.dryrun:
            logger.info('Command: %s' % self.cmd_text)
            return
        lines = [line for line in self.pipe()]
        if lines and echo:
            print('\n'.join(lines))
        if not self.stdin is None:
            self.stdin.close()
        return lines


def run_function(tag, checker, cmdargs, func, abort, *args, **kwargs):
    def arg_string():
        sargs = str(args)
        if sargs[-2] == ',':
            sargs = '%s)' % sargs[:-2]
        if kwargs:
            skwargs = ' %s' % str(kwargs)
        else:
            skwargs = ''
        return '%s%s%s' % (tag, sargs, skwargs)
    if cmdargs.verbose:
        logger.display_messages(arg_string(), tag='TRACE')
    elif cmdargs.pause:
        sys.stdout.write('COMMAND: %s\n[Press Enter to continue] ' % arg_string())
        sys.stdin.readline()
    ret = -1
    try:
        ret = func(*args, **kwargs)
        if checker is not None:
            errmsg = checker(ret, *args, **kwargs)
            if errmsg is not None:
                if abort:
                    logger.abort(errmsg, arg_string())
                else:
                    logger.error(errmsg, arg_string())
    except Exception as e:
        if abort:
            logger.abort(e, arg_string())
        else:
            logger.error(e, arg_string())
    return ret


class RunnerCommandArguments(dict):
    def __init__(self, **kwargs):
        dict.__init__(self, **kwargs)
    def __getattr__(self, name):
        return self.get(name, None)
    def __setattr__(self, name, value):
        self[name] = value


class Runner:
    def __init__(self, cmdargs, **kwargs):
        self.cmdargs = cmdargs
        self.kwargs = kwargs
    def update(self, **kwargs):
        for k in kwargs:
            self.kwargs[k] = kwargs[k]
    def shell(self, cmdline, abort = True):
        def checker(retcode, cmdline):
            if retcode != 0:
                return 'Command failed with return code %d: %s' % (retcode, cmdline)
        cmdlinex = self.expand(cmdline)
        if self.cmdargs.dryrun:
            sys.stdout.write('%s\n' % cmdlinex)
            return 0
        return run_function('shell', checker, self.cmdargs, os.system, abort, cmdlinex)
    def chdir(self, dir):
        dirx = self.expand(dir)
        if self.cmdargs.dryrun:
            sys.stdout.write('cd "%s"\n' % dirx)
        else:
            run_function('chdir', None, self.cmdargs, os.chdir, True, dirx)
    def check_directory(self, path, exists):
        pathx = self.expand(path)
        if self.cmdargs.dryrun:
            sys.stdout.write('test -d "%s" || exit 1\n' % pathx)
        else:
            def checker(actual_exists, path):
                if exists and not actual_exists:
                    return 'Directory "%s" does not exist' % path
                if not exists and actual_exists:
                    return 'Directory "%s" already exists' % path
            run_function('check_directory', checker, self.cmdargs, os.path.exists, True, pathx)
    def expand(self, s):
        try:
            return os.path.expanduser(os.path.expandvars(s)) % self.kwargs
        except ValueError as e:
            logger.abort(e, s)
