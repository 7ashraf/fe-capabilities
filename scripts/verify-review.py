#!/usr/bin/env python3
"""Run Phase 5 technical evidence; independent developer feedback is a separate gate."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main(record_dir=None):
    def run(script, *arguments):
        command = [sys.executable, 'scripts/' + script, *map(str, arguments)]
        print('+ ' + ' '.join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
    run('verify-reuse.py')
    run('verify-policy.py')
    run('verify-phase0.py')
    for script, filename in [('verify-mutations.py', 'mutations.json'),
                             ('anvil-review.py', 'adversarial-review.json'),
                             ('demo.py', 'demo.json')]:
        arguments = ['--record', str(Path(record_dir) / filename)] if record_dir else []
        run(script, *arguments)
    print('PASS Phase 5 technical checks. Independent developer feedback remains a separate review requirement.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record-dir', help='Optional evidence directory relative to repository root')
    main(parser.parse_args().record_dir)
