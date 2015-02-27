#!/usr/bin/env python

import os
import subprocess
import re
import logger
import run
import utility


class G:
    github_root_config = os.path.expanduser('~/.github_root')
    re_section = re.compile('^\s*\[([^\]]+)\]\s*$')


def get_info():
    """
    Read ~/.gitconfig and return an object with <section>.<item> attributes.
    """
    class Node(object): pass
    info = Node()
    with open(os.path.expanduser('~/.gitconfig')) as f:
        section = ''
        for line in f:
            m = re_section.match(line)
            if m:
                section = m.group(1).lower()
                setattr(info, section, Node())
            else:
                name, value = [s.strip() for s in line.split('=', 1)]
                setattr(getattr(info, section), name.lower(), value)
    return info


def iter_branches(merged = False, unmerged = False, user = None):
    """
    Generate branch iterator.
    """
    opts = ''
    if merged:
        opts = ' --merged'
    elif unmerged:
        opts = ' --no-merged'
    git_branch = subprocess.Popen('git branch -r%s' % opts, shell=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in git_branch.communicate()[0].split('\n'):
        args = [s.strip() for s in line.split('->') if s.strip()]
        if len(args) == 1:
            branch = args[0]
            if user is None or get_branch_user(branch) == user:
                yield branch


def get_branch_user(branch):
    """
    Get user name for given branch.
    """
    git_branch = subprocess.Popen('git log --pretty=tformat:%%an -1 %s' % branch,
                                  shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return git_branch.communicate()[0].split('\n')[0].strip()


def get_local_branch():
    """
    Get the checked out branch name.
    """
    proc = subprocess.Popen('git status',
                            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    line = proc.communicate()[0].split('\n')[0].strip()
    if proc.returncode != 0:
        logger.abort('You are not in a git workspace folder.')
    return line.split()[-1]


def get_tracking_branch():
    """
    Get the current tracking branch.
    http://stackoverflow.com/questions/171550/find-out-which-remote-branch-a-local-branch-is-tracking
    """
    git_branch = subprocess.Popen("git for-each-ref --format='%(upstream:short)' "
                                  "$(git symbolic-ref -q HEAD)",
                                  shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return git_branch.communicate()[0].split('\n')[0].strip()


def iter_unmerged_commits(branch):
    """
    Get unmerged commits for given branch.
    """
    class Item(object): pass
    git_branch = subprocess.Popen('git cherry -v master %s' % branch,
                                  shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in git_branch.communicate()[0].split('\n'):
        fields = line.split(None, 2)
        if len(fields) == 3 and fields[0] == '+':
            item = Item()
            item.identifier = fields[1]
            item.comment    = fields[2]
            yield item


def find_branch_root(dir_start=None):
    if dir_start is None:
        branch_root = os.getcwd()
    else:
        branch_root = dir_start
    while branch_root != '/':
        if os.path.isdir(os.path.join(branch_root, '.git')):
            return branch_root
        branch_root = os.path.dirname(branch_root)
    logger.abort('Failed to find working project root folder.')


#def delete_branch():
#    #TODO: WIP
#    git_branch = subprocess.Popen('git branch -r%s' % opts, shell=True,
#                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
#    for line in git_branch.communicate()[0].split('\n'):
#        print line


class FileStatus(object):
    def __init__(self, flag, path, path2, modified):
        self.flag = flag
        self.path = path
        self.path2 = path2
        self.modified = modified

def _unquote_path(path):
    if not path or path[0] != '"' or path[-1] != '"':
        return path
    return path[1:-1]

def iter_changes():
    """
    Iterate file change status.
    """
    for s in run.pipe_cmd('git', 'status', '--porcelain'):
        flag, path = s.split(None, 1)
        path = _unquote_path(path)
        if flag.startswith('R'):
            path2 = _unquote_path(s.split(' -> ')[-1])
        else:
            path2 = None
        try:
            if path2:
                modified = os.stat(path2).st_mtime
            else:
                modified = os.stat(path).st_mtime
        except OSError:
            modified = 0.0
        yield FileStatus(flag, path, path2, modified)


def get_changes():
    """
    Provide file status without sorting
    """
    return list(iter_changes())


def get_changes_by_time():
    """
    Provide file status ordered by time.
    """
    changes = list(iter_changes())
    changes.sort(cmp=lambda x, y: cmp(x.modified, y.modified))
    return changes


def remote_branch_exists(url, branch, verbose=False):
    """
    Returns True if the remote branch name exists.
    """
    for s in run.pipe_cmd('git', 'ls-remote', '--heads', url, branch, verbose=verbose):
        if verbose:
            logger.verbose_info(s)
        if s.split()[-1].split('/')[-1] == branch:
            return True
    return False


def git_project_root(dir=None, optional=False):
    rootdir = dir
    if not rootdir:
        rootdir = os.getcwd()
    while rootdir != '/':
        if os.path.isdir(os.path.join(rootdir, '.git')):
            break
        rootdir = os.path.dirname(rootdir)
    else:
        if not optional:
            logger.abort('Failed to find git project root folder.')
        rootdir = None
    return rootdir


def get_github_root(github_root):
    filetool = utility.FileTool(lstrip=True, rstrip=True)
    if github_root:
        logger.info('Saving new GitHub root...')
        filetool.save(G.github_root_config, github_root)
    else:
        for line in filetool.readlines(G.github_root_config):
            github_root = line
        if not github_root:
            logger.abort('Unable to determine the GitHub root - please specify one.')
    return github_root

