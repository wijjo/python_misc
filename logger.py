import sys

def error(*msgs):
    indent = ''
    for msg in msgs:
        sys.stderr.write('ERROR: %s%s\n' % (indent, str(msg)))
        indent += '  '

def abort(*msgs):
    error(*msgs)
    sys.stderr.write('<ABORT>\n')
    sys.exit(1)

