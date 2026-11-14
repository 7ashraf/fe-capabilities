#!/usr/bin/env python3
"""Close review gaps: mined expiry equality and authorized cross-grant callbacks."""
import argparse
import hashlib
import json
from pathlib import Path

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
    with LocalChain(ROOT) as chain:
        owner, delegate, recipient = chain.accounts[:3]
        treasury = ROOT / 'treasury/out/Treasury.bin'
        callback = ROOT / 'tests/runtime/spending/out/CallbackRecipient.bin'
        def deploy(label, file, arguments=''):
            code = '0x' + file.read_text().strip().removeprefix('0x') + arguments
            result = chain.send(label, data=code)
            assert chain.rpc('eth_getCode', [result['contractAddress'], 'latest']) != '0x'
            return result['contractAddress']
        def read(address, signature, *args):
            return words(chain.call({'to': address, 'data': data(signature, *args)}))
        def balance(address):
            return int(chain.rpc('eth_getBalance', [address, 'latest']), 16)
        def now():
            return int(chain.rpc('eth_getBlockByNumber', ['latest', False])['timestamp'], 16)
        def header(receipt):
            result = chain.rpc('eth_getBlockByNumber', [receipt['blockNumber'], False])
            return {'number': result['number'], 'timestamp': str(int(result['timestamp'], 16)), 'hash': result['hash']}
        target = deploy('deploy_expiry_control', treasury, word(owner))
        expiry = now() + 3600
        chain.send('create_expiry_grant', to=target, data=data('createGrant(address,address,uint256,uint256)', delegate, recipient, 25, expiry))
        chain.send('fund_expiry_control', to=target, data=data('deposit()'), value=100)
        initial_recipient = balance(recipient)
        chain.rpc('evm_setNextBlockTimestamp', [expiry - 1])
        before = chain.send('mined_before_expiry', to=target, data=data('spend(uint256,uint256)', 1, 1), sender=delegate)
        before_block = header(before)
        assert int(before_block['timestamp']) == expiry - 1
        baseline = (read(target, 'getGrant(uint256)', 1), balance(target), balance(recipient))
        assert baseline[0][4] == 1 and baseline[1] == 99 and baseline[2] == initial_recipient + 1
        chain.rpc('evm_setNextBlockTimestamp', [expiry])
        equality = chain.send('mined_equal_expiry', to=target, data=data('spend(uint256,uint256)', 1, 1), sender=delegate, success=False)
        equal_block = header(equality)
        assert int(equal_block['timestamp']) == expiry
        chain.expect_error('equal_expiry_error_bytes', {'from': delegate, 'to': target, 'data': data('spend(uint256,uint256)', 1, 1)},
                           cast('sig', 'Expired(uint256,uint256)') + word(expiry) + word(expiry))
        assert (read(target, 'getGrant(uint256)', 1), balance(target), balance(recipient)) == baseline
        chain.rpc('evm_setNextBlockTimestamp', [expiry + 1])
        after = chain.send('mined_after_expiry', to=target, data=data('spend(uint256,uint256)', 1, 1), sender=delegate, success=False)
        after_block = header(after)
        assert int(after_block['timestamp']) == expiry + 1
        assert (read(target, 'getGrant(uint256)', 1), balance(target), balance(recipient)) == baseline
        fixture = deploy('deploy_cross_grant_recipient', callback)
        guarded = deploy('deploy_shared_lock', treasury, word(fixture))
        for grant_id in [1, 2]:
            chain.send(f'create_cross_grant_{grant_id}', to=fixture,
                       data=data('create(address,uint256,uint256)', guarded, 25, now() + 3600))
        chain.send('fund_shared_lock', to=guarded, data=data('deposit()'), value=100)
        chain.send('configure_nested_grant_2', to=fixture,
                   data=data('configure(address,uint256,uint256)', guarded, 2, 2))
        outer = chain.send('grant_1_attempts_nested_grant_2', to=fixture,
                           data=data('execute(address,uint256,uint256,bool)', guarded, 1, 7, 'false'))
        assert read(fixture, 'stats()') == [1, 1, 0, 0]  # Exact Reentrant was checked inside the real callback.
        assert read(guarded, 'getGrant(uint256)', 1)[4] == 7
        assert read(guarded, 'getGrant(uint256)', 2)[4] == 0
        assert read(guarded, 'getGrant(uint256)', 2)[-1] == 1
        assert read(guarded, 'nextGrantId()') == [3]
        assert balance(guarded) == 93 and balance(fixture) == 7
        logs = [log for log in outer['logs'] if log['address'].lower() == guarded.lower()]
        assert len(logs) == 1 and logs[0]['topics'][1] == '0x' + word(1)
        chain.send('disable_cross_grant_callback', to=fixture,
                   data=data('configure(address,uint256,uint256)', guarded, 2, 0))
        sequential = chain.send('later_two_grant_2_payments', to=fixture,
                                data=data('execute(address,uint256,uint256,bool)', guarded, 2, 2, 'true'))
        assert read(guarded, 'getGrant(uint256)', 1)[4] == 7
        assert read(guarded, 'getGrant(uint256)', 2)[4] == 4
        assert balance(guarded) == 89 and balance(fixture) == 11
        logs = [log for log in sequential['logs'] if log['address'].lower() == guarded.lower()]
        assert len(logs) == 2
        for log, spent in zip(logs, [2, 4]):
            assert log['topics'] == [cast('keccak', 'Spent(uint256,address,address,uint256,uint256)'),
                                     '0x' + word(2), '0x' + word(fixture), '0x' + word(fixture)]
            assert log['data'] == '0x' + word(2) + word(spent)
        evidence = {'schema_version': 1, 'fork': 'osaka', 'tools': chain.versions,
                    'bytecode_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [treasury, callback]},
                    'transactions': chain.receipts, 'expected_errors': chain.errors,
                    'expiry': str(expiry), 'expiry_blocks': [before_block, equal_block, after_block],
                    'cross_grant': {'treasury': guarded, 'recipient': fixture, 'nested_error': 'Reentrant()',
                                    'final_grant_1_spent': str(read(guarded, 'getGrant(uint256)', 1)[4]),
                                    'final_grant_2_spent': str(read(guarded, 'getGrant(uint256)', 2)[4]),
                                    'final_balance': str(balance(guarded))}}
        if record:
            Path(record).parent.mkdir(parents=True, exist_ok=True)
            Path(record).write_text(json.dumps(evidence, indent=2) + '\n')
        print(f'PASS review: {len(chain.receipts)} transactions; mined expiry-1/equality/+1; shared cross-grant lock and later payments')
        return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', help='Optional raw review evidence JSON path')
    run(parser.parse_args().record)
