# Phase 3 — protected spending and real ETH

Status: completed locally on 14 November 2026, using Fe 26.5.0, Sonatina,
optimization 1, release/test profiles, checked arithmetic, and local Osaka EVMs.
The treasury now implements the complete frozen
[treasury v0 interface](../spec/treasury-v0.md).

## Run

From this independent repository root:

```sh
python3 scripts/verify-spending.py
python3 scripts/verify-policy.py
python3 scripts/verify-phase0.py
```

`verify-spending.py` includes the administration regression, full ABI check,
eleven spending/callback Fe tests, release builds of the treasury and test
recipient, and a fresh local Anvil spending scenario. It verifies the pinned
compiler digest/version and Foundry commit. `FE_BIN` can select an existing
pinned release binary. No external RPC or funded real account is used.

To refresh raw spending evidence:

```sh
python3 scripts/verify-spending.py --record docs/evidence/anvil-spending.json
```

## Implementation

`deposit()` is explicitly payable and open to any sender. Positive deposits
emit the exact Deposited event; zero deposits emit none. Both paths acquire and
release the same mutex as create, revoke, and spend. Empty calldata remains an
unsupported, nonpayable fallback, not an implicit deposit entry point.

`spend(grantId, amount)` locks the shared state, loads the current grant, and
constructs read-only `PolicyContext` from actual caller, timestamp, and balance.
It calls the unchanged pure evaluator, maps rejected categories to exact typed
ABI errors, and persists the proposed spent value before the external payment.
No mutable storage projection survives that call. The call pays the stored
recipient with empty calldata, exact amount, and requested gas 100,000, using
the pinned stdlib's non-bubbling `send_value` path without copying returndata.

Failed payment produces `PaymentFailed()` and EVM rollback restores accounting,
ETH, lock, and logs. Successful payment emits Spent and explicitly unlocks.
Two legitimate operations in the same transaction therefore work. Public
getters remain available during callbacks, exposing reserved spent and actual
post-transfer balance exactly as specified.

All eight functions, four events, fifteen errors, constructor, and fallback
match the frozen target ABI. The comparison preserves types, ordering,
mutability, indexing, and anonymity; it ignores argument/return labels that are
only metadata. The Phase 2 ABI snapshot remains a historical administrative
projection, and its canonical entries still match the new full contract.
No storage layout compatibility claim follows from this ABI check.

## Verification results

| Check | Result |
| --- | --- |
| `fe check treasury` and formatting | Passed through administration runner |
| `fe test tests/runtime/administration --backend sonatina -O 1` | 6 passed |
| Full emitted ABI and Phase 2 projection | Passed |
| Local administration regression | 32 submitted transactions, 27 expected rejection checks |
| `fe check tests/runtime/spending` and formatting | Passed |
| `fe test tests/runtime/spending --backend sonatina -O 1` | 11 passed, 0 failed |
| Treasury and test recipient release builds | Passed, bytecode/runtime/ABI/metadata emitted |
| Local spending scenario | 89 submitted transactions, 16 expected rejection checks, 7 callback modes; all assertions passed |
| Pure policy regression | 70 vectors on each of Sonatina/native; unit-type negative passed |
| Phase 0 regression | Reference tests, access pair, payment tests, build, and local transactions passed |

The spending Fe tests cover successful batch payments, recipient rejection and
same-transaction recovery, each protected callback entry point, the callback
getter view, insufficient funding, exact policy error payloads, and uncaught
callback failure. Runtime checks compare exact custom-error bytes, not merely
nonzero exit codes. Anvil additionally tests actual block time at before/equal/
after expiry, mined receipts, independent account roles, and committed logs.

## Callback matrix

The test-only CallbackRecipient can be the treasury's owner, delegate, and
recipient simultaneously. Its nested create/revoke/spend calls would otherwise
have valid authority and parameters. The checks therefore establish a lock
rejection, not an unrelated authority error or an out-of-gas failure. The fixture
has an intentionally unrestricted controller and must not be used as a production
wallet or delegate. It is built separately from the production treasury ingot.

| Mode | Recipient behavior | Observed result |
| --- | --- | --- |
| 0 | Accept payment | ETH/accounting commit |
| 1 | Emit a recipient log, then reject | PaymentFailed; all payment/accounting/log changes roll back |
| 2 | Catch nested spend on the same grant | Exactly Reentrant; outer payment succeeds once |
| 3 | Catch nested revoke as authorized owner | Exactly Reentrant; grant remains active |
| 4 | Catch nested grant creation as authorized owner | Exactly Reentrant; no new ID or record |
| 5 | Catch nested zero deposit | Exactly Reentrant; no event |
| 6 | Catch nested positive deposit | Exactly Reentrant; attempted returned value rolls back |
| 7 | Observe grant and balance through getters | Reserved spent 7, actual treasury balance 93 during a 7-wei payment from 100 |
| 8 | Bubble a nested revoke's lock error | Outer PaymentFailed; entire outer operation rolls back |

For modes 2–8, the Anvil runner then disables the callback and submits two valid
2-wei payments in one transaction. Both complete, their Spent events have the
correct successive newSpent values, and final ETH/accounting agree. The Fe suite
also catches a failed recipient payment and completes a later valid spend within
the same transaction, proving rollback restored the lock without relying on a
new transaction resetting transient storage.

## Transaction evidence

[anvil-spending.json](evidence/anvil-spending.json) records the treasury/fixture
bytecode file hashes, pinned tool versions, raw transactions/receipts, expected
RPC error objects, callback observations, and final grant states. Quantities in
final observations are decimal strings; RPC quantities remain exact hex strings.
Failed submitted transactions must have status 0 and no logs.

The main scenario uses distinct owner, delegate, recipient, and depositor roles.
It confirms that an owner without delegate authority cannot spend, while any
account can explicitly deposit. It checks exact remaining-cap and available-
balance error payloads, zero amount, unknown/reserved IDs, revoked grants, cap
precedence, and a valid spend call carrying forbidden transaction value.
The valid nonpayable test uses an otherwise authorized, affordable spend, so a
domain error cannot hide accidental payable behavior.

After a failed funding attempt, a later deposit permits payment. Spending exactly
the remaining cap succeeds; another wei fails. Actual block timestamps test a
last valid payment, equality rejection, and rejection after expiry, with exact
Expired(expiresAt,currentTime) payloads from eth_call. Each failed transaction
preserves the observed grant records, owner, next ID, treasury balance, and
recipient balances. An eth_call error payload is a simulation result at the
recorded latest time; its matching submitted failed receipt need not encode the
same currentTime if mining advances the timestamp.

Deposited and Spent log topics/data are compared to the canonical signatures and
indexed-field order. Successful contract recipients emit RecipientTouched before
Spent. Rejected recipients and uncaught callback errors leave no recipient or
treasury log committed. The main scenario also verifies that spending one grant
does not change sibling snapshots.

## Source verification, trust, and remaining work

The compiler remains at commit
`3dab95f8eebdccf9a2382bb59a33f7bbd03540ca`; the stdlib's Call, Ctx, Mutex, and
returndata helpers and passing mutex fixtures were inspected before use. No
application unsafe code or new external dependency was introduced. The private
error mapper's cap subtraction is reached only after the pure evaluator has
established spent <= cap. The safe checked addition remains in the pure policy.

Requested recipient gas remains the frozen 100,000; EVM caps/stipend apply and
more expensive recipients can fail. Transaction-level gas exhaustion is not a
guaranteed application error. The test matrix covers the listed callback modes,
not all possible hostile programs, arbitrary gas settings, or every cross-grant
callback sequence. Maximum integer arithmetic remains covered by the independent
pure vectors, and full-width error/event quantities are exercised on Anvil.
This phase does not constitute an audit or formal verification.

Next is Phase 4: demonstrate a second independent consumer of the same policy
library, external compile-fail proofs of omitted payment/store access and
read-only boundaries, and a documented capability/dependency table. Adversarial
review, seeded-defect detection, and final handoff remain Phases 5 and 6.
