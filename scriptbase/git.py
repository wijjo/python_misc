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

import os
import subprocess
import re

from . import console
from . import command


GITHUB_ROOT_CONFIG = os.path.expanduser('~/.github_root')
RE_SECTION = re.compile('^\s*\[([^\]]+)\]\s*$')
RE_VERSION = re.compile('.* version ([^\s]+)', re.IGNORECASE)


def parse_version_number_string(version_string):
    return [int(s) for s in version_string.split(' ')[-1].split('.')]


def version_number_compare(version_string_1, version_string_2):
    """
    Compare two dot-separated version strings
    return 0 if version_string_1 = version_string_2
          -1 if version_string_1 < version_string_2
          +1 if version_string_1 > version_string_2
    """
    if version_string_1 is None:
        if version_string_2 is None:
            return 0
        return -1
    if version_string_2 is None:
        return 1
    version1 = parse_version_number_string(version_string_1)
    version2 = parse_version_number_string(version_string_2)
    for i in xrange(len(version2)):
        if len(version1) < i + 1 or version1[i] < version2[i]:
            return -1
        if version1[i] > version2[i]:
            return +1
    if len(version1) > len(version2):
        return +1
    return 0


def get_info():
    """
    Read ~/.gitconfig and return an object with <section>.<item> attributes.
    """
    class Node(object): pass
    info = Node()
    with open(os.path.expanduser('~/.gitconfig')) as f:
        section = ''
        for line in f:
            m = RE_SECTION.match(line)
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
    proc = subprocess.Popen('git branch',
                            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    branch = '(unknown)'
    for line in proc.communicate()[0].split('\n'):
        if line.startswith('* '):
            branch = line[2:]
    if proc.returncode != 0:
        console.abort('You are not in a git workspace folder.')
    return branch


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
        if os.path.exists(os.path.join(branch_root, '.git')):
            return branch_root
        branch_root = os.path.dirname(branch_root)
    console.abort('Failed to find working project root folder.')


#def delete_branch():
#    #TODO: WIP
#    git_branch = subprocess.Popen('git branch -r%s' % opts, shell=True,
#                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
#    for line in git_branch.communicate()[0].split('\n'):
#        print line


def _unquote_path(path):
    if not path or path[0] != '"' or path[-1] != '"':
        return path
    return path[1:-1]


def iter_changes(submodules=False):
    """
    Iterate file change status.
    """
    def _get_status(s, submodule):
        class FileStatus(object):
            def __init__(self, flag, path, path2, modified):
                self.flag = flag
                self.path = path
                self.path2 = path2
                self.modified = modified
        def _get_path(p):
            p2 = p if not submodule else os.path.join(submodule, p)
            return _unquote_path(p2)
        flag, path = s.split(None, 1)
        path = _get_path(path)
        path2 = None if not flag.startswith('R') else _get_path(s.split(' -> ')[-1])
        try:
            modified = os.stat(path2 if path2 else path).st_mtime
        except OSError:
            modified = 0.0
        return FileStatus(flag, path, path2, modified)
    status_cmd_args = ('git', 'status', '--porcelain', '--ignore-submodules')
    with command.Command(*status_cmd_args) as cmd:
        for s in cmd:
            yield _get_status(s, None)
    if submodules:
        submodule = None
        with command.Command('git', 'submodule', 'foreach', ' '.join(status_cmd_args)) as cmd:
            for s in cmd:
                if s.startswith('Entering'):
                    submodule = s[10:-1]
                else:
                    yield _get_status(s, submodule)


def get_changes():
    """
    Provide file status without sorting
    """
    return list(iter_changes())


def get_changes_by_time():
    """
    Provide file status ordered by time.
    """
    return sorted(list(iter_changes()), key=lambda x: x.modified)


def remote_branch_exists(url, branch, verbose=False):
    """
    Returns True if the remote branch name exists.
    """
    args = ['git', 'ls-remote', '--heads', url, branch]
    if verbose:
        console.verbose_info(' '.join(args))
    with command.Command(*args) as cmd:
        for s in cmd:
            if verbose:
                console.verbose_info(s)
            if s.split()[-1].split('/')[-1] == branch:
                return True
    return False


def git_project_root(dir=None, optional=False):
    if dir:
        os.chdir(dir)
        save_dir = os.getcwd()
    else:
        save_dir = None
    try:
        with command.Command('git', 'rev-parse', '--show-toplevel') as cmd:
            root_dir = cmd.next()
    finally:
        if save_dir:
            os.chdir(save_dir)
    if not root_dir and not optional:
        console.abort('Failed to find git project root folder.')
    return root_dir


def get_github_root(github_root):
    if github_root:
        console.info('Saving new GitHub root...')
        try:
            with open(GITHUB_ROOT_CONFIG, 'w') as f:
                f.write(github_root)
                f.write(os.linesep)
        except (IOError, OSError) as e:
            console.abort('Unable to save "%s"' % GITHUB_ROOT_CONFIG, e)
    else:
        try:
            with open(GITHUB_ROOT_CONFIG) as f:
                github_root = f.read().strip()
        except (IOError, OSError) as e:
            console.abort('Unable to read "%s"' % GITHUB_ROOT_CONFIG, e)
    return github_root


def git_version():
    version = None
    with command.Command('git', '--version') as cmd:
        for line in cmd:
            if version is None:
                m = RE_VERSION.search(line)
                if not m:
                    console.abort('Failed to parse git version: %s', line.strip())
                version = m.group(1)
    return version


def is_git_version_newer(min_version):
    version = git_version()
    if version is None:
        return False
    return version_number_compare(version, min_version) >= 0


def create_branch(url, branch, ancestor=None, create_remote=False, dryrun=False, verbose=False):
    if ancestor is None:
        ancestor = 'master'
    runner = command.Runner(command.RunnerCommandArguments(dryrun=dryrun, verbose=verbose))
    runner.set_symbols(branch=branch, ancestor=ancestor)
    # Create local branch.
    if branch != 'master':
        runner.shell('git branch %(branch)s origin/%(ancestor)s')
    # Create remote branch?
    if create_remote:
        create_remote_branch(url, branch, dryrun=dryrun, verbose=verbose)


def create_remote_branch(url, branch, dryrun=False, verbose=False):
    runner = command.Runner(command.RunnerCommandArguments(dryrun=dryrun, verbose=verbose))
    runner.set_symbols(branch=branch)
    remote_exists = False
    if not dryrun:
        if url is None:
            url = get_repository_url()
            if url is None:
                console.warning("Failed to get repository URL, assuming the branch does not exist.")
            else:
                remote_exists = remote_branch_exists(url, branch, verbose=verbose)
    if not remote_exists:
        console.info(runner.expand('Creating remote branch %(branch)s...'))
        runner.shell('git push origin %(branch)s:%(branch)s')
    # Check out branch.
    runner.shell('git checkout %(branch)s')
    # Set up remote tracking.
    if branch != 'master' and not remote_exists:
        console.info('Setting local branch to track to remote...')
        if is_git_version_newer('1.8'):
            runner.shell('git branch --set-upstream-to origin/%(branch)s')
        else:
            runner.shell('git branch --set-upstream %(branch)s origin/%(branch)s')


def get_repository_url():
    with command.Command('git', 'config', '--get', 'remote.origin.url') as cmd:
        for line in cmd:
            return line


def iter_submodules():
    with command.Command('git', 'submodule', '--quiet', 'foreach', 'echo $name') as cmd:
        for line in cmd:
            yield line.strip()
