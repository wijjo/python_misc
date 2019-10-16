#pylint: disable=missing-docstring

from scriptbase.argdeco import CLI

@CLI.Main(
    description='CLI test program',
    arguments=[
        (['-r', '--reps'], CLI.Integer('AOI', 'global integer option')),
        (['-v', '--verbose'], CLI.Boolean('AOB', 'global boolean option')),
        CLI.String('AOS', '-t', 'global string option'),
    ]
)
def _main(args, results):
    results.update('main', args)

@CLI.Command(
    'bbb',
    arguments=[
        ('-i', CLI.Integer('BOI', 'bbb integer option')),
        ('-b', CLI.Boolean('BOB', 'bbb boolean option')),
        ('-s', CLI.String('BOS', 'bbb string option')),
        CLI.Integer('BAI', 'bbb integer argument'),
        CLI.Boolean('BAB', 'bbb boolean argument'),
        CLI.String('BAS', 'bbb string argument'),
    ]
)
def _bbb(args, results):
    results.update('bbb', args)

@CLI.Command(
    'ccc',
    arguments=[
        ('-I', CLI.Integer('COI', 'ccc integer option')),
        ('-B', CLI.Boolean('COB', 'ccc boolean option')),
        ('-S', CLI.String('COS', 'ccc string option')),
        CLI.Integer('CAI', 'ccc integer argument'),
        CLI.Boolean('CAB', 'ccc boolean argument'),
        CLI.String('CAS', 'ccc string argument'),
    ]
)
def _ccc(args, results):
    results.update('ccc', args)

def canon_dict(args):
    return {k: args[k] for k in sorted(args.keys())}

def run_test(cli_args, exp_called, exp_args):
    class Results:
        def __init__(self):
            self.called = []
            self.args = None
        def update(self, name, args):
            self.called.append(name)
            self.args = {k: getattr(args, k) for k in args.__dict__.keys() if k[0] != '_'}
    exp_args['ZZZ_SUBCOMMANDS'] = exp_called[-1] if len(exp_called) > 1 else None
    results = Results()
    import argparse
    try:
        CLI.main(results, cli_args=cli_args, abort_exception=True)
    except (argparse.ArgumentError, SystemExit):
        return 1
    exp_args = canon_dict(exp_args)
    res_args = canon_dict(results.args)
    errors = 0
    if exp_called != results.called:
        print('called: expected {}'.format(exp_called))
        print('called: received {}'.format(results.called))
        errors += 1
    if exp_args != res_args:
        print('args: expected {}'.format(exp_args))
        print('args: received {}'.format(res_args))
        errors += 1
    return errors

class Tests:

    def __init__(self):
        self.errors = 0

    def run(self):
        self.errors += run_test(
            [],
            ['main'],
            dict(AOB=False,
                 AOI=None,
                 AOS=None))
        self.errors += run_test(
            ['-v'],
            ['main'],
            dict(AOB=True,
                 AOI=None,
                 AOS=None))
        self.errors += run_test(
            ['-r', '99', '-t', 'abc'],
            ['main'],
            dict(AOB=False,
                 AOI=99,
                 AOS='abc'))
        self.errors += run_test(
            ['bbb', '111', 'true', 'BBB'],
            ['main', 'bbb'],
            dict(AOB=False,
                 AOI=None,
                 AOS=None,
                 BAB=True,
                 BAI=111,
                 BAS='BBB',
                 BOB=False,
                 BOI=None,
                 BOS=None))
        print('Total errors: {}'.format(self.errors))

def main():
    tests = Tests()
    tests.run()
    return tests.errors

if __name__ == '__main__':
    import sys
    sys.exit(main())
