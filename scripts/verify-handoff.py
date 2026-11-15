#!/usr/bin/env python3
"""Verify the frozen local handoff; retain independent review as outstanding."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from doctor import inspect

ROOT = Path(__file__).resolve().parent.parent


def main(record=None):
    environment = inspect()
    pins = json.loads((ROOT / 'toolchain.json').read_text())
    release = pins['handoff']
    for filename in ['LICENSE', 'NOTICE.md', 'licenses/Fe-APACHE-2.0.txt',
                     'docs/setup.md', 'docs/handoff.md', 'docs/reviewer-feedback.md']:
        if not (ROOT / filename).is_file():
            raise SystemExit(f'Missing handoff file: {filename}')
    for filename, expected in release['frozen_source_sha256'].items():
        if hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() != expected:
            raise SystemExit(f'Frozen input changed: {filename}. Update the spec, evidence, and release pins deliberately.')
    command = [sys.executable, 'scripts/verify-review.py']
    print('+ ' + ' '.join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)
    report = {'schema_version': 1, 'prepared_on': release['prepared_on'], 'version': release['version'],
              'environment': environment, 'license': 'MIT', 'technical_checks': 'passed',
              'command': ['python3', 'scripts/verify-review.py'],
              'frozen_source_sha256': release['frozen_source_sha256'],
              'independent_review': pins['independent_review']}
    if record:
        Path(record).parent.mkdir(parents=True, exist_ok=True)
        Path(record).write_text(json.dumps(report, indent=2) + '\n')
    print('PASS Phase 6 local handoff verification; independent developer feedback remains pending.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', help='Optional local handoff verification record JSON path')
    main(parser.parse_args().record)
