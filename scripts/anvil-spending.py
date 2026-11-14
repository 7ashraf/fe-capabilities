#!/usr/bin/env python3
"""Execute funded treasury grants, rollback, expiry, and authorized hostile callbacks."""
import argparse
import hashlib
import json
from pathlib import Path

from local_chain import LocalChain, cast

ROOT = Path(__file__).resolve().parent.parent
MAX = 2**256 - 1
CREATE = 'createGrant(address,address,uint256,uint256)'
SPEND = 'spend(uint256,uint256)'
EXECUTE = 'execute(address,uint256,uint256,bool)'


def word(value):
    return f'{int(value, 16) if isinstance(value, str) and value.startswith("0x") else int(value):064x}'


def calldata(signature, *args):
    return cast('calldata', signature, *map(str, args))


def words(data):
    assert data.startswith('0x') and (len(data) - 2) % 64 == 0
    return [int(data[i:i + 64], 16) for i in range(2, len(data), 64)]


def run(record=None):
    with LocalChain(ROOT) as chain:
        owner, delegate, recipient, depositor, other_recipient, outsider = chain.accounts[:6]
        treasury_artifacts = ROOT / 'treasury/out'
        fixture_artifacts = ROOT / 'tests/runtime/spending/out'

        def deploy(label, directory, contract, arguments=''):
            data = '0x' + (directory / f'{contract}.bin').read_text().strip().removeprefix('0x') + arguments
            result = chain.send(label, data=data)
            address = result['contractAddress']
            assert chain.rpc('eth_getCode', [address, 'latest']) != '0x'
            return address

        def read(address, signature, *args):
            return words(chain.call({'to': address, 'data': calldata(signature, *args)}))

        def balance(address):
            return int(chain.rpc('eth_getBalance', [address, 'latest']), 16)

        def grant(target, grant_id):
            result = read(target, 'getGrant(uint256)', grant_id)
            assert len(result) == 7
            return result

        def timestamp():
            return int(chain.rpc('eth_getBlockByNumber', ['latest', False])['timestamp'], 16)

        def check_event(receipt, emitter, signature, indexed, data):
            matching = [item for item in receipt['logs'] if item['address'].lower() == emitter.lower()]
            assert len(matching) == 1, receipt
            log = matching[0]
            assert log['topics'] == [cast('keccak', signature), *['0x' + word(x) for x in indexed]], log
            assert log['data'] == '0x' + ''.join(word(x) for x in data), log

        target = deploy('deploy_treasury', treasury_artifacts, 'Treasury', word(owner))
        recipients = [recipient, other_recipient]
        recipient_start = balance(recipient)
        other_start = balance(other_recipient)
        expiry = timestamp() + 3600

        def snapshot():
            return {'grants': [grant(target, i) for i in range(1, 5)],
                    'next_id': read(target, 'nextGrantId()'), 'treasury_balance': balance(target),
                    'owner': read(target, 'owner()'), 'recipient_balances': [balance(x) for x in recipients]}

        def reject(label, data, signature=None, arguments=(), sender=delegate, value=0):
            before = snapshot()
            expected = None if signature is None else cast('sig', signature) + ''.join(word(x) for x in arguments)
            chain.expect_error(label, {'from': sender, 'to': target, 'data': data, 'value': hex(value),
                                       'gas': hex(2_000_000)}, expected)
            chain.send(label, to=target, data=data, sender=sender, value=value, success=False)
            assert snapshot() == before, label

        zero = chain.send('zero_deposit', to=target, data=calldata('deposit()'), sender=depositor)
        assert zero['logs'] == [] and balance(target) == 0
        deposit = chain.send('deposit_100', to=target, data=calldata('deposit()'), value=100, sender=depositor)
        check_event(deposit, target, 'Deposited(address,uint256)', [depositor], [100])
        assert balance(target) == 100
        for grant_id, to, cap in [(1, recipient, 25), (2, other_recipient, 200), (3, recipient, MAX)]:
            receipt = chain.send(f'create_{grant_id}', to=target, data=calldata(CREATE, delegate, to, cap, expiry))
            check_event(receipt, target, 'GrantCreated(uint256,address,address,uint256,uint256)',
                        [grant_id, delegate, to], [cap, expiry])
            assert grant(target, grant_id) == [1, int(delegate, 16), int(to, 16), cap, 0, expiry, 1]
        siblings = [grant(target, 2), grant(target, 3)]
        payment = chain.send('spend_7', to=target, data=calldata(SPEND, 1, 7), sender=delegate)
        check_event(payment, target, 'Spent(uint256,address,address,uint256,uint256)', [1, delegate, recipient], [7, 7])
        assert balance(target) == 93 and balance(recipient) == recipient_start + 7
        assert grant(target, 1)[4] == 7 and [grant(target, 2), grant(target, 3)] == siblings
        reject('owner_is_not_delegate', calldata(SPEND, 1, 1), 'Unauthorized()', sender=owner)
        reject('outsider_is_not_delegate', calldata(SPEND, 1, 1), 'Unauthorized()', sender=outsider)
        for grant_id in [0, 999, MAX]:
            reject(f'unknown_{grant_id}_before_authority', calldata(SPEND, grant_id, 0), 'UnknownGrant(uint256)', [grant_id], sender=outsider)
        reject('zero_amount', calldata(SPEND, 1, 0), 'InvalidAmount()')
        reject('cap_one_over', calldata(SPEND, 1, 19), 'CapExceeded(uint256,uint256)', [18, 19])
        reject('cap_before_balance', calldata(SPEND, 1, MAX), 'CapExceeded(uint256,uint256)', [18, MAX])
        reject('insufficient_balance', calldata(SPEND, 2, 100), 'InsufficientBalance(uint256,uint256)', [93, 100])
        reject('spend_is_nonpayable', calldata(SPEND, 1, 1), sender=delegate, value=1)
        deposit = chain.send('later_deposit_50', to=target, data=calldata('deposit()'), value=50, sender=outsider)
        check_event(deposit, target, 'Deposited(address,uint256)', [outsider], [50])
        payment = chain.send('later_spend_100', to=target, data=calldata(SPEND, 2, 100), sender=delegate)
        check_event(payment, target, 'Spent(uint256,address,address,uint256,uint256)', [2, delegate, other_recipient], [100, 100])
        assert balance(target) == 43 and balance(other_recipient) == other_start + 100
        payment = chain.send('exact_remaining_18', to=target, data=calldata(SPEND, 1, 18), sender=delegate)
        check_event(payment, target, 'Spent(uint256,address,address,uint256,uint256)', [1, delegate, recipient], [18, 25])
        assert balance(target) == 25 and balance(recipient) == recipient_start + 25
        reject('spent_cap', calldata(SPEND, 1, 1), 'CapExceeded(uint256,uint256)', [0, 1])
        chain.send('revoke_2', to=target, data=calldata('revoke(uint256)', 2))
        reject('revoked_grant', calldata(SPEND, 2, 1), 'InactiveGrant(uint256)', [2])
        # Real block context at before/equal/after exclusive expiry.
        expiry_observations = []
        chain.rpc('evm_setNextBlockTimestamp', [expiry - 2])
        chain.rpc('evm_mine', [])
        payment = chain.send('last_valid_timestamp', to=target, data=calldata(SPEND, 3, 1), sender=delegate)
        block = chain.rpc('eth_getBlockByNumber', [payment['blockNumber'], False])
        assert int(block['timestamp'], 16) < expiry
        expiry_observations.append({'label': 'last_valid_payment', 'block_number': block['number'],
                                    'timestamp': str(int(block['timestamp'], 16)), 'expires_at': str(expiry)})
        check_event(payment, target, 'Spent(uint256,address,address,uint256,uint256)', [3, delegate, recipient], [1, 1])
        chain.rpc('evm_setNextBlockTimestamp', [expiry])
        chain.rpc('evm_mine', [])
        assert timestamp() == expiry
        equal_block = chain.rpc('eth_getBlockByNumber', ['latest', False])
        expiry_observations.append({'label': 'equality_error_call', 'block_number': equal_block['number'],
                                    'timestamp': str(expiry), 'expires_at': str(expiry)})
        reject('expiry_equality', calldata(SPEND, 3, 1), 'Expired(uint256,uint256)', [expiry, expiry])
        current = timestamp()
        assert current >= expiry
        if current == expiry:
            chain.rpc('evm_setNextBlockTimestamp', [expiry + 1])
            chain.rpc('evm_mine', [])
        after_block = chain.rpc('eth_getBlockByNumber', ['latest', False])
        expiry_observations.append({'label': 'after_expiry_error_call', 'block_number': after_block['number'],
                                    'timestamp': str(int(after_block['timestamp'], 16)), 'expires_at': str(expiry)})
        reject('after_expiry', calldata(SPEND, 3, 1), 'Expired(uint256,uint256)', [expiry, timestamp()])

        rejecting = deploy('deploy_rejecting_recipient', fixture_artifacts, 'CallbackRecipient')
        recipients.append(rejecting)
        fresh_expiry = timestamp() + 3600
        chain.send('create_rejecting_grant', to=target, data=calldata(CREATE, delegate, rejecting, 25, fresh_expiry))
        chain.send('configure_rejection', to=rejecting, data=calldata('configure(address,uint256,uint256)', target, 4, 1))
        reject('recipient_rejection', calldata(SPEND, 4, 7), 'PaymentFailed()')
        assert read(rejecting, 'stats()') == [0, 0, 0, 0]
        chain.send('configure_acceptance', to=rejecting, data=calldata('configure(address,uint256,uint256)', target, 4, 0))
        payment = chain.send('recovery_after_rejection', to=target, data=calldata(SPEND, 4, 7), sender=delegate)
        check_event(payment, target, 'Spent(uint256,address,address,uint256,uint256)', [4, delegate, rejecting], [7, 7])
        assert len(payment['logs']) == 2
        assert payment['logs'][0]['topics'] == [cast('keccak', 'RecipientTouched()')]
        assert payment['logs'][1]['address'].lower() == target.lower()
        assert balance(rejecting) == 7 and grant(target, 4)[4] == 7
        assert read(rejecting, 'stats()') == [1, 1, 0, 0]
        zero = chain.send('zero_deposit_after_payments', to=target, data=calldata('deposit()'), sender=outsider)
        assert zero['logs'] == []

        callbacks = []
        for mode in [2, 3, 4, 5, 6, 7, 8]:
            fixture = deploy(f'deploy_callback_{mode}', fixture_artifacts, 'CallbackRecipient')
            guarded = deploy(f'deploy_guarded_{mode}', treasury_artifacts, 'Treasury', word(fixture))
            chain.send(f'create_callback_grant_{mode}', to=fixture,
                       data=calldata('create(address,uint256,uint256)', guarded, 25, timestamp() + 3600))
            chain.send(f'fund_callback_{mode}', to=guarded, data=calldata('deposit()'), value=100)
            chain.send(f'configure_callback_{mode}', to=fixture,
                       data=calldata('configure(address,uint256,uint256)', guarded, 1, mode))
            execute = calldata(EXECUTE, guarded, 1, 7, 'false')
            if mode == 8:
                chain.expect_error('uncaught_callback_failure', {'from': owner, 'to': fixture, 'data': execute,
                                                                'gas': hex(2_000_000)}, cast('sig', 'PaymentFailed()'))
                chain.send('uncaught_callback_failure', to=fixture, data=execute, success=False)
                assert balance(guarded) == 100 and balance(fixture) == 0 and grant(guarded, 1)[4] == 0
                assert read(fixture, 'stats()') == [0, 0, 0, 0]
            else:
                payment = chain.send(f'callback_attempt_{mode}', to=fixture, data=execute)
                check_event(payment, guarded, 'Spent(uint256,address,address,uint256,uint256)', [1, fixture, fixture], [7, 7])
                assert len(payment['logs']) == 2 and payment['logs'][0]['topics'] == [cast('keccak', 'RecipientTouched()')]
                assert balance(guarded) == 93 and balance(fixture) == 7 and grant(guarded, 1)[4] == 7
                expected = [1, 1, 7, 93] if mode == 7 else [1, 1, 0, 0]
                assert read(fixture, 'stats()') == expected
            assert read(guarded, 'nextGrantId()') == [2]
            assert grant(guarded, 1)[-1] == 1 and grant(guarded, 2) == [0] * 7
            before_recovery = {'stats': [str(x) for x in read(fixture, 'stats()')],
                               'spent_wei': str(grant(guarded, 1)[4]), 'treasury_wei': str(balance(guarded))}
            chain.send(f'disable_callback_{mode}', to=fixture,
                       data=calldata('configure(address,uint256,uint256)', guarded, 1, 0))
            # Two legitimate spends in a single mined transaction, after each attack case.
            payment = chain.send(f'two_valid_spends_after_callback_{mode}', to=fixture,
                                 data=calldata(EXECUTE, guarded, 1, 2, 'true'))
            assert len(payment['logs']) == 4
            new_spent = 4 if mode == 8 else 11
            spent_logs = [item for item in payment['logs'] if item['address'].lower() == guarded.lower()]
            assert len(spent_logs) == 2
            for item, expected_spent in zip(spent_logs, [new_spent - 2, new_spent]):
                assert item['topics'] == [cast('keccak', 'Spent(uint256,address,address,uint256,uint256)'),
                                          '0x' + word(1), '0x' + word(fixture), '0x' + word(fixture)]
                assert item['data'] == '0x' + word(2) + word(expected_spent)
            assert grant(guarded, 1)[4] == new_spent and grant(guarded, 1)[-1] == 1
            assert balance(guarded) == 100 - new_spent and balance(fixture) == new_spent
            callbacks.append({'mode': mode, 'fixture': fixture, 'treasury': guarded,
                              'after_attack': before_recovery, 'final_spent_wei': str(new_spent),
                              'final_treasury_wei': str(balance(guarded))})
        evidence = {'schema_version': 1, 'fork': 'osaka', 'tools': chain.versions,
                    'client_version': chain.rpc('web3_clientVersion', []),
                    'treasury': target, 'roles': {'owner': owner, 'delegate': delegate, 'recipient': recipient,
                                                'depositor': depositor, 'other_recipient': other_recipient},
                    'bytecode_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                        for directory in [treasury_artifacts, fixture_artifacts] for p in sorted(directory.glob('*.bin'))},
                    'transactions': chain.receipts, 'expected_errors': chain.errors, 'callbacks': callbacks,
                    'expiry_observations': expiry_observations,
                    'final': {'grants': {str(i): [str(x) for x in grant(target, i)] for i in range(1, 5)},
                              'treasury_wei': str(balance(target)), 'recipient_gain_wei': str(balance(recipient) - recipient_start),
                              'other_recipient_gain_wei': str(balance(other_recipient) - other_start),
                              'rejecting_then_accepting_recipient_wei': str(balance(rejecting))}}
        if record:
            Path(record).parent.mkdir(parents=True, exist_ok=True)
            Path(record).write_text(json.dumps(evidence, indent=2) + '\n')
        print(f'PASS Anvil spending: {len(chain.receipts)} transactions; {len(chain.errors)} exact/rejection checks; '
              f'{len(callbacks)} callback modes; real transfers, expiry, events, rollback and later batch calls')
        return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', help='Optional raw transaction and callback evidence JSON')
    run(parser.parse_args().record)
