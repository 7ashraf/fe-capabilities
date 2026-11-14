# Phase 4 — reusable package and independent consumer

Status: completed locally on 14 November 2026 with Fe 26.5.0 and the pinned
Foundry tools. Policy source and ingot configuration are unchanged from the
package introduced at commit `6a4fa0629d9432eb522b49f6cb121cd7e820a7d6`.

## Deliverables

- [Package instructions](../policy/README.md) for the public `capabilities_policy`
  ingot and the same checked budget/policy decisions used by both applications.
- [Sponsorship](../examples/sponsorship/README.md), a fixed single campaign that
  imports only the shared package, not the treasury or a copy of its core logic.
- Three external access-boundary pairs, a diagnostic-aware runner, and
  [fixture expectations](../tests/vectors/boundaries-v1.json).
- [Capability/dependency table](capability-boundaries.md) distinguishing safe code
  access, runtime authority, trusted providers, and ordinary decision values.
- Raw [boundary diagnostics](evidence/boundaries.json),
  [shared compiler source inputs](evidence/shared-policy.json), and
  [sponsorship transactions](evidence/anvil-sponsorship.json).

## Reproduce

From this standalone repository root, with Python 3.11+, pinned Fe, and Foundry:

```sh
python3 scripts/verify-reuse.py
python3 scripts/verify-policy.py
python3 scripts/verify-phase0.py
```

To refresh Phase 4 evidence, use:

```sh
python3 scripts/verify-reuse.py --record-dir docs/evidence
```

The reuse runner verifies external positive/negative controls, runs the complete
treasury spending/administration checks, builds/tests the independent consumer,
checks its ABI snapshot, compares actual compiler metadata source inputs, and
runs local Anvil sponsorship transactions. It does not change the library or
move the core policy into a host script. Both consumers compile from the same
checkout; no sibling repository, published package, or network service is needed.

## Checks and outcomes

| Check | Result |
| --- | --- |
| Public package source/config hashes | Matched pinned SHA-256 values; no core changes |
| Both manifests and compiler source inputs | Same package version, actual directory, source contents, and compiler Keccak hashes |
| Missing payment effect | Sole expected `error[8-0036]`, Call required by pay |
| Missing persistence effect | Sole expected `error[8-0036]`, StorageMap required by persist |
| Read-only grant assignment | Sole expected `error[8-0018]`, immutable assignment |
| Matching positive controls | All three compiled and passed their EVM runtime tests |
| Sponsorship formatting/type check | Passed |
| `fe test tests/runtime/sponsorship --backend sonatina -O 1` | 4 passed, 0 failed |
| Sponsorship and Receiver release builds | Passed, optimization 1 |
| Sponsorship emitted ABI snapshot | Matched |
| Anvil sponsorship | 32 submitted transactions, 15 rejection checks; all assertions passed |
| Treasury regression included in reuse runner | 6 administration tests, 11 spending tests, full ABI and both Anvil scenarios passed |
| Pure policy regression | 70 explicit vectors on each of Sonatina/native; typed-amount negative passed |
| Phase 0 regression | Reference/access/payment/build/local transaction checks passed |

The four sponsorship EVM tests establish two same-transaction payments and
isolation between campaigns; exact funding/zero/cap error codes; distinct actual
operator and creator authority (including a contract operator); cancellation and
repeat cancellation; and payment rollback followed by same-transaction recovery.

The separate Anvil scenario uses distinct creator, operator, beneficiary, and
funder accounts. It checks constructor rejections, actual ETH transfers, exact
Funded/Sponsored/Cancelled logs, permanent cancellation and its no-op repeat,
independent campaign state, exclusive expiry using actual block time, and
recipient rejection followed by a later successful transaction. Valid affordable
sponsorship/cancellation calls carrying forbidden transaction value are rejected.
Every rejected call preserves observed status, creator, campaign balance, and
beneficiary balance. Failed submitted transactions have no committed logs.

## Reuse and boundary interpretation

The package's public evaluator computes each proposed transition. Sponsorship
binds current EVM context and one guarded Grant, while the treasury binds a
private grant map and ID allocator. Their ABIs and storage differ; matching
policy inputs are demonstrated by compiler metadata, not by asserting equivalent
application behavior or identical machine code. The sponsorship error-code
mapper translates categories and contains no policy checks or budget math.

The external store fixture supplies a mutable stdlib StorageMap from its own
contract storage in the positive control, and omits that effect in the negative
consumer. It does not obtain the treasury's private store. The payment fixture's
positive control transfers ETH; omitting its Call dependency causes the intended
compiler rejection. Read-only grant code cannot assign through that access,
while the matching mutable control intentionally can.

These proofs concern explicit dependencies in submitted safe code, not a
sandbox against arbitrary trusted providers or edited hosts. Runtime authority
still depends on actual caller/state/context binding. Copyable data and decisions
remain forgeable values, not credentials. Full limits and component dependencies
are documented in the capability table.

## Remaining work

The small sponsorship example uses local test ETH and has no refund/withdrawal
path or operator rotation. Its focused tests are not a duplicate of every
adversarial treasury callback test. Neither application is claimed audited or
formally verified.

Next is Phase 5: invariant/entry-point review, a threat and test matrix, seeded
defects demonstrating that cap removal, changed expiry equality, missing caller
checks, and forgotten unlocks are detected, a reproducible demo, and feedback
from an outside developer. No outside contact or feedback has been fabricated.
