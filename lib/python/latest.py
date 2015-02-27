import sys
import os
if sys.version_info[0] == 2 and sys.version_info[1] < 6:
    for dir in os.environ['PATH'].split(':'):
        for name in ('python2.7', 'python2.6'):
            path = os.path.join(dir, name)
            if os.path.exists(path):
                print 'Re-running with %s...' % path
                os.execv(path, [path] + sys.argv)
