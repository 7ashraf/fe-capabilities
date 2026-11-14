# Phase 2 — persistent storage and administration

Status: completed locally on 14 November 2026 with pinned Fe 26.5.0.
This is the historical Phase 2 record at commit `2dc30ad`; the full spending
adapter subsequently completed in [Phase 3](phase3.md).
`treasury/` is a deployable administrative contract using `policy/` as a relative
local dependency. Its six functions implement the administrative subset of the
frozen [treasury v0 specification](../spec/treasury-v0.md). Deposit and spend
remain unsupported until Phase 3; this phase does not expose no-op placeholders.

## Run

From this independent repository root, with the pinned compiler and Foundry:

```sh
python3 scripts/verify-administration.py
```

This verifies the compiler binary digest/version, checks formatting and types,
runs six EVM tests, builds release artifacts, compares the emitted ABI against
the frozen subset and its versioned snapshot, then starts a temporary loopback
Anvil Osaka process for real transactions. That process is always stopped.
`FE_BIN` may select an existing pinned compiler binary.

Refresh the raw local evidence with:

```sh
python3 scripts/verify-administration.py --record docs/evidence/anvil-administration.json
```

The actual emitted interface is recorded as
[treasury-admin-v1.abi.json](../spec/treasury-admin-v1.abi.json). It contains:

- Nonpayable constructor taking the explicit owner, and nonpayable fallback.
- `createGrant`, `revoke`, `owner`, `nextGrantId`, `treasuryBalance`, `getGrant`.
- `GrantCreated` and `GrantRevoked` events.
- Ten administration/dispatch errors from the full target ABI.

The target ABI comparison checks types, ordered outputs, mutability, indexed
fields, event anonymity, and error signatures. Argument/return labels are
metadata and do not change canonical encoding: the constructor's emitted input
is named `initial_owner` and tuple outputs are unnamed. The snapshot additionally
records those exact emitted labels. The current runner now validates the full
frozen treasury ABI and projects its administrative entries against this
historical snapshot, preserving the Phase 2 checks as deposit/spend are added.

## Storage boundary

The contract has an immutable, nonzero owner and a private
`Mutex<TreasuryStore>`. The store holds a `u256` next ID and
`StorageMap<u256, Grant>`. Grant values use the same typed snapshots as the pure
policy, including an explicit exists bit. No raw slots, unsafe code, public
state mutation helpers, or Solidity layout assumptions were introduced.

Creation/revocation acquire the same stdlib mutex, build `PolicyContext` from
actual `Ctx` values, call the unchanged pure evaluator, then persist a valid
transition and emit its event. Both success and no-op paths explicitly unlock.
A revert restores the accounting/lock state. Grant creation never transfers ETH
or reserves treasury funds. Contract owners are supported using actual caller
identity, without transaction-origin authority.

Unknown, zero, and reserved MAX IDs return seven zero ABI words. Revoked records
retain existence and all historical fields; only active becomes false. Their IDs
never become candidates for reallocation. Owner and all unrelated grants are
unchanged by revocation.

Administration makes no external calls. Adversarial payment callbacks and the
lock's composition with spending remain Phase 3 tests, not claims established
by this phase.

## Checks and results

| Check | Result |
| --- | --- |
| Compiler | `fe 26.5.0 (3dab95f)`, release digest verified |
| `fe check treasury` | Passed |
| `fe fmt treasury --check` | Passed |
| `fe fmt tests/runtime/administration --check` | Passed |
| `fe check tests/runtime/administration` | Passed |
| `fe test tests/runtime/administration --backend sonatina -O 1` | 6 passed, 0 failed |
| `fe build treasury --contract Treasury --backend sonatina --profile release -O 1 --emit bytecode,runtime-bytecode,abi,metadata` | Passed |
| Emitted ABI comparison | 6 functions, 2 events, 10 errors, constructor, fallback matched |
| Local Anvil administration | 32 submitted transactions; 27 expected RPC rejection checks; all assertions passed |
| Phase 1 regression | 70 vectors passed on Sonatina and native; unit-type negative passed |
| Phase 0 regression | Reference/access/payment/build/Anvil checks passed |

The six Fe tests establish:

1. Two distinct persistent records, independent fields including a MAX cap,
   repeated revocation, and a new third ID without reuse or revival. Multiple
   normal mutations in one test transaction also check explicit unlock.
2. Absent map entries read as missing, and feeding the actual loaded snapshot
   into the pure spending evaluator returns `UnknownGrant`, even with a zero
   caller/time context. This is not an integrated spend entry point yet.
3. Invalid delegate/recipient/cap/expiry yield the intended exact error shape,
   do not consume an ID, and permit a subsequent valid creation.
4. Unknown revocation returns the full `UnknownGrant(999)` error bytes and
   allows a later valid mutation in the same transaction after rollback.
5. A contract owner can create/revoke through its own call frame; the direct
   external caller receives `Unauthorized()` for both operations.
6. Zero owner deployment reverts with the exact `InvalidOwner()` selector.

## Raw transaction evidence

[anvil-administration.json](evidence/anvil-administration.json) contains raw
transactions, mined receipts, RPC error objects, bytecode file digests, and final
observations. Failed submitted transactions have status 0 and no committed logs.
Expected error checks compare exact bytes, including the unknown grant ID payload.

The runner verifies full seven-word records across separate mined transactions,
exact return bytes from observations, actual caller authority, and error
precedence for unauthorized unknown revocations. Every rejected call compares
owner, next ID, actual balance, and complete snapshots for IDs 0, 1, 2, 3, 999,
and MAX before and after. All of those observations remain unchanged.

`GrantCreated` logs must have topic0 for the canonical signature, indexed ID,
delegate and recipient in that order, and cap/expiry as data. Revocation must
emit only the expected indexed ID. A second revocation produces no log. Creating
the third grant leaves the first revoked record and the second active record
unchanged. IDs across those transactions are 1, 2, 3 and the final next ID is 4.

Additional RPC checks cover unknown/short/empty calldata, unsupported deposit
and spend selectors, nonpayable constructor/functions/fallback, truncated known
calldata, and noncanonical address encoding. Compiler dispatch/ABI rejections
are asserted to fail and preserve state; their error encoding is not classified
as an application policy error. Known unsupported zero-value calls return exactly
`UnsupportedCall()`.

A final `anvil_setBalance` fixture gives the treasury 55 wei to confirm that
`treasuryBalance()` reads actual EVM balance, without changing grant records.
This is explicitly an environment fixture, not a real transfer or deposit test.
No funded real account or external RPC is used. Final quantities in the evidence
are decimal strings, preserving full 256-bit precision.

## Source checks and implementation notes

Inspected the pinned stdlib's `StorageMap::get/set`, `Mutex::value/try_lock/unlock`,
`Ctx`, and `Log`, plus passing struct-map, mutex-map, and event fixtures. The
compiler and bundled stdlib remain at
`3dab95f8eebdccf9a2382bb59a33f7bbd03540ca`.

The initial adapter type check reported `error[8-0024]` for call argument label
mismatches. The minimal form is `validate_owner(initial_owner)` where the callee
requires label `owner`; it is corrected to `validate_owner(owner: initial_owner)`.
The same explicit labels fix the other reported calls. This was a call-site
syntax correction on the pinned compiler, not a toolchain or policy change.

## Next gate and limits

This completes Phase 2. The pure library's signatures/effects are unchanged.
Maximum-ID exhaustion remains covered by Phase 1's literal policy vectors;
no raw storage injection or infeasible run of 2^256 allocations is claimed here.
The contract has no owner rotation, allocator override, deletion, or upgrade path.

Phase 3 must add real deposit and protected spending against this same store
and mutex, bind context within the locked invocation, preserve exact error/event
payloads, prove atomic accounting/payment rollback, and exercise same-function
and cross-function hostile callbacks, getter observations, and later valid calls.
The full eight-function/four-event ABI is not implemented until that phase.
