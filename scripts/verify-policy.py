#!/usr/bin/env python3
"""Compile explicit policy vectors into Fe tests and run them on both backends."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
ERRORS = {'InvalidOwner', 'Unauthorized', 'UnknownGrant', 'InactiveGrant', 'InvalidAddress',
          'InvalidAmount', 'InvalidExpiry', 'GrantIdExhausted', 'Expired',
          'InvalidGrantState', 'CapExceeded', 'InsufficientBalance'}
MAX = 2**256 - 1


def number(value, address=False):
    assert isinstance(value, str) and re.fullmatch(r'0|[1-9][0-9]*', value), value
    assert int(value) <= (2**160 - 1 if address else MAX), value
    return value


def boolean(value):
    assert type(value) is bool, value
    return str(value).lower()


def grant_assertions(name, data):
    return '\n'.join([
        f'assert!({name}.exists == {boolean(data["exists"])})',
        f'assert!({name}.active == {boolean(data["active"])})',
        f'assert!({name}.delegate == Address::new({number(data["delegate"], True)}))',
        f'assert!({name}.recipient == Address::new({number(data["recipient"], True)}))',
        f'assert!({name}.cap == wei({number(data["cap"])}))',
        f'assert!({name}.spent == wei({number(data["spent"])}))',
        f'assert!({name}.expires_at == Timestamp::from_seconds({number(data["expires_at"])}))',
    ])


def emit(vector):
    name, kind, data, expected = (vector[key] for key in ['name', 'kind', 'input', 'expected'])
    assert re.fullmatch('[a-z][a-z0-9_]*', name), name
    assert kind in {'spend', 'create', 'revoke', 'owner'}, kind
    for key, value in data.items():
        if key in {'exists', 'active'}:
            boolean(value)
        else:
            number(value, key in {'owner', 'caller', 'delegate', 'recipient'})
    source = f'''#[test]
fn {name}() {{
    let id = GrantId::from_word({data['id']})
    let next_id = GrantId::from_word({data['next_id']})
    let owner = Address::new({data['owner']})
    let amount = wei({data['amount']})
    let context = PolicyContext::new(
        caller: Address::new({data['caller']}),
        now: Timestamp::from_seconds({data['now']}),
        available: wei({data['available']}),
    )
    let grant = Grant {{
        exists: {boolean(data['exists'])}, delegate: Address::new({data['delegate']}),
        recipient: Address::new({data['recipient']}), cap: wei({data['cap']}),
        spent: wei({data['spent']}), expires_at: Timestamp::from_seconds({data['expires_at']}),
        active: {boolean(data['active'])},
    }}
    let request = GrantRequest {{
        delegate: Address::new({data['delegate']}), recipient: Address::new({data['recipient']}),
        cap: wei({data['cap']}), expires_at: Timestamp::from_seconds({data['expires_at']}),
    }}
    with (context) {{
'''
    expression = {
        'spend': 'evaluate_spend(id, grant, amount)',
        'create': 'evaluate_create(owner, next_id, request)',
        'revoke': 'evaluate_revoke(owner, id, grant)',
        'owner': 'validate_owner(owner)',
    }[kind]
    if 'error' in expected:
        assert set(expected) == {'error'} and expected['error'] in ERRORS, expected
        arms = f'Err(PolicyError::{expected["error"]}) => {{}},\n_ => assert!(false),'
    else:
        if kind == 'spend':
            assert set(expected) == {'recipient', 'amount', 'new_spent'}, expected
            checks = f'''assert!(decision.recipient == Address::new({number(expected['recipient'], True)}))
assert!(decision.amount == wei({number(expected['amount'])}))
assert!(decision.new_spent == wei({number(expected['new_spent'])}))'''
        elif kind == 'create':
            assert set(expected) == {'id', 'next_id', 'delegate', 'recipient', 'cap', 'spent', 'expires_at', 'exists', 'active'}, expected
            checks = f'''assert!(decision.id.word() == {number(expected['id'])})
assert!(decision.next_id.word() == {number(expected['next_id'])})
''' + grant_assertions('decision.grant', expected)
        elif kind == 'revoke':
            assert set(expected) == {'changed'}, expected
            checks = f'assert!(decision == {boolean(expected["changed"])})'
        else:
            assert expected == {'ok': True}, expected
            checks = ''
        arms = f'Ok(decision) => {{ {checks} }},\nErr(_) => assert!(false),'
    source += f'match {expression} {{\n{arms}\n}}\n}}\n'
    # Expected post-state is the original literal fixture on both success and error.
    # No host-language policy or arithmetic oracle computes expected outcomes.
    source += grant_assertions('grant', data) + '\n'
    source += f'''assert!(context.caller == Address::new({data['caller']}))
assert!(context.now == Timestamp::from_seconds({data['now']}))
assert!(context.available == wei({data['available']}))
assert!(request.delegate == Address::new({data['delegate']}))
assert!(request.recipient == Address::new({data['recipient']}))
assert!(request.cap == wei({data['cap']}))
assert!(request.expires_at == Timestamp::from_seconds({data['expires_at']}))
assert!(id.word() == {data['id']})
assert!(next_id.word() == {data['next_id']})
}}\n'''
    return source


def main():
    fe = Path(os.environ.get('FE_BIN', ROOT / '.tools/bin/fe')).resolve()
    manifest = json.loads((ROOT / 'toolchain.json').read_text())
    system = {'Darwin': 'mac', 'Linux': 'linux'}[platform.system()]
    arch = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'amd64'}[platform.machine()]
    expected = manifest['fe']['assets'][f'fe_{system}_{arch}']['digest']
    assert 'sha256:' + hashlib.sha256(fe.read_bytes()).hexdigest() == expected, 'Compiler checksum mismatch'
    assert subprocess.check_output([str(fe), '--version'], text=True).strip() == 'fe 26.5.0 (3dab95f)'
    corpus = json.loads((ROOT / 'tests/vectors/policy-v1.json').read_text())
    assert corpus['schema_version'] == 1
    vectors = corpus['vectors']
    assert len({v['name'] for v in vectors}) == len(vectors), 'Duplicate vector name'
    target = ROOT / '.tools/policy-vectors'
    (target / 'src').mkdir(parents=True, exist_ok=True)
    (target / 'fe.toml').write_text('[ingot]\nname = "policy_vectors"\nversion = "0.1.0"\n'
                                  '\n[dependencies]\ncapabilities = { path = ' + json.dumps('../../policy') + ' }\n')
    (target / 'src/lib.fe').write_text('use capabilities::{GrantId, Grant, GrantRequest, PolicyContext, PolicyError, '
                                      'evaluate_spend, evaluate_create, evaluate_revoke, validate_owner}\n'
                                      'use std::evm::{Address, Timestamp, wei}\n\n' + '\n'.join(map(emit, vectors)))
    def run(*args):
        print('+ fe ' + ' '.join(map(str, args)), flush=True)
        subprocess.run([str(fe), *map(str, args)], cwd=ROOT, check=True)
    run('check', 'policy')
    run('fmt', 'policy', '--check')
    run('fmt', 'tests/compile_fail/policy_units_allowed', '--check')
    run('fmt', 'tests/compile_fail/policy_units_rejected', '--check')
    run('check', 'tests/compile_fail/policy_units_allowed')
    def normalized(path):
        source = re.sub(r'\s+', '', (ROOT / path).read_text())
        return source.replace(',)', ')')
    allowed = normalized('tests/compile_fail/policy_units_allowed/src/lib.fe')
    rejected = normalized('tests/compile_fail/policy_units_rejected/src/lib.fe')
    assert allowed.replace('amount:wei(7)', 'amount:Timestamp::from_seconds(7)') == rejected
    negative = subprocess.run([str(fe), 'check', '--color', 'never',
                               'tests/compile_fail/policy_units_rejected'],
                              cwd=ROOT, capture_output=True, text=True)
    diagnostic = negative.stdout + negative.stderr
    assert negative.returncode == 1, diagnostic
    assert diagnostic.count('error[') == 1 and 'error[8-0000]' in diagnostic, diagnostic
    assert 'expected `Wei`, but `Timestamp` is given' in diagnostic, diagnostic
    print(diagnostic, end='', flush=True)
    print('PASS timestamp rejected as payment amount for the intended type mismatch', flush=True)
    run('check', target)
    for backend in ['sonatina', 'native']:
        run('test', target, '--backend', backend, '-O', '1')
    print(f'PASS {len(vectors)} explicit policy vectors on each backend, including unchanged inputs')


if __name__ == '__main__':
    main()
