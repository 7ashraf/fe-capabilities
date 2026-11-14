# Invariant and entry-point test matrix

This is an engineering review of the current submitted code, not an independent
security audit. It maps the ten planned invariants to concrete source boundaries
and tests, and records remaining gaps instead of inferring safety from test count.
The pure package and both production consumers are unchanged by Phase 5.

## Treasury invariants

| Invariant | Boundary/control | Evidence |
| --- | --- | --- |
| 1. Successful spender is the current delegate of a valid grant | Locked load, real caller context, evaluate_spend | `runtime_policy_errors_have_exact_payloads`; Anvil owner/outsider denials; `wrong_caller` vector and delegate-removal mutant |
| 2. spent <= cap, with safe arithmetic | Validate record, compare against cap - spent, only then add | 70 vectors include exact remaining, one over, MAX, final wei, attempted overflow, corrupt spent; cap-removal mutant |
| 3. Payment uses stored recipient and consumes the same requested amount | ABI accepts only ID/amount; persist proposed spent; send exact Wei | Full ABI comparison; fixed-recipient Anvil logs/value observations; two same-transaction spends |
| 4. Expiry is exclusive | Actual timestamp, now >= expiry rejection | Before/equal/after vectors; equality mutant; review receipts mined at expiresAt-1, expiresAt, expiresAt+1 |
| 5. Revocation blocks later spends and old IDs never revive | exists separate from active; no deletion; monotonically increasing next ID | Administration persistence/ID tests; inactive spending error; repeated-revoke no-op; reserved/MAX allocator vectors |
| 6. Failed payment rolls back accounting and logs | Reserve before call, PaymentFailed reverts outer operation | Rejecting-recipient and uncaught-callback tests; failed receipts have no logs; same-transaction and later-transaction recovery |
| 7. Reentry cannot mutate protected state | One Mutex covers deposit/create/revoke/spend and every grant | Authorized callback modes 2–6; contract-owner create/revoke attempts; new cross-grant Fe/Anvil tests |
| 8. Later normal calls in the same transaction work | Explicit unlock on success/no-op; revert restores prior lock | Batch spend, repeat revoke followed by create, failure then later spend, forgotten-unlock mutant |
| 9. One grant cannot overwrite another | Keyed private store, current record update only | Two distinct records/caps; sibling observations after payments; cross-grant callback leaves grant 2 untouched, then normal grant-2 batch works |
| 10. Actual balance may include unsolicited ETH | Use selfbalance, no deposit-minus-spend ledger equality | Balance fixture in administration runner; real deposits/payments and actual-balance funding errors; actual forced-ETH opcode transfer remains untested |

Balance deltas for simple test recipients are observations of those fixtures.
An arbitrary recipient can forward or return ETH, so no universal claim says its
final net balance increase always equals the treasury's successful call value.

## Every treasury entry point

| Entry point | Authority and state | Expected success/failure coverage |
| --- | --- | --- |
| Constructor | Explicit immutable nonzero owner; next ID 1 | Valid EOA/contract owner; exact InvalidOwner; constructor nonpayability |
| deposit | Any sender, shared lock, actual call value | Positive event fields; zero no-event; both zero/positive callback attempts rejected with Reentrant |
| createGrant | Owner only; shared lock; pure request validation; allocate/persist once | Valid creation, invalid addresses/cap/expiry, no ID consumption on failure, contract owner, exact logs, blocked owner callback |
| revoke | Owner only; shared lock; known ID; deactivate or no-op | Unknown-ID payload, unauthorized-before-unknown order, repeat no-event, lock recovery, blocked owner callback |
| spend | Shared lock; known ID before delegate check; pure policy; reserve/pay/emit/unlock | Wrong caller, unknown/reserved ID, inactive, zero, cap/funding payloads, expiry, payment rollback, callbacks and batch execution |
| owner | Read-only immutable value | Getter wire shape; unchanged after mutations/failures; rejects value |
| nextGrantId | Read-only store projection | Sequence 1/2/3, unchanged on failed/no-op calls; no ID reuse |
| treasuryBalance | Real current selfbalance | Deposits/payments; nonzero environment balance fixture; callback observes post-transfer balance |
| getGrant | Read-only copy; missing/reserved IDs return zero words | Seven flat outputs; full created/revoked/missing records; callback observes reserved spent |
| Fallback | Explicit nonpayable UnsupportedCall path | Empty, short, unknown selectors; nonpayable value rejection; no implicit deposit |

Known-selector truncated input and noncanonical address bits are tested through
the pinned compiler's ABI rejection. No application-error encoding is promised
for compiler-generated dispatch, decoding, or nonpayable failures.

## Independent sponsorship consumer

| Entry point | Boundary | Evidence |
| --- | --- | --- |
| Constructor | Creator from actual caller; evaluate_create validates operator/beneficiary/cap/expiry | Exact PolicyRejected codes 5/6/7; two independent campaigns; immutable creator getter |
| fund | Any sender, shared campaign lock, actual value | Positive Funded; zero no-event |
| sponsor | Actual operator, current locked Grant, same evaluate_spend, reserve/pay/emit | Wrong caller, contract operator, zero/cap/funding/expiry cases, exact events and real ETH, payment rejection/recovery |
| cancel | Actual creator, same evaluate_revoke, shared lock | Operator denied, creator allowed, inactive repeat no-event, later spending rejected |
| campaignSponsor/status | Read-only creator/full snapshot | Exact outputs and unchanged state after failures |
| Fallback | Explicit nonpayable UnsupportedCall | Empty calldata rejected; valid affordable sponsor/cancel calls reject attached value |

Sponsorship has four focused Fe EVM tests plus 32 Anvil transactions/15 rejection
checks. It does not duplicate the treasury's full adversarial callback matrix.

## Negative compilation and mutation controls

- Phase 0: mutable Budget forwarding allowed; read-only forwarding rejected.
- Phase 1: Wei amount accepted; Timestamp amount rejected.
- Phase 4: missing Call, missing mutable StorageMap, and read-only Grant assignment
  each produce exactly the expected sole diagnostic; matching controls execute.
- Phase 5: four seeded defects each compile, pass their unmodified baseline, and
  fail an existing targeted runtime test. No source-hash mismatch, compiler
  crash, setup failure, or timeout is counted as runtime defect detection.

See [mutation evidence](evidence/mutations.json) for exact patches, test-oracle
hashes, commands, checks, and outputs.

## Explicit untested combinations

The matrix does not establish correctness for every hostile recipient, gas
schedule, callback sequence, storage corruption, or arbitrary trusted provider.
Remaining gaps include actual forced-ETH opcode transfers (only a balance fixture
was used), exhaustive multi-grant/actor state sequences, every callback/payment-
failure combination, huge revert/return payload stress, systematic gas griefing,
multiple EVM clients/forks, real-chain fee/deployment behavior, and independent
human reproduction. MAX-ID allocation is tested in pure vectors, not by raw slot
injection or an infeasible count of on-chain creations. None is silently marked
as a completed check.
