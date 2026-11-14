#!/usr/bin/env python3
"""Exercise the independent sponsorship consumer on a temporary local Osaka chain."""
import argparse
import hashlib
import json
from pathlib import Path

from local_chain import LocalChain, cast

ROOT = Path(__file__).resolve().parent.parent
ZERO = '0x' + '00' * 20


def word(value):
    return f'{int(value, 16) if isinstance(value, str) and value.startswith("0x") else int(value):064x}'


def calldata(signature, *args):
    return cast('calldata', signature, *map(str, args))


def words(data):
    assert data.startswith('0x') and (len(data) - 2) % 64 == 0
    return [int(data[i:i + 64], 16) for i in range(2, len(data), 64)]


def run(record=None):
    with LocalChain(ROOT) as chain:
        creator, operator, beneficiary, outsider, other_beneficiary = chain.accounts[:5]
        artifacts = ROOT / 'examples/sponsorship/out'
        fixtures = ROOT / 'tests/runtime/sponsorship/out'
        bytecode = (artifacts / 'Sponsorship.bin').read_text().strip().removeprefix('0x')
        def now():
            return int(chain.rpc('eth_getBlockByNumber', ['latest', False])['timestamp'], 16)
        def creation(who, to, cap, expiry):
            return '0x' + bytecode + word(who) + word(to) + word(cap) + word(expiry)
        def read(address, signature, *args):
            return words(chain.call({'to': address, 'data': calldata(signature, *args)}))
        def balance(address):
            return int(chain.rpc('eth_getBalance', [address, 'latest']), 16)
        def event(receipt, emitter, signature, indexed, data):
            assert len(receipt['logs']) == 1
            log = receipt['logs'][0]
            assert log['address'].lower() == emitter.lower()
            assert log['topics'] == [cast('keccak', signature), *['0x' + word(x) for x in indexed]]
            assert log['data'] == '0x' + ''.join(word(x) for x in data)
        expiry = now() + 3600
        for label, who, to, cap, expiration, code in [
            ('invalid_operator', ZERO, beneficiary, 25, expiry, 5),
            ('invalid_beneficiary', operator, ZERO, 25, expiry, 5),
            ('invalid_cap', operator, beneficiary, 0, expiry, 6),
            ('invalid_expiry', operator, beneficiary, 25, 0, 7),
        ]:
            data = creation(who, to, cap, expiration)
            chain.expect_error(label, {'from': creator, 'data': data}, cast('sig', 'PolicyRejected(uint256)') + word(code))
            result = chain.send(label, data=data, success=False)
            assert result['contractAddress'] is None
        def deploy(label, to, cap=25, expiration=None):
            expiration = expiration or now() + 3600
            receipt = chain.send(label, data=creation(operator, to, cap, expiration))
            address = receipt['contractAddress']
            assert chain.rpc('eth_getCode', [address, 'latest']) != '0x'
            assert read(address, 'campaignSponsor()') == [int(creator, 16)]
            assert read(address, 'status()') == [1, int(operator, 16), int(to, 16), cap, 0, expiration, 1]
            return address
        target = deploy('deploy_primary', beneficiary)
        start = balance(beneficiary)
        def reject(label, address, data, code=None, signature=None, sender=operator, value=0, recipient=beneficiary):
            before = (read(address, 'status()'), read(address, 'campaignSponsor()'), balance(address), balance(recipient))
            expected = None
            if code is not None:
                expected = cast('sig', 'PolicyRejected(uint256)') + word(code)
            elif signature:
                expected = cast('sig', signature)
            chain.expect_error(label, {'from': sender, 'to': address, 'data': data, 'value': hex(value), 'gas': hex(2_000_000)}, expected)
            chain.send(label, to=address, data=data, sender=sender, value=value, success=False)
            assert (read(address, 'status()'), read(address, 'campaignSponsor()'), balance(address), balance(recipient)) == before
        reject('unfunded', target, calldata('sponsor(uint256)', 7), code=12)
        zero = chain.send('zero_funding', to=target, data=calldata('fund()'), sender=outsider)
        assert zero['logs'] == [] and balance(target) == 0
        funding = chain.send('fund_100', to=target, data=calldata('fund()'), value=100, sender=outsider)
        event(funding, target, 'Funded(address,uint256)', [outsider], [100])
        payment = chain.send('sponsor_7', to=target, data=calldata('sponsor(uint256)', 7), sender=operator)
        event(payment, target, 'Sponsored(address,address,uint256,uint256)', [operator, beneficiary], [7, 7])
        assert balance(target) == 93 and balance(beneficiary) == start + 7 and read(target, 'status()')[4] == 7
        reject('creator_is_not_operator', target, calldata('sponsor(uint256)', 1), code=2, sender=creator)
        reject('zero_amount', target, calldata('sponsor(uint256)', 0), code=6)
        reject('over_budget', target, calldata('sponsor(uint256)', 19), code=11)
        reject('operator_cannot_cancel', target, calldata('cancel()'), code=2)
        other_start = balance(other_beneficiary)
        second = deploy('deploy_second', other_beneficiary, cap=10)
        chain.send('fund_second', to=second, data=calldata('fund()'), value=10, sender=outsider)
        payment = chain.send('exact_second_limit', to=second, data=calldata('sponsor(uint256)', 10), sender=operator)
        event(payment, second, 'Sponsored(address,address,uint256,uint256)', [operator, other_beneficiary], [10, 10])
        assert read(target, 'status()')[4] == 7 and read(second, 'status()')[4] == 10
        assert balance(other_beneficiary) == other_start + 10 and balance(second) == 0
        cancelled = chain.send('cancel_primary', to=target, data=calldata('cancel()'))
        event(cancelled, target, 'Cancelled()', [], [])
        repeated = chain.send('repeat_cancel', to=target, data=calldata('cancel()'))
        assert repeated['logs'] == []
        reject('cancelled', target, calldata('sponsor(uint256)', 1), code=4)
        deadline = now() + 600
        expired = deploy('deploy_expiring', beneficiary, expiration=deadline)
        chain.send('fund_expiring', to=expired, data=calldata('fund()'), value=10)
        chain.rpc('evm_setNextBlockTimestamp', [deadline])
        chain.rpc('evm_mine', [])
        assert now() == deadline
        reject('exclusive_expiry', expired, calldata('sponsor(uint256)', 1), code=9)
        receiver_code = (fixtures / 'Receiver.bin').read_text().strip().removeprefix('0x')
        receiver = chain.send('deploy_receiver', data='0x' + receiver_code)['contractAddress']
        recovery = deploy('deploy_recovery', receiver)
        chain.send('fund_recovery', to=recovery, data=calldata('fund()'), value=100)
        chain.send('receiver_reject', to=receiver, data=calldata('reject(bool)', 'true'))
        reject('rejected_payment', recovery, calldata('sponsor(uint256)', 7), signature='PaymentFailed()', recipient=receiver)
        chain.send('receiver_accept', to=receiver, data=calldata('reject(bool)', 'false'))
        payment = chain.send('later_success', to=recovery, data=calldata('sponsor(uint256)', 7), sender=operator)
        event(payment, recovery, 'Sponsored(address,address,uint256,uint256)', [operator, receiver], [7, 7])
        assert read(recovery, 'status()')[4] == 7 and balance(recovery) == 93 and balance(receiver) == 7
        reject('nonpayable_valid_payment', recovery, calldata('sponsor(uint256)', 1), value=1, recipient=receiver)
        reject('nonpayable_valid_cancel', recovery, calldata('cancel()'), sender=creator, value=1, recipient=receiver)
        reject('unsupported_empty_calldata', recovery, '0x', signature='UnsupportedCall()', recipient=receiver)
        evidence = {'schema_version': 1, 'fork': 'osaka', 'tools': chain.versions,
                    'roles': {'creator': creator, 'operator': operator, 'beneficiary': beneficiary, 'depositor': outsider},
                    'contracts': {'primary': target, 'second': second, 'expired': expired, 'recovery': recovery, 'receiver': receiver},
                    'bytecode_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                        for directory in [artifacts, fixtures] for p in sorted(directory.glob('*.bin'))},
                    'transactions': chain.receipts, 'expected_errors': chain.errors,
                    'expiry_equality_timestamp': str(deadline),
                    'final': {'primary': [str(x) for x in read(target, 'status()')],
                              'second': [str(x) for x in read(second, 'status()')],
                              'recovery': [str(x) for x in read(recovery, 'status()')],
                              'recovery_balance_wei': str(balance(recovery)), 'recovery_recipient_wei': str(balance(receiver))}}
        if record:
            Path(record).parent.mkdir(parents=True, exist_ok=True)
            Path(record).write_text(json.dumps(evidence, indent=2) + '\n')
        print(f'PASS Anvil sponsorship: {len(chain.receipts)} transactions, {len(chain.errors)} rejection checks, '
              'independent roles/campaigns, exact events, expiry and rollback')
        return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', help='Optional raw sponsorship transaction evidence JSON')
    run(parser.parse_args().record)
