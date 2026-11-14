# Fe Capabilities

Build reusable Fe policy components for limited ETH spending permissions, then
validate their composition in a treasury. Phases 0–4 are complete: narrow
access and real local payments are proven, and the pure grant policy passes
explicit boundary vectors on both EVM and native backends. Persistent grant
administration, deposits, and delegate spending now run together on the EVM,
with payment rollback and hostile callback checks. An independent sponsorship
consumer now uses the identical policy inputs, with external access proofs.

The [treasury specification](spec/treasury-v0.md) and
[target ABI](spec/treasury-v0.abi.json) are implemented by the treasury.
Read [the policy API](docs/policy-api.md), [Phase 1 results](docs/phase1.md),
[Phase 2 administration results](docs/phase2.md), and
[Phase 3 spending results](docs/phase3.md), and
[Phase 4 reuse results](docs/phase4.md).

## Run checks

Requires Python 3.11+, Fe 26.5.0, and Foundry 1.5.1-stable at commit
`b0a9dd9ceda36f63e2326ce530c10e6916f4b8a2` (`anvil` and `cast` on PATH).

From this repository root:

```sh
python3 scripts/bootstrap-fe.py
source scripts/env.sh
python3 scripts/verify-reuse.py
python3 scripts/verify-policy.py
python3 scripts/verify-phase0.py
```

If the pinned compiler is already installed, set `FE_BIN` to its absolute path
instead of downloading again. The runner verifies its binary digest and version.
The reuse runner checks both consumers and their compiler policy inputs, runs
three new compile-fail pairs and positive controls, and includes the spending
runner. The spending runner includes administration checks and validates the full ABI,
real transfers, exact events/errors, rollback, and hostile callbacks.
The policy runner executes 70 explicit vectors on each backend and rejects timestamps passed as payment
amounts. The Phase 0 runner executes reference
examples, budget and payment tests, expected compilation failure, release build,
and a fresh local Anvil Osaka chain. It stops that chain
after checking real transaction receipts, balances, accounting, and error bytes.

| Demonstrated boundary | Evidence |
| --- | --- |
| Code access | External pairs reject missing payment/store effects and read-only Grant mutation; matching positive controls compile and execute. |
| Runtime authority | Treasury administration binds actual `Ctx::caller`; unapproved callers fail, while a contract owner can create/revoke. |
| Persistence | Revoked records retain their ID and fields; later creation does not revive them or corrupt another grant. |
| Payment and rollback | The treasury transfers ETH only under current grant policy; rejecting recipients and failed callbacks roll back accounting, balances, and logs. |
| Shared lock | Authorized callback mutations fail with `Reentrant()`; later valid calls in the same transaction still work. |

## Scope and trust

`spike/` is a feasibility ingot, not the finished treasury library.
`reserve` uses a concrete application-owned mutable budget effect and has no EVM
dependency. `PaymentProbe` is a separate experiment using actual EVM context,
a fixed recipient, and the standard library's transient mutex.
`policy/` holds the tested pure grant policy with read-only context and typed
amount/time/identifier values. It returns proposed transitions without mutation.
`treasury/` binds that policy to current EVM context, a private persistent grant
store, and one shared mutex for every mutation. The full eight-function ABI is
deployed and tested locally, including ETH payments and exclusive expiry.

`examples/sponsorship/` imports the same package for a fixed campaign with
creator cancellation, an operator, and a fixed beneficiary. Its core policy is
not copied. See [package usage](policy/README.md) and
[the capability table](docs/capability-boundaries.md).

The trusted boundary assembles capabilities and checks runtime authority. This
does not sandbox hostile trusted code. Independent adversarial review, seeded-defect detection, and a security audit
remain incomplete. Callback tests cover the modes
listed in Phase 3 results; they are not a proof against every hostile program.
No application unsafe code was introduced. The pinned stdlib supplies EVM internals.

Read [the feasibility evidence](docs/feasibility.md),
[the implementation plan](docs/reference/FE_CAPABILITIES_PLAN.md), and
[the language reference](docs/reference/FE_AGENT_REFERENCE.md).
Next: Phase 5, review invariants, verify tests against seeded defects, prepare
a reproducible demo, and collect independent developer feedback.

## Repository and provenance

This directory is an independent Git repository. Make implementation commits here
and push its existing `main` branch to this project's remote to retain history.
Setup scripts, toolchain pins, and references are included for separate checkouts.
No remote is configured yet.

`tests/reference/` reproduces section 20 of the supplied agent reference;
`docs/reference/` preserves the supplied planning material. The initial ingot was
generated by `fe new` and its counter was replaced with this feasibility spike.
The policy, treasury, spike, test fixtures, runners, and documentation were
developed with Codex assistance.
