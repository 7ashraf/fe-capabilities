# Phase 0 feasibility

**Result: passed locally on 14 November 2026.** The exit gate has a real
compiler-enforced access boundary and actual ETH payment/rollback evidence.
This is the Phase 0 historical record. Phase 1 subsequently completed; see
[the policy milestone](phase1.md) for its results and
[the README](../README.md) for current progress. The original plan's earlier dates are historical;
this record reports the execution date.

## Reproduction

From this repository root, with the pinned compiler and Foundry available:

```sh
source scripts/env.sh
python3 scripts/verify-phase0.py
```

This single runner checks compiler version and SHA-256, formatting, reference
examples, the spike, the external access pair, a release build, and local Anvil
transactions. `FE_BIN=/absolute/path/to/fe` can select an existing compiler.
The intentionally failing fixture is run separately; do not use `fe test tests`
as an all-passing suite.

To refresh raw transaction evidence after building:

```sh
python3 scripts/anvil-payment.py --record docs/evidence/anvil-payment.json
```

The RPC runner starts its own loopback-only Anvil process on an ephemeral port,
uses that process's unlocked test accounts, and terminates it in a `finally`
block. No public RPC, funded account, Solidity compiler, or deployment service is
used. JSON quantities in the raw RPC receipts are hex strings; final wei amounts
are decimal strings. Bytecode digests hash the generated `.bin` files as stored.

## Toolchain and environment

- Fe: `fe 26.5.0 (3dab95f)`, full source commit
  `3dab95f8eebdccf9a2382bb59a33f7bbd03540ca`.
- Host: Darwin arm64; compiler release asset `fe_mac_arm64`, SHA-256
  `4968711c5bc02c1a3151cfaea0d81a48dc74803ea208362022af467c2a523fed`.
- Backend: Sonatina for EVM tests/build; native for the pure reference examples.
- Optimization: `-O 1`; test profile `test`, build profile `release`.
- Arithmetic: checked; emitted `PaymentProbe.metadata.json` confirms EVM Osaka.
- Foundry: `1.5.1-stable`, commit
  `b0a9dd9ceda36f63e2326ce530c10e6916f4b8a2`.
- Anvil: `--hardfork osaka`; local chain ID 31337.
- Dependencies: compiler-bundled core/std at the pinned release; no external ingots.
- Solidity: unused. RPC evidence schema: version 1.

Machine-readable pins: [toolchain.json](../toolchain.json).

## Exact checks and outcomes

All commands below ran successfully unless explicitly marked as expected failure.
The verification runner repeats them and checks the negative diagnostic.

| Command | Outcome |
| --- | --- |
| `fe --version` | `fe 26.5.0 (3dab95f)` |
| `fe check spike` | Passed |
| `fe fmt spike --check` | Passed |
| `fe fmt tests --check` | Passed |
| `fe test tests/reference/language_smoke.fe tests/reference/contract_smoke.fe -O 1` | 4 passed |
| `fe test tests/reference/language_smoke.fe --backend native -O 1` | 2 passed |
| `fe test spike --backend sonatina -O 1` | 4 passed |
| `fe check tests/compile_fail/allowed` | Passed |
| `fe test tests/compile_fail/allowed -O 1` | 1 passed |
| `fe check --color never tests/compile_fail/readonly` | Expected exit 1, exactly one diagnostic `error[8-0037]` |
| `fe build spike --backend sonatina --profile release -O 1 --emit bytecode,runtime-bytecode,abi,metadata` | Built all three Fe contracts |
| `python3 scripts/anvil-payment.py` | Passed all RPC assertions |

### Application-owned effect and access pair — tested

`reserve(amount)` requires `budget: mut Budget`; it rejects zero and amounts
above the remaining budget before mutation. Tests check the exact error variant,
unchanged rejected state, and exact-budget consumption.

The two external consumer ingots import the same implementation. Their source
files differ only by `mut` in the consumer's effect declaration:

```text
allowed:  fn consumer() uses (budget: mut Budget)
readonly: fn consumer() uses (budget: Budget)
```

The negative diagnostic is:

```text
error[8-0037]: effect `Budget` must be mutable when calling `reserve`
```

The runner rejects unexpected compilation success, a different diagnostic, or
additional diagnostics. Both consumers provide the same mutable local at the
call site; the negative consumer's own declared read-only boundary prevents it
from forwarding mutable access. Merely omitting `mut` from `with (budget)` on a
mutable local was experimentally accepted by this compiler and is not used as
evidence of a read-only boundary.

### ETH payment and rejection — tested

The Fe tests deploy `PaymentProbe` and accepting/rejecting recipients inside the
real EVM test backend. They verify actual balances, accounting, exact custom
error shapes, rollback, and transient-lock release across sequential calls in
one transaction. The rejecting recipient is first called directly and confirmed
to produce `RecipientRejected()`; deployment/setup failure cannot masquerade as
the expected payment rejection.

The [raw Anvil execution record](evidence/anvil-payment.json) additionally contains
submitted transactions and mined receipts, including a failed payment transaction
with status 0 and no logs. Independent RPC assertions establish:

- Deposit 100 wei, pay 7: recipient 7, probe 93, recorded paid 7.
- A different local sender gets exactly `Unauthorized()`; a submitted unauthorized
  transaction fails without changing those amounts.
- Zero payment gets exactly `InvalidAmount()`.
- A rejecting recipient gets no ETH; the probe returns exactly `PaymentFailed()`
  (4 bytes) and retains 100 wei with recorded paid 0.
- A later deposit to the failed probe works, leaving 101 wei.
- A later successful 3 wei payment leaves recipient 10, probe 90, recorded paid 10.

These are local test funds. Runtime authorization uses actual `Ctx::caller`,
not a caller field supplied as an argument.

## Source verification and decisions

Inspected source and passing fixtures at the pinned Fe commit before using the
payment APIs. Source links here are version-pinned:

- [Call/SendValue/CallOutcome/Ctx](https://github.com/argotorg/fe/blob/3dab95f8eebdccf9a2382bb59a33f7bbd03540ca/ingots/std/src/evm/effects.fe).
- [Mutex implementation](https://github.com/argotorg/fe/blob/3dab95f8eebdccf9a2382bb59a33f7bbd03540ca/ingots/std/src/evm/mutex.fe)
  and [passing reentrancy fixture](https://github.com/argotorg/fe/blob/3dab95f8eebdccf9a2382bb59a33f7bbd03540ca/crates/fe/tests/fixtures/fe_test/reentrancy_mutex.fe).
- [Wei/payment fixture](https://github.com/argotorg/fe/blob/3dab95f8eebdccf9a2382bb59a33f7bbd03540ca/crates/fe/tests/fixtures/fe_test/wei_units.fe),
  [fallback fixture](https://github.com/argotorg/fe/blob/3dab95f8eebdccf9a2382bb59a33f7bbd03540ca/crates/fe/tests/fixtures/fe_test/recv_fallback.fe),
  and [error helpers](https://github.com/argotorg/fe/blob/3dab95f8eebdccf9a2382bb59a33f7bbd03540ca/ingots/std/src/evm/returndata.fe).

Use a concrete application-owned budget effect for now. No generic framework or
custom mutex is required. `send_value` exposes failure without bubbling, and the
probe maps it to `PaymentFailed()`. It limits recipient gas to 100,000 for this
experiment; this is not a finalized treasury gas policy. Standard `Mutex<u256>`
guards payment accounting and deposit. Explicit unlock permits a second normal
payment in the same transaction; revert restores the failed operation's lock.
`peek()` can expose intermediate accounting during a callback; no stronger
callback-observation claim is made.

## Limitations and next gate

This completes Phase 0 only. The budget function and payment probe are separate
experiments. No grant store, expiry/delegate policy, final ABI/error precedence,
event contract, adversarial callback matrix, or second consumer is implemented.
The positive/negative proof concerns a safe consumer's declared access; trusted
providers remain part of the trust boundary. No application unsafe code was added.

Next is Phase 1: freeze `spec/treasury-v0.md`, validation precedence, events, and
ABI; implement pure grant policy with independent vectors for identity,
existence/active state, amount/cap bounds, and exclusive expiry. Later phases
must integrate the proven boundary and payment path and test their composition.
