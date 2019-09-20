#pylint: disable=missing-docstring

from scriptbase.argdeco import CLI

@CLI.Main(
    description='CLI test program',
    arguments=[
        CLI.Opt.Integer('AOI', ['-r', '--reps'], 'global integer option'),
        CLI.Opt.Boolean('AOB', ['-v', '--verbose'], 'global boolean option'),
        CLI.Opt.String('AOS', '-t', 'global string option'),
    ]
)
def _main(args, results):
    results.update('main', args)

@CLI.Command(
    'bbb',
    arguments=[
        CLI.Opt.Integer('BOI', '-i', 'bbb integer option'),
        CLI.Opt.Boolean('BOB', '-b', 'bbb boolean option'),
        CLI.Opt.String('BOS', '-s', 'bbb string option'),
        CLI.Arg.Integer('BAI', 'bbb integer argument'),
        CLI.Arg.Boolean('BAB', 'bbb boolean argument'),
        CLI.Arg.String('BAS', 'bbb string argument'),
    ]
)
def _bbb(args, results):
    results.update('bbb', args)

@CLI.Command(
    'ccc',
    arguments=[
        CLI.Opt.Integer('COI', '-I', 'ccc integer option'),
        CLI.Opt.Boolean('COB', '-B', 'ccc boolean option'),
        CLI.Opt.String('COS', '-S', 'ccc string option'),
        CLI.Arg.Integer('CAI', 'ccc integer argument'),
        CLI.Arg.Boolean('CAB', 'ccc boolean argument'),
        CLI.Arg.String('CAS', 'ccc string argument'),
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
    CLI.main(results, cli_args=cli_args)
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
