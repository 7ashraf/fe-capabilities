# Phase 1 — specification and pure policy

Status: completed locally on 14 November 2026 with Fe 26.5.0 at commit
`3dab95f8eebdccf9a2382bb59a33f7bbd03540ca`. This is a pure policy milestone;
the grant treasury was not deployed or integrated at this milestone.
Phase 2 subsequently completed; see [administration results](phase2.md).

## Deliverables

- [Treasury v0 revision 1](../spec/treasury-v0.md) freezes operation semantics,
  validation precedence, canonical ABI, custom-error payloads, and event fields.
- [Target ABI](../spec/treasury-v0.abi.json) provides a machine-readable interface
  for the future storage/EVM adapter.
- [Policy ingot](../policy/src/lib.fe) implements owner validation, creation,
  revocation, and spending decisions with a read-only application-owned context.
- [API notes](policy-api.md) explain value types, trust assumptions, and execution
  obligations. No unsafe code or mutable storage/payment effect is used here.
- [Golden corpus](../tests/vectors/policy-v1.json) contains 70 explicit input and
  expected-output records: 38 spend, 19 create, 11 revoke, 2 owner.

## Verification

Run from the project root with the pinned compiler installed:

```sh
python3 scripts/verify-policy.py
python3 scripts/verify-phase0.py
cast interface spec/treasury-v0.abi.json
```

`FE_BIN` may point to an existing release binary; both runners verify its digest
and version. All quantities in the JSON are decimal strings. Tests are rendered
into an ignored external-consumer ingot and compiled into Fe. The Python host
contains no policy decision logic or expected-result arithmetic. The expected
values in the committed corpus were authored from the specification.

| Check | Result |
| --- | --- |
| `fe check policy` | Passed |
| `fe fmt policy --check` | Passed |
| Formatting/type-check of the valid unit consumer | Passed |
| Timestamp used as amount | Expected exit 1, exactly `error[8-0000]`, expected Wei but Timestamp given |
| Generated consumer `fe check` | Passed |
| 70 vectors, `fe test ... --backend sonatina -O 1` | 70 passed, 0 failed |
| Same vectors, `fe test ... --backend native -O 1` | 70 passed, 0 failed |
| Phase 0 regression command | Passed: reference examples, narrow mutable access pair, payment tests, release build, Anvil transactions |
| `cast interface spec/treasury-v0.abi.json` | Parsed target ABI successfully; no Solidity compiler invoked |

Compiler settings, release hashes, and Foundry version are pinned in
[toolchain.json](../toolchain.json). Backend profiles remain `test`, optimization
1, checked arithmetic; EVM execution is Osaka. No external ingot dependency was
added. The ABI file is a frozen target, not a claim of generated adapter coverage.

## Exit gate coverage

The vectors assert exact success fields or the intended error category. On both
success and rejection they check every input grant, context, request, and ID
field against its original literal value. Important cases include:

- Zero amount, exact remaining budget, one over, exhausted budget, full MAX cap,
  final wei at MAX, and an overflow attempt rejected before addition.
- Expiry before/equal/after now and maximum timestamps without unchecked math.
- Wrong caller, missing grant, inactive grant, zero-map entry, and corrupt records.
- Zero and reserved MAX IDs are unknown; MAX-1 is usable. Creation can allocate
  MAX-1 and return the MAX exhaustion sentinel, but never wrap or allocate zero.
- Exact/insufficient balance, including cap failure winning over funding failure.
- Multiple simultaneous violations to freeze authority/existence/active/amount/
  expiry/record/cap/balance precedence.
- Invalid creation owner/addresses/cap/expiry and exhausted ID; successful grants
  initialize exists/active true and spent zero.
- Repeat-revocation no-op, unknown and unauthorized revocation, and revocation
  of an expired or budget-corrupted grant.

The external unit pair proves a `Timestamp` cannot be passed as a `Wei` amount.
The matching successful consumer differs only in that argument expression;
formatting differences are normalized by the runner before comparison. This is
a unit-type check, separate from Phase 0's effect mutability boundary.

## Decisions and remaining work

Return a proposed transition instead of mutating and returning `Err`. Use the
actual context only at the trusted EVM boundary; pure tests construct it
explicitly. Do not treat a `SpendDecision` as reusable authority.

Events and exact ABI payloads are specified here but require execution tests in
the adapter. No persistence, ID allocator, ABI/event emission, full payment-policy
composition, or hostile callback matrix has been implemented in this phase.

Next gate is Phase 2: persistent storage and administration, immutable validated
owner, monotonic IDs, create/revoke/observe handlers, actual ABI/events, missing
record safety, and isolation between grants. Integrate spending/payment in Phase 3.
