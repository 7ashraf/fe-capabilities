#!/usr/bin/env python3
"""Verify external positive controls and intended compile-time boundary failures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main(record=None):
    fe = Path(os.environ.get('FE_BIN', ROOT / '.tools/bin/fe')).resolve()
    pins = json.loads((ROOT / 'toolchain.json').read_text())
    system = {'Darwin': 'mac', 'Linux': 'linux'}[platform.system()]
    arch = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'amd64'}[platform.machine()]
    assert 'sha256:' + hashlib.sha256(fe.read_bytes()).hexdigest() == pins['fe']['assets'][f'fe_{system}_{arch}']['digest']
    version = subprocess.check_output([str(fe), '--version'], text=True).strip()
    assert version == 'fe 26.5.0 (3dab95f)'
    fixtures = json.loads((ROOT / 'tests/vectors/boundaries-v1.json').read_text())
    assert fixtures['schema_version'] == 1
    results = []
    def normalize(path):
        return re.sub(r'\s+', '', path.read_text()).replace(',)', ')')
    for case in fixtures['cases']:
        positive = ROOT / case['positive']
        negative = ROOT / case['negative']
        allowed = normalize(positive / 'src/lib.fe')
        rejected = normalize(negative / 'src/lib.fe')
        assert allowed.count(case['allowed_declaration']) == 1
        assert allowed.replace(case['allowed_declaration'], case['rejected_declaration']) == rejected
        for directory in [positive, negative]:
            subprocess.run([str(fe), 'fmt', str(directory), '--check'], cwd=ROOT, check=True)
        subprocess.run([str(fe), 'check', str(positive)], cwd=ROOT, check=True)
        subprocess.run([str(fe), 'test', str(positive), '--backend', 'sonatina', '-O', '1'], cwd=ROOT, check=True)
        failure = subprocess.run([str(fe), 'check', '--color', 'never', str(negative)], cwd=ROOT,
                                 capture_output=True, text=True)
        diagnostic = failure.stdout + failure.stderr
        assert failure.returncode == 1, f'{case["name"]}: unexpected compiler outcome {failure.returncode}: {diagnostic}'
        assert diagnostic.count('error[') == 1 and f'error[{case["category"]}]' in diagnostic, diagnostic
        assert case['substring'] in diagnostic, diagnostic
        print(diagnostic, end='', flush=True)
        print(f'PASS {case["name"]}: positive runtime control, intended negative diagnostic, one access change', flush=True)
        results.append({'name': case['name'], 'positive_test': 'passed', 'negative_exit': failure.returncode,
                        'diagnostic': diagnostic, 'positive_sha256': hashlib.sha256((positive / 'src/lib.fe').read_bytes()).hexdigest(),
                        'negative_sha256': hashlib.sha256((negative / 'src/lib.fe').read_bytes()).hexdigest()})
    if record:
        Path(record).parent.mkdir(parents=True, exist_ok=True)
        Path(record).write_text(json.dumps({'schema_version': 1, 'compiler': version, 'cases': results}, indent=2) + '\n')
    print(f'PASS {len(results)} external access-boundary pairs', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', help='Optional diagnostic evidence JSON path')
    main(parser.parse_args().record)
