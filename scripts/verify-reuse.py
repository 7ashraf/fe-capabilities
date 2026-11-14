#!/usr/bin/env python3
"""Verify independent consumers, shared compiler inputs, and safe-code boundaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent


def shared_policy():
    pins = json.loads((ROOT / 'toolchain.json').read_text())['policy_package']
    policy = ROOT / 'policy'
    for filename, expected in pins['source_sha256'].items():
        assert hashlib.sha256((policy / filename).read_bytes()).hexdigest() == expected, filename
    compiled = {}
    for name, directory, contract in [('treasury', ROOT / 'treasury', 'Treasury'),
                                       ('sponsorship', ROOT / 'examples/sponsorship', 'Sponsorship')]:
        manifest = tomllib.loads((directory / 'fe.toml').read_text())
        assert set(manifest['dependencies']) == {'capabilities'}
        assert (directory / manifest['dependencies']['capabilities']['path']).resolve() == policy.resolve()
        metadata = json.loads((directory / 'out' / f'{contract}.metadata.json').read_text())
        assert {i['name'] for i in metadata['settings']['ingots']} == {manifest['ingot']['name'], pins['name']}
        library = [i for i in metadata['settings']['ingots'] if i['name'] == pins['name']]
        assert len(library) == 1 and library[0]['version'] == pins['version']
        sources = {key: value for key, value in metadata['sources'].items() if key.startswith(pins['name'] + '/')}
        assert set(sources) == {pins['name'] + '/' + filename for filename in pins['source_sha256'] if filename.endswith('.fe')}
        for key, value in sources.items():
            filename = key.removeprefix(pins['name'] + '/')
            assert value['content'] == (policy / filename).read_text(), (name, key)
        compiled[name] = sources
    assert compiled['treasury'] == compiled['sponsorship'], 'Consumers compiled different policy contents'
    return {'schema_version': 1, 'package': pins['name'], 'version': pins['version'],
            'source_introduced_at': pins['source_introduced_at'], 'source_sha256': pins['source_sha256'],
            'compiler_keccak256': {key: value['keccak256'] for key, value in compiled['treasury'].items()},
            'consumers': {'treasury': '../policy', 'sponsorship': '../../policy'}}


def main(record_dir=None):
    fe = Path(os.environ.get('FE_BIN', ROOT / '.tools/bin/fe')).resolve()
    def run(*command):
        print('+ ' + ' '.join(map(str, command)), flush=True)
        subprocess.run(list(map(str, command)), cwd=ROOT, check=True)
    boundary = [sys.executable, 'scripts/verify-boundaries.py']
    if record_dir:
        boundary.extend(['--record', str(Path(record_dir) / 'boundaries.json')])
    run(*boundary)  # Verifies pinned compiler digest/version before any builds.
    run(sys.executable, 'scripts/verify-spending.py')
    run(fe, 'check', 'examples/sponsorship')
    run(fe, 'fmt', 'examples/sponsorship', '--check')
    run(fe, 'check', 'tests/runtime/sponsorship')
    run(fe, 'fmt', 'tests/runtime/sponsorship', '--check')
    run(fe, 'test', 'tests/runtime/sponsorship', '--backend', 'sonatina', '-O', '1')
    for directory, contract in [('examples/sponsorship', 'Sponsorship'), ('tests/runtime/sponsorship', 'Receiver')]:
        run(fe, 'build', directory, '--contract', contract, '--backend', 'sonatina', '--profile', 'release',
            '-O', '1', '--emit', 'bytecode,runtime-bytecode,abi,metadata')
    actual = json.loads((ROOT / 'examples/sponsorship/out/Sponsorship.abi.json').read_text())
    expected = json.loads((ROOT / 'examples/sponsorship/abi.json').read_text())
    assert actual == expected, 'Sponsorship ABI changed'
    package = shared_policy()
    if record_dir:
        output = ROOT / record_dir
        output.mkdir(parents=True, exist_ok=True)
        (output / 'shared-policy.json').write_text(json.dumps(package, indent=2) + '\n')
    print('PASS both consumers compiled the identical pinned policy source contents', flush=True)
    command = [sys.executable, 'scripts/anvil-sponsorship.py']
    if record_dir:
        command.extend(['--record', str(Path(record_dir) / 'anvil-sponsorship.json')])
    run(*command)
    print('PASS Phase 4 reuse verification', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record-dir', help='Optional evidence directory relative to repository root')
    main(parser.parse_args().record_dir)
