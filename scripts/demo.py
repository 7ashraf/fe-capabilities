#!/usr/bin/env python3
"""Short, asserted local ETH treasury demonstration; always stops its Anvil chain."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess

from local_chain import LocalChain, cast

ROOT = Path(__file__).resolve().parent.parent


def word(value):
    return f'{int(value, 16) if isinstance(value, str) and value.startswith("0x") else int(value):064x}'


def data(signature, *args):
    return cast('calldata', signature, *map(str, args))


def words(encoded):
    assert encoded.startswith('0x') and (len(encoded) - 2) % 64 == 0
    return [int(encoded[i:i + 64], 16) for i in range(2, len(encoded), 64)]


def run(record=None):
    fe = Path(os.environ.get('FE_BIN', ROOT / '.tools/bin/fe')).resolve()
    pins = json.loads((ROOT / 'toolchain.json').read_text())
    system = {'Darwin': 'mac', 'Linux': 'linux'}[platform.system()]
    arch = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'amd64'}[platform.machine()]
    assert 'sha256:' + hashlib.sha256(fe.read_bytes()).hexdigest() == pins['fe']['assets'][f'fe_{system}_{arch}']['digest']
    assert subprocess.check_output([str(fe), '--version'], text=True).strip() == 'fe 26.5.0 (3dab95f)'
    for directory, contract in [('treasury', 'Treasury'), ('tests/runtime/spending', 'CallbackRecipient')]:
        result = subprocess.run([str(fe), 'build', directory, '--contract', contract, '--backend', 'sonatina',
                                 '--profile', 'release', '-O', '1', '--emit', 'bytecode,runtime-bytecode,abi,metadata'],
                                cwd=ROOT, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
    print('Local Anvil Osaka demo — test wei only', flush=True)
    steps = []
    def note(message):
        steps.append(message)
        print(f'{len(steps)}. {message}', flush=True)
    with LocalChain(ROOT) as chain:
        owner, delegate, recipient, outsider = chain.accounts[:4]
        artifacts = [ROOT / 'treasury/out/Treasury.bin', ROOT / 'tests/runtime/spending/out/CallbackRecipient.bin']
        def deploy(label, file, arguments=''):
            receipt = chain.send(label, data='0x' + file.read_text().strip().removeprefix('0x') + arguments)
            address = receipt['contractAddress']
            assert chain.rpc('eth_getCode', [address, 'latest']) != '0x'
            return address
        def read(address, signature, *args):
            return words(chain.call({'to': address, 'data': data(signature, *args)}))
        def balance(address):
            return int(chain.rpc('eth_getBalance', [address, 'latest']), 16)
        def expiry():
            return int(chain.rpc('eth_getBlockByNumber', ['latest', False])['timestamp'], 16) + 3600
        target = deploy('deploy_treasury', artifacts[0], word(owner))
        chain.send('deposit_100', to=target, data=data('deposit()'), value=100)
        assert balance(target) == 100
        note('Funded the treasury with 100 wei.')
        chain.send('create_grant_1', to=target, data=data('createGrant(address,address,uint256,uint256)', delegate, recipient, 10, expiry()))
        assert read(target, 'getGrant(uint256)', 1)[3:5] == [10, 0]
        note('Owner granted a delegate a 10-wei cap for one fixed recipient.')
        recipient_start = balance(recipient)
        chain.send('allowed_spend_4', to=target, data=data('spend(uint256,uint256)', 1, 4), sender=delegate)
        assert read(target, 'getGrant(uint256)', 1)[4] == 4 and balance(target) == 96
        assert balance(recipient) == recipient_start + 4
        note('Allowed payment: recipient received 4 wei; recorded spent is 4.')
        def reject(label, amount, sender, signature, arguments):
            before = (read(target, 'getGrant(uint256)', 1), read(target, 'nextGrantId()'), balance(target), balance(recipient))
            request = {'from': sender, 'to': target, 'data': data('spend(uint256,uint256)', 1, amount)}
            expected = cast('sig', signature) + ''.join(word(x) for x in arguments)
            chain.expect_error(label, request, expected)
            chain.send(label, to=target, data=request['data'], sender=sender, success=False)
            assert (read(target, 'getGrant(uint256)', 1), read(target, 'nextGrantId()'), balance(target), balance(recipient)) == before
        reject('overspend', 7, delegate, 'CapExceeded(uint256,uint256)', [6, 7])
        note('Rejected overspend: requested 7 wei with only 6 remaining.')
        reject('unapproved_account', 1, outsider, 'Unauthorized()', [])
        note('Rejected an unapproved account with Unauthorized().')
        chain.send('revoke', to=target, data=data('revoke(uint256)', 1))
        reject('revoked_grant', 1, delegate, 'InactiveGrant(uint256)', [1])
        note('Owner revoked the grant; the old delegate can no longer spend.')
        hostile = deploy('deploy_callback_recipient', artifacts[1])
        guarded = deploy('deploy_callback_treasury', artifacts[0], word(hostile))
        chain.send('create_callback_grant', to=hostile, data=data('create(address,uint256,uint256)', guarded, 25, expiry()))
        chain.send('fund_callback', to=guarded, data=data('deposit()'), value=20)
        chain.send('configure_reentry', to=hostile, data=data('configure(address,uint256,uint256)', guarded, 1, 2))
        chain.send('callback_payment', to=hostile, data=data('execute(address,uint256,uint256,bool)', guarded, 1, 3, 'false'))
        assert read(hostile, 'stats()')[:2] == [1, 1]
        assert read(guarded, 'getGrant(uint256)', 1)[4] == 3 and balance(guarded) == 17 and balance(hostile) == 3
        note('Blocked authorized recipient reentry with Reentrant(); outer payment committed once.')
        chain.send('disable_reentry', to=hostile, data=data('configure(address,uint256,uint256)', guarded, 1, 0))
        batch = chain.send('two_valid_payments', to=hostile, data=data('execute(address,uint256,uint256,bool)', guarded, 1, 2, 'true'))
        assert read(guarded, 'getGrant(uint256)', 1)[4] == 7 and balance(guarded) == 13 and balance(hostile) == 7
        assert read(hostile, 'stats()')[:2] == [1, 3]
        assert len([log for log in batch['logs'] if log['address'].lower() == guarded.lower()]) == 2
        note('Two later valid payments succeeded in one transaction; spent is 7 and balance is 13.')
        evidence = {'schema_version': 1, 'fork': 'osaka', 'tools': chain.versions, 'steps': steps,
                    'bytecode_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts},
                    'transactions': chain.receipts, 'expected_errors': chain.errors,
                    'final': {'ordinary_treasury_wei': str(balance(target)), 'ordinary_spent_wei': str(read(target, 'getGrant(uint256)', 1)[4]),
                              'callback_treasury_wei': str(balance(guarded)), 'callback_spent_wei': str(read(guarded, 'getGrant(uint256)', 1)[4])}}
        if record:
            Path(record).parent.mkdir(parents=True, exist_ok=True)
            Path(record).write_text(json.dumps(evidence, indent=2) + '\n')
    print('PASS demo; temporary chain stopped.', flush=True)
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', help='Optional raw demo evidence JSON path')
    run(parser.parse_args().record)
