#!/usr/bin/env python3
"""Reproduce Phase 0 evidence with the pinned compiler and local Foundry tools."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def run(*command):
    print('+ ' + ' '.join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=ROOT, check=True)


def main():
    configured = os.environ.get('FE_BIN')
    fe = Path(configured).resolve() if configured else ROOT / '.tools' / 'bin' / 'fe'
    if not fe.is_file():
        candidate = shutil.which('fe')
        if not candidate:
            raise SystemExit('Run python3 scripts/bootstrap-fe.py first, or set FE_BIN.')
        fe = Path(candidate)
    manifest = json.loads((ROOT / 'toolchain.json').read_text())
    system = {'Darwin': 'mac', 'Linux': 'linux'}[platform.system()]
    arch = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'amd64'}[platform.machine()]
    expected = manifest['fe']['assets'][f'fe_{system}_{arch}']['digest']
    assert 'sha256:' + hashlib.sha256(fe.read_bytes()).hexdigest() == expected, 'Fe binary checksum mismatch'
    version = subprocess.check_output([str(fe), '--version'], text=True).strip()
    assert version == 'fe 26.5.0 (3dab95f)', version
    print(version, flush=True)
    run(fe, 'check', 'spike')
    run(fe, 'fmt', 'spike', '--check')
    run(fe, 'fmt', 'tests', '--check')
    run(fe, 'test', 'tests/reference/language_smoke.fe', 'tests/reference/contract_smoke.fe', '-O', '1')
    run(fe, 'test', 'tests/reference/language_smoke.fe', '--backend', 'native', '-O', '1')
    run(fe, 'test', 'spike', '--backend', 'sonatina', '-O', '1')
    run(fe, 'check', 'tests/compile_fail/allowed')
    run(fe, 'test', 'tests/compile_fail/allowed', '-O', '1')
    allowed = (ROOT / 'tests/compile_fail/allowed/src/lib.fe').read_text()
    readonly = (ROOT / 'tests/compile_fail/readonly/src/lib.fe').read_text()
    assert allowed.replace('budget: mut Budget', 'budget: Budget') == readonly, 'Access pair must differ only by mutability'
    command = [str(fe), 'check', '--color', 'never', 'tests/compile_fail/readonly']
    print('+ ' + ' '.join(command) + ' (expected failure)', flush=True)
    negative = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    diagnostic = negative.stdout + negative.stderr
    assert negative.returncode == 1, f'Expected compiler rejection, got {negative.returncode}: {diagnostic}'
    assert diagnostic.count('error[') == 1 and 'error[8-0037]' in diagnostic, diagnostic
    assert 'must be mutable when calling `reserve`' in diagnostic, diagnostic
    print(diagnostic, end='', flush=True)
    print('PASS read-only consumer rejected for the intended effect requirement', flush=True)
    run(fe, 'build', 'spike', '--backend', 'sonatina', '--profile', 'release', '-O', '1',
        '--emit', 'bytecode,runtime-bytecode,abi,metadata')
    run(sys.executable, 'scripts/anvil-payment.py')
    print('PASS Phase 0 verification', flush=True)


if __name__ == '__main__':
    main()
