# Pure policy API (Phase 1)

Status: tested with Fe 26.5.0 on Sonatina and native backends. The ingot is
`policy/`, named `capabilities_policy`. It uses compiler-bundled stdlib value
types without requiring EVM execution effects. No external dependency, raw
storage, unsafe code, RPC, or payment operation occurs inside the pure policy.

## Inputs and results

| Type | Meaning |
| --- | --- |
| `GrantId` | Distinct identifier wrapper; `from_word`/`word` explicitly cross the ABI boundary. Zero and MAX are never allocated. |
| `Grant` | Read-only snapshot with explicit exists bit, delegate, recipient, `Wei` cap/spent, `Timestamp` expiry, active flag. |
| `GrantRequest` | Proposed delegate, recipient, cap, expiry. |
| `PolicyContext` | Application-owned effect: actual caller address, current timestamp, available `Wei`. |
| `PolicyError` | Exact error category; ABI payloads are constructed later by the adapter using the same snapshot. |
| `SpendDecision` | Fixed recipient, amount, and new spent value; no input mutation. |
| `CreateDecision` | Allocated ID, next ID, initialized grant; no store write. |

```fe
use capabilities_policy::{PolicyContext, evaluate_spend}

// In a trusted caller with id, grant, amount, caller, now, available already bound:
let context = PolicyContext::new(caller: caller, now: now, available: available)
with (context) {
    let result = evaluate_spend(id: id, grant: grant, amount: amount)
    // Handle Ok/Err. Do not cache a decision for a later operation.
}
```

The snippet illustrates API shape; its actual external consumer is the generated
Fe vector ingot from `scripts/verify-policy.py`. Every vector supplies an explicit
context, avoiding fake implementations of the stdlib's sealed `Ctx` trait.

| Function | Result | Dependencies |
| --- | --- | --- |
| `validate_owner(owner)` | `Result<PolicyError, ()>` | ordinary address |
| `evaluate_create(owner, next_id, request)` | `Result<PolicyError, CreateDecision>` | read-only `PolicyContext` |
| `evaluate_revoke(owner, id, grant)` | `Result<PolicyError, bool>` | read-only `PolicyContext`; true means deactivate/emit, false means successful inactive no-op |
| `evaluate_spend(id, grant, amount)` | `Result<PolicyError, SpendDecision>` | read-only `PolicyContext` |

Fe's `Result<Error, Value>` is error-first. No evaluator mutates grants, context,
requests, or IDs on either success or rejection. Do not confuse this with EVM
rollback: it is a pure computation that proposes a transition. `Grant` is a
copyable value snapshot, not an alias to a live storage resource.

`GrantId::from_word` does not establish existence or authority. Domain evaluators
reject reserved IDs at use. Public data and decisions are constructible values,
not unforgeable credentials. The trusted adapter must load the correct record
and build context from real `Ctx` under the shared lock immediately before
execution, then apply the proposed update, pay, emit, and unlock atomically.

## Budget arithmetic

Spend first checks a valid record (`spent <= cap`, positive cap, valid addresses),
then compares amount to `cap - spent`. Only after passing that check does it add
amount to spent. The addition cannot exceed cap or the `u256` maximum. Available
balance is checked last, so insufficient funds cannot hide a cap violation.

A corrupted record produces `InvalidGrantState`, without subtraction underflow.
Revocation deliberately does not require a valid budget, allowing an authorized
owner to deactivate a corrupted or expired record. Creation reserves MAX as the
next-ID exhaustion sentinel; the final allocatable ID is MAX-1.

## Golden vectors and provenance

[policy-v1.json](../tests/vectors/policy-v1.json) contains explicit input snapshots
and expected results authored from the written specification. Every quantity is
a decimal string to preserve full 256-bit precision. Actor words 1–4 denote
owner, delegate, recipient, and stranger; no real account is required.

The host script validates literal ranges and renders Fe tests; it does not decide
whether a spend/create/revoke succeeds or calculate expected new spent values.
Expected values are committed in the JSON. Generated files go in ignored
`.tools/policy-vectors/`, an external consumer with a relative dependency on
`policy/`. Tests compare all result fields and confirm every input field still
matches its literal original value, on success and error alike.

Run `python3 scripts/verify-policy.py`. It checks the compiler digest/version,
type-checks and formats the library, and runs the same vectors with both
`--backend sonatina -O 1` and `--backend native -O 1`.

A first manifest experiment using an absolute local dependency path was rejected
by Fe 26.5.0 before code compilation (`Invalid fe.toml ... dependency ... invalid
path`). The minimal fix is the supported relative path `../../policy` in the
generated consumer's manifest; no compiler upgrade or policy change was used.

## Remaining boundaries

The spec and [target ABI](../spec/treasury-v0.abi.json) are frozen design inputs.
The full treasury ABI is now emitted and compared against this target. Policy
categories map to the exact errors/payloads in [treasury-v0.md](../spec/treasury-v0.md).
The [Phase 3 EVM adapter](phase3.md) now implements storage existence, ID
allocation, current context binding, the full ABI/events, payment composition,
and the documented callback behavior. Broader reuse and external boundary
proofs remain Phase 4 work. Phase 0 proves the payment primitive separately; it does not
prove the full composition. Reusable consumer and adversarial coverage remain
later plan gates.
