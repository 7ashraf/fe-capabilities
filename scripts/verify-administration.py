#!/usr/bin/env python3
"""Verify the Phase 2 contract, administrative ABI subset, and actual transactions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
FUNCTIONS = {'createGrant', 'revoke', 'owner', 'nextGrantId', 'treasuryBalance', 'getGrant'}
EVENTS = {'GrantCreated', 'GrantRevoked'}
ERRORS = {'InvalidOwner', 'Unauthorized', 'InvalidAddress', 'InvalidAmount', 'InvalidExpiry',
          'GrantIdExhausted', 'UnknownGrant', 'InvalidGrantState', 'Reentrant', 'UnsupportedCall'}


def normalized(entries):
    def parameter(value):
        # Argument/return labels are metadata, not part of canonical ABI encoding.
        return {key: ([parameter(c) for c in item] if key == 'components' else item)
                for key, item in value.items() if key != 'name'}
    results = {}
    for entry in entries:
        key = (entry['type'], entry.get('name', ''))
        assert key not in results, f'Duplicate ABI entry {key}'
        results[key] = {key: [parameter(p) for p in value] if key in {'inputs', 'outputs'} else value
                        for key, value in entry.items()}
    return results


def check_abi():
    actual = json.loads((ROOT / 'treasury/out/Treasury.abi.json').read_text())
    frozen = json.loads((ROOT / 'spec/treasury-v0.abi.json').read_text())
    expected = [entry for entry in frozen if
                entry['type'] in {'constructor', 'fallback'} or
                entry['type'] == 'function' and entry['name'] in FUNCTIONS or
                entry['type'] == 'event' and entry['name'] in EVENTS or
                entry['type'] == 'error' and entry['name'] in ERRORS]
    assert len(expected) == 20, 'Unexpected phase coverage fixture'
    assert normalized(actual) == normalized(expected), 'Emitted ABI differs from the frozen administrative subset'
    snapshot = json.loads((ROOT / 'spec/treasury-admin-v1.abi.json').read_text())
    assert actual == snapshot, 'Emitted ABI differs from the versioned Phase 2 snapshot'
    print('PASS emitted ABI: 6 functions, 2 events, 10 errors, constructor and fallback', flush=True)


def main(record=None):
    fe = Path(os.environ.get('FE_BIN', ROOT / '.tools/bin/fe')).resolve()
    manifest = json.loads((ROOT / 'toolchain.json').read_text())
    system = {'Darwin': 'mac', 'Linux': 'linux'}[platform.system()]
    arch = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'amd64'}[platform.machine()]
    digest = 'sha256:' + hashlib.sha256(fe.read_bytes()).hexdigest()
    assert digest == manifest['fe']['assets'][f'fe_{system}_{arch}']['digest']
    assert subprocess.check_output([str(fe), '--version'], text=True).strip() == 'fe 26.5.0 (3dab95f)'
    def run(*command):
        print('+ ' + ' '.join(map(str, command)), flush=True)
        subprocess.run(list(map(str, command)), cwd=ROOT, check=True)
    run(fe, 'check', 'treasury')
    run(fe, 'fmt', 'treasury', '--check')
    run(fe, 'fmt', 'tests/runtime/administration', '--check')
    run(fe, 'check', 'tests/runtime/administration')
    run(fe, 'test', 'tests/runtime/administration', '--backend', 'sonatina', '-O', '1')
    run(fe, 'build', 'treasury', '--contract', 'Treasury', '--backend', 'sonatina', '--profile', 'release',
        '-O', '1', '--emit', 'bytecode,runtime-bytecode,abi,metadata')
    check_abi()
    command = [sys.executable, 'scripts/anvil-administration.py']
    if record:
        command.extend(['--record', str(record)])
    run(*command)
    print('PASS Phase 2 administration verification', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', help='Optional raw Anvil evidence output path')
    main(parser.parse_args().record)
