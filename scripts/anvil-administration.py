#!/usr/bin/env python3
"""Check real treasury administration transactions, full records, and event bytes."""
import argparse
import hashlib
import json
from pathlib import Path

from local_chain import LocalChain, cast

ROOT = Path(__file__).resolve().parent.parent
CREATE = 'createGrant(address,address,uint256,uint256)'
MAX = 2**256 - 1
ZERO = '0x' + '00' * 20


def word(number):
    return f'{int(number, 16) if isinstance(number, str) and number.startswith("0x") else int(number):064x}'


def calldata(signature, *args):
    return cast('calldata', signature, *map(str, args))


def run(record=None):
    with LocalChain(ROOT) as chain:
        owner, stranger, delegate, recipient, delegate2, recipient2 = chain.accounts[:6]
        artifacts = ROOT / 'treasury/out'
        bytecode = (artifacts / 'Treasury.bin').read_text().strip().removeprefix('0x')
        owner_argument = word(owner)
        invalid_data = '0x' + bytecode + word(ZERO)
        chain.expect_error('zero_owner_constructor', {'from': owner, 'data': invalid_data}, cast('sig', 'InvalidOwner()'))
        invalid_deployment = chain.send('zero_owner_constructor', data=invalid_data, success=False)
        assert invalid_deployment['contractAddress'] is None
        # Automatic constructor nonpayability is also part of the target ABI.
        chain.expect_error('nonpayable_constructor', {'from': owner, 'data': '0x' + bytecode + owner_argument, 'value': '0x1'})
        deployment = chain.send('deploy_administration', data='0x' + bytecode + owner_argument)
        target = deployment['contractAddress']
        assert chain.rpc('eth_getCode', [target, 'latest']) != '0x'

        def read(signature, *args):
            return chain.call({'to': target, 'data': calldata(signature, *args)})

        def integer(signature, *args):
            return int(read(signature, *args), 16)

        def grant(grant_id):
            encoded = read('getGrant(uint256)', grant_id)
            assert len(encoded) == 2 + 64 * 7, encoded
            return [int(encoded[2 + 64 * i:2 + 64 * (i + 1)], 16) for i in range(7)]

        def snapshot():
            return {'owner': read('owner()'), 'next_id': integer('nextGrantId()'),
                    'balance': integer('treasuryBalance()'),
                    'grants': {str(i): grant(i) for i in [0, 1, 2, 3, 999, MAX]}}

        def reject(label, data, signature=None, arguments=(), sender=owner, value=0):
            before = snapshot()
            expected = None
            if signature:
                expected = cast('sig', signature) + ''.join(word(a) for a in arguments)
            tx = {'from': sender, 'to': target, 'data': data, 'value': hex(value), 'gas': hex(2_000_000)}
            chain.expect_error(label, tx, expected)
            chain.send(label, to=target, data=data, value=value, sender=sender, success=False)
            assert snapshot() == before, label

        def event(receipt, signature, indexed, data):
            assert len(receipt['logs']) == 1, receipt
            emitted = receipt['logs'][0]
            assert emitted['address'].lower() == target.lower()
            assert emitted['topics'] == [cast('keccak', signature), *['0x' + word(x) for x in indexed]], emitted
            assert emitted['data'] == '0x' + ''.join(word(x) for x in data), emitted

        assert integer('owner()') == int(owner, 16)
        assert integer('nextGrantId()') == 1 and integer('treasuryBalance()') == 0
        for grant_id in [0, 1, 999, MAX]:
            assert grant(grant_id) == [0] * 7
        now = int(chain.rpc('eth_getBlockByNumber', ['latest', False])['timestamp'], 16)
        expiry = now + 3600

        def create(grant_id, who, to, cap):
            data = calldata(CREATE, who, to, cap, expiry)
            assert int(chain.call({'from': owner, 'to': target, 'data': data}), 16) == grant_id
            assert integer('nextGrantId()') == grant_id  # eth_call leaves no allocation behind.
            receipt = chain.send(f'create_{grant_id}', to=target, data=data)
            event(receipt, 'GrantCreated(uint256,address,address,uint256,uint256)',
                  [grant_id, who, to], [cap, expiry])
            assert grant(grant_id) == [1, int(who, 16), int(to, 16), cap, 0, expiry, 1]
            assert integer('nextGrantId()') == grant_id + 1
            return receipt

        # Rejections do not allocate ID 1 or mutate any observed record.
        reject('unauthorized_create', calldata(CREATE, ZERO, ZERO, 0, 0), 'Unauthorized()', sender=stranger)
        reject('zero_delegate', calldata(CREATE, ZERO, recipient, 25, expiry), 'InvalidAddress()')
        reject('zero_recipient', calldata(CREATE, delegate, ZERO, 25, expiry), 'InvalidAddress()')
        reject('zero_cap', calldata(CREATE, delegate, recipient, 0, expiry), 'InvalidAmount()')
        reject('past_expiry', calldata(CREATE, delegate, recipient, 25, 0), 'InvalidExpiry()')
        current = int(chain.rpc('eth_getBlockByNumber', ['latest', False])['timestamp'], 16)
        reject('equal_expiry', calldata(CREATE, delegate, recipient, 25, current), 'InvalidExpiry()')
        create(1, delegate, recipient, 25)
        first = grant(1)
        create(2, delegate2, recipient2, MAX)
        second = grant(2)
        assert grant(1) == first
        reject('unauthorized_revoke_known', calldata('revoke(uint256)', 1), 'Unauthorized()', sender=stranger)
        reject('unauthorized_before_unknown', calldata('revoke(uint256)', 999), 'Unauthorized()', sender=stranger)
        for grant_id in [0, 999, MAX]:
            reject(f'unknown_revoke_{grant_id}', calldata('revoke(uint256)', grant_id), 'UnknownGrant(uint256)', [grant_id])
        revoked = chain.send('revoke_1', to=target, data=calldata('revoke(uint256)', 1))
        event(revoked, 'GrantRevoked(uint256)', [1], [])
        first[-1] = 0
        assert grant(1) == first and grant(2) == second
        repeat = chain.send('repeat_revoke_1', to=target, data=calldata('revoke(uint256)', 1))
        assert repeat['logs'] == [] and grant(1) == first and integer('nextGrantId()') == 3
        create(3, delegate, recipient2, 30)
        assert grant(1) == first and grant(2) == second  # No revival or sibling corruption.

        for data in ['0x', '0x01', '0xdeadbeef', calldata('deposit()'), calldata('spend(uint256,uint256)', 999, 1)]:
            reject('unsupported_' + data, data, 'UnsupportedCall()')
        for signature, args in [('owner()', []), ('nextGrantId()', []), ('treasuryBalance()', []),
                                ('getGrant(uint256)', [1]), ('revoke(uint256)', [1]),
                                (CREATE, [delegate, recipient, 25, expiry])]:
            reject('nonpayable_' + signature, calldata(signature, *args), value=1)
        reject('nonpayable_fallback', '0x', value=1)
        reject('truncated_known_selector', cast('sig', CREATE))
        # Deliberately noncanonical high address bits: ABI rejection, not policy address zero.
        invalid_address = cast('sig', CREATE) + word(1 << 160) + word(recipient) + word(25) + word(expiry)
        reject('noncanonical_address', invalid_address)
        # Environment fixture for unsolicited ETH; this is not a claimed payment test.
        chain.rpc('anvil_setBalance', [target, hex(55)])
        assert integer('treasuryBalance()') == 55
        assert int(chain.rpc('eth_getBalance', [target, 'latest']), 16) == 55
        assert grant(1) == first and grant(2) == second
        assert integer('owner()') == int(owner, 16) and integer('nextGrantId()') == 4
        final = snapshot()
        evidence = {'schema_version': 1, 'fork': 'osaka', 'tools': chain.versions,
                    'client_version': chain.rpc('web3_clientVersion', []),
                    'treasury': target, 'owner': owner,
                    'bytecode_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in sorted(artifacts.glob('*.bin'))},
                    'transactions': chain.receipts, 'expected_errors': chain.errors,
                    'balance_fixture': {'method': 'anvil_setBalance', 'wei': '55'},
                    'final': {'next_id': str(final['next_id']), 'owner': final['owner'],
                              'balance_wei': str(final['balance']),
                              'grants': {k: [str(x) for x in v] for k, v in final['grants'].items()}}}
        if record:
            Path(record).parent.mkdir(parents=True, exist_ok=True)
            Path(record).write_text(json.dumps(evidence, indent=2) + '\n')
        print(f'PASS Anvil administration: {len(chain.receipts)} transactions; '
              f'{len(chain.errors)} rejection checks; exact event topics/data; persistent isolated records')
        return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', help='Optional raw receipt and RPC error evidence JSON')
    run(parser.parse_args().record)
