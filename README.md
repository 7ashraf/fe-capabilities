# Fe Capabilities

Reusable Fe policy for limited ETH spending: a delegate pays one fixed recipient
within a lifetime cap, before an exclusive expiry, until the owner revokes the
grant. The treasury binds that pure policy to current EVM context, persistent
grants, a shared reentrancy lock, atomic payments, and typed errors/events.
A separate sponsorship application imports the same unchanged policy package.

The implementation and local handoff are prepared. Independent developer feedback
remains pending; this has not been represented as an audit or a review waiver.

## Quick start

Requires Python 3.11+, Fe 26.5.0, and Anvil/Cast 1.5.1-stable at commit
`b0a9dd9ceda36f63e2326ce530c10e6916f4b8a2`. The complete native/EVM suite requires
macOS arm64 or Linux amd64; this handoff was executed on macOS arm64.
See [setup and troubleshooting](docs/setup.md) for exact tool selection.

From this repository root:

```sh
python3 scripts/bootstrap-fe.py
source scripts/env.sh
python3 scripts/doctor.py
python3 scripts/demo.py
python3 scripts/verify-handoff.py
```

The bootstrap verifies the compiler digest and reuses a matching local binary.
An existing release can instead be selected with an absolute `FE_BIN` path.
No pip/npm install, Solidity compiler, public RPC, funded wallet, or sibling
project checkout is needed. Temporary local Anvil chains are stopped afterward.

The demo creates a grant, makes an allowed payment, rejects overspending,
an unapproved caller, and a revoked grant, then demonstrates blocked reentry
and two later valid payments in one transaction. Each outcome is asserted
against real local EVM execution.

## Supported behavior

| Area | Behavior/evidence |
| --- | --- |
| Permission | Immutable nonzero owner; distinct stored delegates and fixed recipients |
| Grant lifecycle | Explicit existence, monotonic IDs, permanent revocation, repeat-revoke no-op |
| Spending | Positive amount, exclusive expiry, checked remaining cap, actual ETH balance |
| Payment | Reserve before call; failure restores accounting, value, lock, and logs |
| Reentrancy | One lock covers all mutations and grants; documented callback getter view |
| Reuse | Treasury and sponsorship compile identical policy source inputs |
| Code access | External missing-payment/store and read-only-write fixtures reject; matching controls execute |

The full [treasury specification](spec/treasury-v0.md) and
[target ABI](spec/treasury-v0.abi.json) are implemented. Read the
[public policy API](docs/policy-api.md), [package usage](policy/README.md),
[capability/dependency table](docs/capability-boundaries.md), and
[sponsorship example](examples/sponsorship/README.md).

## Tests and evidence

`verify-handoff.py` checks prerequisites and frozen inputs, then runs both
consumers, full ABI/source identity checks, 70 vectors on each backend, external
positive/negative access pairs, prior reference tests, four isolated compiling
mutants, mined expiry/cross-grant checks, local transaction scenarios, and the
demo. Unexpected compiler/tool failures do not count as detected defects.

For focused work, use `verify-policy.py`, `verify-spending.py`, `verify-reuse.py`,
`verify-boundaries.py`, or `verify-mutations.py` under `scripts/`. A broad
`fe test tests` includes deliberate compiler failures and is not the test entry
point. Raw outputs and reviewed limits are in:

- [Invariant/entry-point matrix](docs/test-matrix.md) and [threat notes](docs/threat-model.md).
- [Phase 5 technical review](docs/phase5.md) and [Phase 6 handoff](docs/phase6.md).
- [Historical phase results](docs/feasibility.md), [pure policy](docs/phase1.md),
  [administration](docs/phase2.md), [spending](docs/phase3.md), and [reuse](docs/phase4.md).
- [Independent feedback status/template](docs/reviewer-feedback.md).

## Trust and limits

Policy data and decisions are constructible values, not unforgeable credentials.
The trusted EVM boundary must bind current caller/state/time/balance under its
lock and execute the resulting transition immediately. Compile-time access does
not sandbox arbitrary trusted providers. No application unsafe code is used;
compiler-bundled stdlib and EVM internals remain trusted.

Recipient gas is requested at 100,000. The project is pinned to Osaka, with no
cross-client or universal gas-behavior claim. The matrix records untested cases.
The sponsorship example has no refund/withdrawal or operator rotation. Independent
human feedback and a professional audit are absent; local test results do not
claim production readiness.

## License, provenance, and handoff

Project-authored work is [MIT licensed](LICENSE). [NOTICE.md](NOTICE.md) records
supplied plans/examples, compiler-generated scaffolding, upstream Fe primitives,
licenses, and Codex assistance. `spike/` remains separate feasibility evidence;
the reusable implementation is in `policy/` and its two consumers.

This directory is an independent Git repository. Preserve its existing branch
history when assigning its own remote and pushing. The local handoff command:

```sh
python3 scripts/package-handoff.py
```

requires a clean committed tree and creates a full-history Git bundle, checksum,
and exact-commit manifest in ignored `.tools/`. Follow
[handoff instructions](docs/handoff.md) to clone, run, and verify that artifact.
No outside review has been claimed; it remains an outstanding handoff item.
