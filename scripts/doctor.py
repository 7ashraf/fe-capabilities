#!/usr/bin/env python3
"""Check prerequisites for the complete reproducible local verification suite."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def inspect():
    if sys.version_info < (3, 11):
        raise SystemExit('Python 3.11+ is required (the reuse runner uses tomllib).')
    system, machine = platform.system(), platform.machine()
    arch = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'amd64', 'AMD64': 'amd64'}.get(machine)
    if (system, arch) not in {('Darwin', 'arm64'), ('Linux', 'amd64')}:
        raise SystemExit('The full native/EVM suite requires macOS arm64 or Linux amd64; see docs/setup.md.')
    pins = json.loads((ROOT / 'toolchain.json').read_text())
    fe = Path(os.environ.get('FE_BIN', ROOT / '.tools/bin/fe')).resolve()
    if not fe.is_file():
        raise SystemExit('Fe is missing. Run python3 scripts/bootstrap-fe.py, or set FE_BIN to a pinned binary.')
    digest = hashlib.sha256(fe.read_bytes()).hexdigest()
    asset = f'fe_{"mac" if system == "Darwin" else "linux"}_{arch}'
    if 'sha256:' + digest != pins['fe']['assets'][asset]['digest']:
        raise SystemExit('Fe checksum differs from toolchain.json; select the pinned release.')
    version = subprocess.check_output([str(fe), '--version'], text=True).strip()
    if version != 'fe 26.5.0 (3dab95f)':
        raise SystemExit(f'Unexpected Fe version: {version}')
    tools = {}
    for name in ['anvil', 'cast']:
        if not shutil.which(name):
            raise SystemExit(f'{name} is missing from PATH; see docs/setup.md for the pinned Foundry version.')
        output = subprocess.check_output([name, '--version'], text=True).strip()
        if pins['foundry']['commit'] not in output or pins['foundry']['version'] not in output:
            raise SystemExit(f'{name} differs from pinned Foundry 1.5.1-stable; use the matching tools on PATH.')
        tools[name] = output
    report = {'schema_version': 1, 'python': platform.python_version(), 'os': system,
              'architecture': machine, 'fe': version, 'fe_asset': asset, 'fe_sha256': digest,
              'foundry': tools, 'evm_fork': pins['evm_fork'],
              'independent_review': pins['independent_review']['status']}
    print(f'PASS prerequisites: {system} {machine}; Python {platform.python_version()}; {version}; pinned Anvil/Cast')
    return report


def main(record=None):
    report = inspect()
    if record:
        Path(record).parent.mkdir(parents=True, exist_ok=True)
        Path(record).write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', help='Optional environment report JSON path')
    main(parser.parse_args().record)
