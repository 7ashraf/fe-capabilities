#!/usr/bin/env python3
"""Package the current clean branch and complete history into a local Git bundle."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def git(*arguments):
    return subprocess.check_output(['git', *arguments], cwd=ROOT, text=True).strip()


def main():
    if git('status', '--porcelain'):
        raise SystemExit('Commit all source/handoff changes before packaging; the bundle represents committed history.')
    branch = git('branch', '--show-current')
    if not branch:
        raise SystemExit('Package from a named branch to preserve a normal clone checkout.')
    pins = json.loads((ROOT / 'toolchain.json').read_text())
    files = pins['handoff']['frozen_source_sha256']
    for filename, expected in files.items():
        if hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() != expected:
            raise SystemExit(f'Frozen input changed: {filename}')
    output = ROOT / '.tools'
    output.mkdir(exist_ok=True)
    bundle = output / 'fe-capabilities-handoff.bundle'
    subprocess.run(['git', 'bundle', 'create', str(bundle), branch, 'HEAD'], cwd=ROOT, check=True)
    subprocess.run(['git', 'bundle', 'verify', str(bundle)], cwd=ROOT, check=True)
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    bundle.with_suffix('.bundle.sha256').write_text(digest + '  ' + bundle.name + '\n')
    manifest = {'schema_version': 1, 'version': pins['handoff']['version'],
                'prepared_on': pins['handoff']['prepared_on'], 'commit': git('rev-parse', 'HEAD'),
                'branch': branch, 'commit_count': int(git('rev-list', '--count', 'HEAD')),
                'bundle': bundle.name, 'bundle_sha256': digest,
                'fe': pins['fe']['version'], 'fe_commit': pins['fe']['commit'],
                'foundry': pins['foundry'], 'license': 'MIT',
                'verification_record': 'docs/evidence/handoff.json',
                'independent_review': pins['independent_review'], 'frozen_source_sha256': files}
    (output / 'handoff-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Local handoff: {bundle}')
    print(f'Commit: {manifest["commit"]}')
    print(f'SHA-256: {digest}')
    print('Independent feedback: pending. Bundle is a local source/history artifact.')


if __name__ == '__main__':
    main()
