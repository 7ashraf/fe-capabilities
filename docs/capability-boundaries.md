# Capabilities and trust boundaries

The reusable package computes decisions. Each application boundary validates
current state through that package and executes the result. Compiler-checked
access and runtime user authority are separate properties.

## Dependency table

| Component | Supplied data/effects | Can do through that interface | Execution responsibility |
| --- | --- | --- | --- |
| `validate_owner` | Ordinary Address | Validate nonzero owner | No storage or payment |
| `evaluate_create` | Owner, next ID, request; read-only PolicyContext | Propose initialized grant and next ID | Host must persist only the current result |
| `evaluate_revoke` | Owner, ID, grant; read-only PolicyContext | Decide deactivate versus inactive no-op | Host must write/emit under lock |
| `evaluate_spend` | ID, Grant, Wei; read-only PolicyContext | Validate domain policy and compute checked new spent | Host must reserve/pay/emit atomically |
| Treasury boundary | Real Ctx, Call, Log, private mutable Mutex of next-ID/map state | Dispatch, load/persist, pay fixed recipients, emit, lock | Trusted runtime authority and current-state binding |
| Sponsorship boundary | Real Ctx, Call, Log, private mutable Mutex of one Grant | Fund/cancel/sponsor one campaign | Same trusted execution obligations, different application ABI |
| Thin Python runners | Compiler processes, files, local RPC | Encode fixtures, execute tests, preserve raw results | No production policy decisions or on-chain authority |

`Wei`, `Timestamp`, `GrantId`, and ordinary Grant snapshots are values, not
ambient execution capabilities. A read-only access restricts writes through that
access; a local mutable copy can still be changed. Constructing or copying a
SpendDecision is not authority to move real ETH. No application API accepts a
previously approved decision for later execution.

Both application manifests resolve to the same local `policy/` directory.
Neither consumer imports the other. Compiler metadata includes the same three
policy source contents and Keccak hashes; `toolchain.json` also pins their
SHA-256 digests and the unchanged ingot manifest. These are source identity
checks, not a claim that optimized machine code must be identical in two apps.

## External compile-fail proofs

[boundaries-v1.json](../tests/vectors/boundaries-v1.json) declares each expected
access change, diagnostic category, and stable message substring. Each fixture
is a separate ingot consuming the real public policy package. Its matching
positive source differs only in the declared access after formatting is
normalized. The runner checks that difference, executes the positive control,
and requires exactly one intended compiler error from the negative fixture.
Unexpected compilation success, a crash, additional errors, or a syntax/type
failure in place of the expected access diagnostic fails the runner.

| Pair | Allowed declaration | Rejected change | Intended diagnostic |
| --- | --- | --- | --- |
| Payment | Consumer requires read-only PolicyContext and mutable Call | Omit Call from that consumer, still call a payment helper | `8-0036`: missing Call required by pay |
| Store | Consumer requires read-only PolicyContext and mutable StorageMap of Grant | Omit that map, still call a persistence helper | `8-0036`: missing StorageMap required by persist |
| Grant write | Function receives mutable Grant effect | Receive read-only Grant, still assign spent | `8-0018`: immutable assignment |

The store fixture uses an application-owned consumer with a real stdlib
StorageMap bound from its test contract's storage field. This proves the effect
requirement for that safe persistence call; it does not expose or grant access
to TreasuryStore. The payment fixture has a real EVM positive control that
transfers ETH. The write fixture intentionally resets a local Grant when given
mutable access: permitted code access alone says nothing about whether a user
was authorized to reset a budget.

These three proofs supplement Phase 0's read-only Budget forwarding rejection
and Phase 1's Timestamp-versus-Wei type mismatch. Run them separately from the
passing runtime suite with `python3 scripts/verify-boundaries.py`. A broad
`fe test tests` includes deliberate compiler failures and is not the test entry
point documented for this project.

## Exact limit of the claims

The proofs apply to the submitted safe consumer functions and explicit
interfaces. They do not sandbox arbitrary hostile code or prevent a trusted
host from supplying a broader provider elsewhere. Builtin EVM effects and
unsafe stdlib internals remain trusted. The policy API itself exposes no global
mutable store, payment method, or unforgeable bearer credential.

Production context comes from actual Ctx, not public caller/time/balance
arguments. The trusted adapter must load the correct current record while
holding its shared lock, evaluate it, persist the proposed transition, end
mutable projections, pay the stored recipient, emit, and unlock. EVM revert
restores failure state; an Err value from a pure function does not perform
rollback. Existing runtime tests establish the listed authority/payment cases,
while the compile-fail cases establish their narrower code-access properties.

See [policy API](policy-api.md), [treasury spending results](phase3.md), and
[sponsorship example](../examples/sponsorship/README.md). Phase 5 [internal review and defect-detection measurements](phase5.md) are
recorded. Independent developer feedback remains pending.
