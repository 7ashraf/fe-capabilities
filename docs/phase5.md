# Phase 5 — adversarial review and evidence

**Technical work completed locally on 14 November 2026. Full phase pending
independent developer feedback (or an explicit owner waiver).** The local review,
mutation tests, and implementing agent's fresh-checkout checks are not outside
feedback. See [reviewer-feedback.md](reviewer-feedback.md) for the outstanding
record and concrete handoff instructions.

## Deliverables

- [Invariant/entry-point matrix](test-matrix.md), including all ten treasury
  invariants, each treasury and sponsorship entry point, and explicit gaps.
- [Threat/assumption and review notes](threat-model.md) with two closed coverage
  gaps and the limits of safe-code, provider, gas, timestamp, and balance claims.
- Four [mutation recipes](../tests/vectors/mutations-v1.json), a temporary-copy
  runner, and [exact controls/patches/results](evidence/mutations.json).
- A focused cross-grant callback Fe test and
  [mined expiry/cross-grant transaction evidence](evidence/adversarial-review.json).
- An eight-step [demo command](../scripts/demo.py) and
  [raw demo evidence](evidence/demo.json).
- An independent feedback template and a local history-preserving Git bundle.

Optional Compatibility/Replay integrations remain deferred; the core and both
consumers already run independently of those sibling projects.

## Reproduce technical checks

From this repository root with Python 3.11+ and pinned Fe/Foundry available:

```sh
python3 scripts/verify-review.py
```

The runner includes both consumers, the shared source check, external access
pairs, 70 pure vectors on each backend, Phase 0 checks, the four mutants, focused
Anvil review, and the short demo. `FE_BIN` can point to an existing compiler.
It reports technical success separately from the pending human review task.

Refresh Phase 5 raw evidence with:

```sh
python3 scripts/verify-review.py --record-dir docs/evidence
```

## Seeded defects

| Seeded change | Existing targeted test | Unmodified control | Mutant compilation | Mutant runtime |
| --- | --- | --- | --- | --- |
| Remove remaining-cap rejection | `one_over_remaining` golden vector | 1 passed | Passed | 1 failed |
| Change now >= expiry to now > expiry | `expiry_equal_now` golden vector | 1 passed | Passed | 1 failed |
| Remove delegate caller check | `wrong_caller` golden vector | 1 passed | Passed | 1 failed |
| Remove successful treasury spend unlock | `two_same_transaction_spends_transfer_and_account_once_each` | 1 passed | Passed | 1 failed |

**Result: 4/4 selected defects detected, 0 survived.** This is sensitivity to
four hand-selected defects, not an overall defect-detection rate or coverage
percentage. Golden expectations and test bodies were unchanged between each
control and mutant. Hashes, actual outputs, exact commands, and patches are
recorded. All use Sonatina, optimization 1, pinned Fe 26.5.0.

For each case the runner copies the source into a fresh temporary directory,
requires one unambiguous mutation anchor, checks an unmodified control, applies
one patch, requires that the mutant still type-checks, and requires the selected
runtime test to fail with the expected one-test summary. Compile errors, backend
crashes, setup failures, unmatched filters, and timeouts cannot count as detections.
The production working tree is never patched and its source hashes are checked
unchanged at the end. Policy source-identity guards are not used as the failure
oracle; direct existing runtime tests detect the altered behavior.

## Review additions

Spending now has 12 passing Fe EVM tests (the Phase 3 historical record had 11).
The new test executes grant 1 while the authorized recipient tries grant 2. It
requires the callback to observe exactly Reentrant, keeps grant 2 untouched,
and preserves outer grant/accounting/ETH.

The focused Anvil review submits 15 transactions. Its recorded headers prove
that a spend mined at expiresAt-1 succeeds and spends mined at exactly expiresAt
and expiresAt+1 fail, with no committed logs or changed balances/accounting.
The latest-block equality eth_call additionally verifies the exact Expired payload.
The cross-grant scenario then proves two normal grant-2 payments work in one
later transaction, with exact successive Spent data and a shared final balance.

The complete regression still passes: 6 administration tests, 12 spending tests,
4 sponsorship tests, all 3 new external positive/negative pairs, full treasury
ABI, sponsorship ABI, identical compiler policy inputs, both 70-vector backends,
Phase 0 tests, and all local transaction scenarios.

## Reproducible demo

```sh
python3 scripts/demo.py
```

The command verifies the compiler and builds current artifacts itself. It starts
its own loopback-only Osaka chain, uses test accounts, and stops the chain on exit.
Its 16 submitted transactions demonstrate:

1. Fund 100 wei.
2. Create a fixed-recipient 10-wei grant for a distinct delegate.
3. Pay 4 wei successfully.
4. Reject 7 wei when only 6 remain.
5. Reject an unapproved account.
6. Revoke the grant and reject the old delegate.
7. Reject authorized recipient reentry while committing only the outer payment.
8. Complete two later valid payments in one transaction after explicit unlock.

Every printed outcome follows actual assertions about error bytes, balances,
grant state, callbacks, or receipt logs. This is a local demonstration, not a
hosted deployment, benchmark, audit, or claim of production readiness.

## Outstanding gate

The planned outside developer must run the package and explain the boundaries
back. No feedback has been received or invented. The local review bundle is
ready for the user to hand off; it preserves main's commit history. Record actual
feedback and address findings in `reviewer-feedback.md`, or obtain an explicit
owner waiver of that task, before marking the full phase complete.
On 15 November 2026 the owner authorized Phase 6 preparation in parallel,
without waiving outside feedback. See [the local handoff](phase6.md).
