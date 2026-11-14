#!/usr/bin/env python3
"""Exercise the Fe payment probe on a fresh local Osaka chain (no external RPC)."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


class RpcError(RuntimeError):
    def __init__(self, error):
        self.error = error
        super().__init__(str(error))


def run(record=None):
    manifest = json.loads((ROOT / 'toolchain.json').read_text())
    versions = {}
    for tool in ['anvil', 'cast']:
        version = subprocess.check_output([tool, '--version'], text=True).strip()
        if manifest['foundry']['commit'] not in version:
            raise RuntimeError(f'{tool} does not match the pinned Foundry commit')
        versions[tool] = version
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    url = f'http://127.0.0.1:{port}'

    def rpc(method, params):
        payload = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode()
        request = urllib.request.Request(url, payload, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=3) as response:
            result = json.load(response)
        if 'error' in result:
            raise RpcError(result['error'])
        return result['result']

    with tempfile.TemporaryFile() as log:
        node = subprocess.Popen(['anvil', '--hardfork', 'osaka', '--host', '127.0.0.1',
                                 '--port', str(port), '--silent'], stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 15
            while True:
                if node.poll() is not None:
                    log.seek(0)
                    raise RuntimeError('Anvil startup failed: ' + log.read().decode())
                try:
                    accounts = rpc('eth_accounts', [])
                    break
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() > deadline:
                        raise RuntimeError('Anvil readiness timeout')
                    time.sleep(0.1)
            owner, stranger = accounts[:2]
            receipts = []

            def send(to=None, data='0x', value=0, sender=owner, success=True):
                tx = {'from': sender, 'data': data, 'value': hex(value), 'gas': hex(1_000_000)}
                if to:
                    tx['to'] = to
                tx_hash = rpc('eth_sendTransaction', [tx])
                deadline = time.monotonic() + 10
                while True:
                    receipt = rpc('eth_getTransactionReceipt', [tx_hash])
                    if receipt:
                        break
                    if time.monotonic() > deadline:
                        raise RuntimeError('Receipt timeout')
                    time.sleep(0.1)
                assert int(receipt['status'], 16) == int(success), receipt
                receipts.append({'transaction': tx, 'receipt': receipt})
                return receipt

            def calldata(signature, *args):
                return subprocess.check_output(['cast', 'calldata', signature, *map(str, args)], text=True).strip()

            artifacts = ROOT / 'spike' / 'out'

            def deploy(name, recipient=None):
                bytecode = (artifacts / f'{name}.bin').read_text().strip().removeprefix('0x')
                if recipient:
                    bytecode += recipient.removeprefix('0x').rjust(64, '0')
                address = send(data='0x' + bytecode)['contractAddress']
                assert rpc('eth_getCode', [address, 'latest']) != '0x'
                return address

            def balance(address):
                return int(rpc('eth_getBalance', [address, 'latest']), 16)

            def paid(address):
                return int(rpc('eth_call', [{'to': address, 'data': calldata('paid()')}, 'latest']), 16)

            errors = []

            def expect_error(address, data, signature, sender=owner, value=0):
                expected = subprocess.check_output(['cast', 'sig', signature], text=True).strip()
                try:
                    rpc('eth_call', [{'from': sender, 'to': address, 'data': data,
                                      'value': hex(value), 'gas': hex(1_000_000)}, 'latest'])
                except RpcError as failure:
                    assert failure.error.get('data') == expected, failure.error
                    errors.append({'to': address, 'calldata': data, 'error': failure.error,
                                   'expected_error': signature})
                else:
                    raise AssertionError(f'Expected {signature}')

            accepting = deploy('AcceptingRecipient')
            rejecting = deploy('RejectingRecipient')
            good = deploy('PaymentProbe', accepting)
            bad = deploy('PaymentProbe', rejecting)
            deposit = calldata('deposit()')
            pay7 = calldata('pay(uint256)', 7)
            for probe in [good, bad]:
                send(probe, deposit, 100)
                assert balance(probe) == 100 and paid(probe) == 0
            send(good, pay7)
            assert balance(accepting) == 7 and balance(good) == 93 and paid(good) == 7
            expect_error(good, pay7, 'Unauthorized()', sender=stranger)
            send(good, pay7, sender=stranger, success=False)
            assert balance(accepting) == 7 and balance(good) == 93 and paid(good) == 7
            expect_error(good, calldata('pay(uint256)', 0), 'InvalidAmount()')
            # Observe the recipient's deliberate rejection, then the probe's mapping.
            expect_error(rejecting, '0x', 'RecipientRejected()', value=1)
            expect_error(bad, pay7, 'PaymentFailed()')
            failed = send(bad, pay7, success=False)
            assert not failed['logs']
            assert balance(rejecting) == 0 and balance(bad) == 100 and paid(bad) == 0
            send(bad, deposit, 1)
            assert balance(bad) == 101
            send(good, calldata('pay(uint256)', 3))
            assert balance(accepting) == 10 and balance(good) == 90 and paid(good) == 10
            evidence = {
                'schema_version': 1, 'fork': 'osaka', 'chain_id': rpc('eth_chainId', []),
                'client_version': rpc('web3_clientVersion', []), 'tools': versions,
                'contracts': {'accepting': accepting, 'rejecting': rejecting, 'good_probe': good, 'bad_probe': bad},
                'bytecode_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted(artifacts.glob('*.bin'))},
                'transactions': receipts, 'expected_errors': errors,
                'final': {'recipient_wei': str(balance(accepting)), 'good_probe_wei': str(balance(good)),
                          'good_paid_wei': str(paid(good)), 'rejecting_recipient_wei': str(balance(rejecting)),
                          'bad_probe_wei': str(balance(bad)), 'bad_paid_wei': str(paid(bad))},
            }
            if record:
                Path(record).parent.mkdir(parents=True, exist_ok=True)
                Path(record).write_text(json.dumps(evidence, indent=2) + '\n')
            print('PASS Anvil Osaka: ETH transfer, exact errors, rejected transaction rollback, later calls')
            return evidence
        finally:
            node.terminate()
            try:
                node.wait(timeout=5)
            except subprocess.TimeoutExpired:
                node.kill()
                node.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', help='Optional path for raw RPC evidence JSON')
    run(parser.parse_args().record)
