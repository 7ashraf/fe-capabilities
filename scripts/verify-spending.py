#!/usr/bin/env python3
"""Verify Phase 3 spending and callbacks, including the administration regression."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main(record=None):
    fe = Path(os.environ.get('FE_BIN', ROOT / '.tools/bin/fe')).resolve()
    def run(*command):
        print('+ ' + ' '.join(map(str, command)), flush=True)
        subprocess.run(list(map(str, command)), cwd=ROOT, check=True)
    # This checks the pinned digest/version and full frozen ABI, then runs the
    # six administration tests and the separate actual transaction regression.
    run(sys.executable, 'scripts/verify-administration.py')
    run(fe, 'check', 'tests/runtime/spending')
    run(fe, 'fmt', 'tests/runtime/spending', '--check')
    run(fe, 'test', 'tests/runtime/spending', '--backend', 'sonatina', '-O', '1')
    run(fe, 'build', 'tests/runtime/spending', '--contract', 'CallbackRecipient',
        '--backend', 'sonatina', '--profile', 'release', '-O', '1',
        '--emit', 'bytecode,runtime-bytecode,abi,metadata')
    command = [sys.executable, 'scripts/anvil-spending.py']
    if record:
        command.extend(['--record', str(record)])
    run(*command)
    print('PASS Phase 3 spending verification', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', help='Optional raw Anvil spending evidence output path')
    main(parser.parse_args().record)
