# Copyright 2016-17 Steven Cooper
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

"""Git utility classes and functions."""

import os
import re

from . import console
from . import utility
from .command import Command, Runner, Batch


GITHUB_ROOT_CONFIG = os.path.expanduser('~/.github_root')
RE_SECTION = re.compile(r'^\s*\[([^\]]+)\]\s*$')
RE_VERSION = re.compile(r'.* version ([^\s]+)', re.IGNORECASE)
RE_SUBMODULE = re.compile(r'^(.)([0-9a-f]+)\s+(.+) \((.+)\)\s*$')

def parse_version_number_string(version_string):
    """Parse a dot-separated version string."""
    return [int(s) for s in version_string.split(' ')[-1].split('.')]


def version_number_compare(version_string_1, version_string_2): #pylint: disable=too-many-return-statements
    """
    Compare two dot-separated version strings.

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
    for i in utility.range_iter(len(version2)):
        if len(version1) < i + 1 or version1[i] < version2[i]:
            return -1
        if version1[i] > version2[i]:
            return +1
    if len(version1) > len(version2):
        return +1
    return 0


def get_info():
    """Read ~/.gitconfig and return an object with <section>.<item> attributes."""
    class _Node(object):
        pass
    info = _Node()
    with open(os.path.expanduser('~/.gitconfig')) as file_handle:
        section = ''
        for line in file_handle:
            matched = RE_SECTION.match(line)
            if matched:
                section = matched.group(1).lower()
                setattr(info, section, _Node())
            else:
                name, value = [s.strip() for s in line.split('=', 1)]
                setattr(getattr(info, section), name.lower(), value)
    return info


def iter_branches(merged=False, unmerged=False, user=None):
    """Generate branch iterator."""
    cmd_args = ['git', 'branch', '-r']
    if merged:
        cmd_args.append('--merged')
    elif unmerged:
        cmd_args.append('--no-merged')
    with Command(*cmd_args) as cmd:
        for line in cmd:
            args = [s.strip() for s in line.split('->') if s.strip()]
            if len(args) == 1:
                branch = args[0]
                if user is None or get_branch_user(branch) == user:
                    yield branch


def get_branch_user(branch):
    """Get user name for given branch."""
    with Command('git', 'log', '--pretty=tformat:%an', '-1', branch) as cmd:
        for line in cmd:
            return line


def get_local_branch():
    """Get the checked out branch name."""
    branch = '(unknown)'
    with Command('git', 'branch') as cmd:
        for line in cmd:
            if line.startswith('* '):
                branch = line[2:]
    if cmd.return_code != 0:
        console.abort('You are not in a git workspace directory.')
    return branch


def get_tracking_branch():
    """
    Get the current tracking branch.

    http://stackoverflow.com/questions/171550/find-out-which-remote-branch-a-local-branch-is-tracking
    """
    with Command(
        'git',
        'for-each-ref',
        "--format='%(upstream:short)' $(git symbolic-ref -q HEAD)"
    ) as cmd:
        for line in cmd:
            return line
        if cmd.return_code != 0:
            console.abort('"git for-each-ref" failed with return code {return_code}',
                          return_code=cmd.return_code)


def iter_unmerged_commits(branch):
    """Get unmerged commits for given branch."""
    class _Item(object):
        def __init__(self, identifier, comment):
            self.identifier = identifier
            self.comment = comment
    with Command('git', 'cherry', '-v', 'master', branch) as cmd:
        for line in cmd:
            fields = line.split(None, 2)
            if len(fields) == 3 and fields[0] == '+':
                yield _Item(fields[1], fields[2])


def _unquote_path(path):
    if not path or path[0] != '"' or path[-1] != '"':
        return path
    return path[1:-1]


def iter_changes(submodules=False):
    """Iterate file change status."""
    def _get_status(line, submodule):
        class _FileStatus(object):
            def __init__(self, flag, path, path2, modified):
                self.flag = flag
                self.path = path
                self.path2 = path2
                self.modified = modified
        def _get_path(base_path):
            ret_path = base_path if not submodule else os.path.join(submodule, base_path)
            return _unquote_path(ret_path)
        flag, path = line.split(None, 1)
        path = _get_path(path)
        path2 = None if not flag.startswith('R') else _get_path(line.split(' -> ')[-1])
        try:
            modified = os.stat(path2 if path2 else path).st_mtime
        except OSError:
            modified = 0.0
        return _FileStatus(flag, path, path2, modified)
    status_cmd_args = ('git', 'status', '--porcelain', '--ignore-submodules')
    with Command(*status_cmd_args) as cmd:
        for line in cmd:
            yield _get_status(line, None)
    if submodules:
        submodule = None
        with Command('git', 'submodule', 'foreach', ' '.join(status_cmd_args)) as cmd:
            for line in cmd:
                if line.startswith('Entering'):
                    submodule = line[10:-1]
                else:
                    yield _get_status(line, submodule)


def get_changes():
    """Provide file status without sorting."""
    return list(iter_changes())


def get_changes_by_time():
    """Provide file status ordered by time."""
    return sorted(list(iter_changes()), key=lambda x: x.modified)


def remote_branch_exists(url, branch, verbose=False):
    """Return True if the remote branch name exists."""
    args = ['git', 'ls-remote', '--heads', url, branch]
    if verbose:
        console.verbose_info(' '.join(args))
    with Command(*args) as cmd:
        for line in cmd:
            if verbose:
                console.verbose_info(line)
            if line.split()[-1].split('/')[-1] == branch:
                return True
    return False


def git_project_root(directory=None, optional=False):
    """Return the Git project root if inside a Git local repository."""
    def _get_project_root():
        with Command('git', 'rev-parse', '--show-toplevel') as cmd:
            for line in cmd:
                return line
    root_directory = None
    if directory:
        with utility.working_directory_context(directory):
            root_directory = _get_project_root()
    else:
        root_directory = _get_project_root()
    if not root_directory and not optional:
        console.abort('Failed to find git project root directory.')
    return root_directory


def get_github_root(github_root):
    """Read and or write the GitHub root from GITHUB_ROOT_CONFIG."""
    if github_root:
        console.info('Saving new GitHub root...')
        try:
            with open(GITHUB_ROOT_CONFIG, 'w') as file_handle:
                file_handle.write(github_root)
                file_handle.write(os.linesep)
        except (IOError, OSError) as exc:
            console.abort('Unable to save "%s"' % GITHUB_ROOT_CONFIG, exc)
    else:
        try:
            with open(GITHUB_ROOT_CONFIG) as file_handle:
                github_root = file_handle.read().strip()
        except (IOError, OSError) as exc:
            console.abort('Unable to read "%s"' % GITHUB_ROOT_CONFIG, exc)
    return github_root


def git_version():
    """Return the git program version."""
    version = None
    with Command('git', '--version') as cmd:
        for line in cmd:
            if version is None:
                matched = RE_VERSION.search(line)
                if not matched:
                    console.abort('Failed to parse git version: %s', line.strip())
                version = matched.group(1)
    return version


def is_git_version_newer(min_version):
    """Return True if the git program version is newer than a given version."""
    version = git_version()
    if version is None:
        return False
    return version_number_compare(version, min_version) >= 0


def create_branch(      # pylint: disable=too-many-arguments
        url,
        branch,
        ancestor=None,
        create_remote=False,
        dry_run=False,
        verbose=False):
    """Create a new branch."""
    runner = Runner(Runner.CommandArguments(dry_run=dry_run, verbose=verbose))
    runner.var.branch = branch
    runner.var.ancestor = ancestor if ancestor else 'master'
    # Create local branch.
    if branch != 'master':
        runner.shell('git branch {branch} origin/{ancestor}')
    # Create remote branch?
    if create_remote:
        create_remote_branch(url, branch, dry_run=dry_run, verbose=verbose)


def create_remote_branch(url, branch, dry_run=False, verbose=False):
    """Create a new remote branch."""
    runner = Runner(Runner.CommandArguments(dry_run=dry_run, verbose=verbose))
    runner.var.branch = branch
    remote_exists = False
    if not dry_run:
        if url is None:
            url = get_repository_url()
            if url is None:
                console.warning("Failed to get repository URL, assuming the branch does not exist.")
            else:
                remote_exists = remote_branch_exists(url, branch, verbose=verbose)
    if not remote_exists:
        console.info(runner.expand('Creating remote branch {branch}...'))
        runner.shell('git push origin {branch}:{branch}')
    # Check out branch.
    runner.shell('git checkout {branch}')
    # Set up remote tracking.
    if branch != 'master' and not remote_exists:
        console.info('Setting local branch to track to remote...')
        if is_git_version_newer('1.8'):
            runner.shell('git branch --set-upstream-to origin/{branch}')
        else:
            runner.shell('git branch --set-upstream {branch} origin/{branch}')


def get_repository_url():
    """Get the URL for the remote repository."""
    with Command('git', 'config', '--get', 'remote.origin.url') as cmd:
        for line in cmd:
            return line


def iter_submodules():
    """Yield submodule relative paths."""
    with Command('git', 'submodule') as cmd:
        for line in cmd:
            matched = RE_SUBMODULE.match(line)
            if matched:
                yield matched.group(3)
            else:
                print(line)


def rename_branch(branch, remote_name=None, rename_remote=False, dry_run=False):
    """Rename the local and (optionally) the remote branch."""
    old_local = get_local_branch()
    new_local = branch
    batch = Batch(dry_run=dry_run)
    batch.add_command('git', 'branch', '-m', old_local, new_local)
    if rename_remote:
        new_remote = remote_name if remote_name else new_local
        batch.add_command('git', 'push', 'origin', new_remote)
        batch.add_command('git', 'branch', '--set-upstream', new_local, 'origin/%s' % new_remote)
    batch.run()
