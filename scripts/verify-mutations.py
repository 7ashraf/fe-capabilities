#!/usr/bin/env python3
"""Prove four seeded defects are rejected by existing runtime tests in isolated copies."""
import argparse
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(fe, root, *arguments):
    result = subprocess.run([str(fe), *map(str, arguments)], cwd=root,
                            capture_output=True, text=True, timeout=60)
    return {'command': ['fe', *map(str, arguments)], 'exit': result.returncode,
            'output': (result.stdout + result.stderr).replace(str(root), '$CHECKOUT')}


def require_test(result, name, passed):
    assert 'error[' not in result['output'], result
    expected = 'ok. 1 passed; 0 failed' if passed else 'FAILED. 0 passed; 1 failed'
    assert result['exit'] == (0 if passed else 1), result
    assert 'test result: ' + expected in result['output'], result
    status = 'PASS' if passed else 'FAIL'
    assert re.search(r'\b' + status + r'\b[^\n]*\b' + re.escape(name) + r'\b', result['output']), result


def prepare_case(root, case, emitter, corpus):
    if case['kind'] == 'runtime':
        return 'tests/runtime/spending'
    vector = next(v for v in corpus['vectors'] if v['name'] == case['test'])
    target = root / '.tools/mutation-vectors'
    (target / 'src').mkdir(parents=True)
    (target / 'fe.toml').write_text('[ingot]\nname = "mutation_vectors"\nversion = "0.1.0"\n'
                                  '\n[dependencies]\ncapabilities = { path = "../../policy" }\n')
    imports = ('use capabilities::{GrantId, Grant, GrantRequest, PolicyContext, PolicyError, '
               'evaluate_spend, evaluate_create, evaluate_revoke, validate_owner}\n'
               'use std::evm::{Address, Timestamp, wei}\n')
    (target / 'src/lib.fe').write_text(imports + emitter(vector))
    return '.tools/mutation-vectors'


def main(record=None):
    fe = Path(os.environ.get('FE_BIN', ROOT / '.tools/bin/fe')).resolve()
    pins = json.loads((ROOT / 'toolchain.json').read_text())
    system = {'Darwin': 'mac', 'Linux': 'linux'}[platform.system()]
    arch = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'amd64'}[platform.machine()]
    assert 'sha256:' + digest(fe) == pins['fe']['assets'][f'fe_{system}_{arch}']['digest']
    version = subprocess.check_output([str(fe), '--version'], text=True).strip()
    assert version == 'fe 26.5.0 (3dab95f)'
    for filename, expected in pins['policy_package']['source_sha256'].items():
        assert digest(ROOT / 'policy' / filename) == expected
    recipes = json.loads((ROOT / 'tests/vectors/mutations-v1.json').read_text())
    assert recipes['schema_version'] == 1
    required = {'remove_cap_check', 'allow_expiry_equality', 'remove_delegate_check', 'forget_spend_unlock'}
    assert len(recipes['cases']) == 4 and {case['name'] for case in recipes['cases']} == required
    for case in recipes['cases']:
        assert case['file'] in {'policy/src/policy.fe', 'treasury/src/lib.fe'}
        assert case['kind'] in {'policy', 'runtime'}
    corpus = json.loads((ROOT / 'tests/vectors/policy-v1.json').read_text())
    spec = importlib.util.spec_from_file_location('policy_vector_renderer', ROOT / 'scripts/verify-policy.py')
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    original = {case['file']: digest(ROOT / case['file']) for case in recipes['cases']}
    results = []
    for case in recipes['cases']:
        with tempfile.TemporaryDirectory(prefix='fe-defect-' + case['name'] + '-') as directory:
            checkout = Path(directory)
            shutil.copytree(ROOT, checkout, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('.git', '.tools', 'out', 'cache', '__pycache__'))
            suite = prepare_case(checkout, case, renderer.emit, corpus)
            arguments = ['test', '--color', 'never', suite, '--backend', 'sonatina', '-O', '1', '--filter', case['test']]
            test_sha256 = digest(checkout / suite / 'src/lib.fe')
            baseline_check = command(fe, checkout, 'check', suite)
            assert baseline_check['exit'] == 0, baseline_check
            baseline = command(fe, checkout, *arguments)
            require_test(baseline, case['test'], passed=True)
            path = checkout / case['file']
            before = path.read_text()
            assert before.count(case['before']) == 1, f'{case["name"]}: stale or ambiguous mutation anchor'
            after = before.replace(case['before'], case['after'], 1)
            path.write_text(after)
            mutant_check = command(fe, checkout, 'check', suite)
            assert mutant_check['exit'] == 0, f'Mutant does not type-check; not a runtime detection: {mutant_check}'
            failure = command(fe, checkout, *arguments)
            require_test(failure, case['test'], passed=False)
            assert digest(checkout / suite / 'src/lib.fe') == test_sha256, 'Mutation changed the test oracle'
            patch = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                               fromfile='baseline/' + case['file'], tofile='mutant/' + case['file']))
            results.append({'name': case['name'], 'test': case['test'], 'detected': True,
                            'file': case['file'], 'test_sha256': test_sha256, 'baseline_sha256': hashlib.sha256(before.encode()).hexdigest(),
                            'mutant_sha256': hashlib.sha256(after.encode()).hexdigest(), 'patch': patch,
                            'baseline_check': baseline_check, 'baseline_test': baseline,
                            'mutant_check': mutant_check, 'mutant_test': failure})
            print(f'PASS {case["name"]}: baseline passes; mutant compiles; existing test fails at runtime', flush=True)
    assert all(digest(ROOT / filename) == expected for filename, expected in original.items()), 'Working tree source changed'
    evidence = {'schema_version': 1, 'compiler': version, 'compiler_sha256': digest(fe),
                'backend': 'sonatina', 'optimization': '1', 'source_sha256': original,
                'test_inputs_sha256': {name: digest(ROOT / name) for name in [
                    'tests/vectors/policy-v1.json', 'tests/vectors/mutations-v1.json',
                    'scripts/verify-policy.py', 'scripts/verify-mutations.py', 'tests/runtime/spending/src/lib.fe']},
                'cases': results, 'detected': len(results), 'survived': 0}
    if record:
        Path(record).parent.mkdir(parents=True, exist_ok=True)
        Path(record).write_text(json.dumps(evidence, indent=2) + '\n')
    print(f'PASS {len(results)}/{len(recipes["cases"])} seeded defects detected; original sources unchanged', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', help='Optional mutation evidence JSON path')
    main(parser.parse_args().record)
