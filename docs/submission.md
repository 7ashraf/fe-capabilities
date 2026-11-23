# Fe Capabilities submission

## One-sentence pitch

Fe Capabilities gives an ETH treasury narrowly scoped spending grants and
reuses the same Fe policy in a separate sponsorship contract.

## Fe-specific technical highlight

A pure Fe ingot returns typed policy decisions for a fixed recipient, lifetime
budget, expiry, and revocation. Fe effects and access modes make each component's
dependencies explicit. Compile-fail fixtures isolate missing payment or storage
access and read-only writes. The treasury separately binds the decision to
current EVM caller, time, and stored state, then reserves the budget and makes
the payment under a shared lock. The sponsorship example imports the same
policy sources.

## Reproducible demo

Use Python 3.11+, Git, curl, and Anvil/Cast 1.5.1-stable (commit
`b0a9dd9ceda36f63e2326ce530c10e6916f4b8a2`). Run these commands in Bash
or Zsh from the project root.

```sh
python3 scripts/bootstrap-fe.py
source scripts/env.sh
python3 scripts/doctor.py
python3 scripts/demo.py
python3 scripts/verify-handoff.py
```

The demo makes a payment on local Anvil and checks overspending, an unapproved
caller, revocation, and a reentrant callback. It also checks that two later
payments can succeed in one transaction. See [setup](setup.md) and
[handoff](handoff.md).

## Pre-existing work, reuse, and AI assistance

The supplied plans and reference examples are retained as historical inputs.
The initial scaffolding came from `fe new`. Compiler-bundled Fe core and std
supply ABI, EVM, storage, and locking primitives. Codex assisted with
implementation, testing, documentation, verification, and contest preparation.
The four mutation cases are deliberately seeded tests. See [NOTICE.md](../NOTICE.md).

## Release details

- **Exact Fe version:** `fe 26.5.0 (3dab95f)`, source commit
  `3dab95f8eebdccf9a2382bb59a33f7bbd03540ca`.
- **Manifests:** [policy](../policy/fe.toml), [treasury](../treasury/fe.toml),
  [sponsorship](../examples/sponsorship/fe.toml), and [toolchain](../toolchain.json).
- **License:** [MIT](../LICENSE). Use `git rev-parse HEAD` in the project
  checkout for the full commit SHA after publishing the candidate.
- **Limits:** The full suite was verified on macOS arm64 with the Osaka fork.
  The treasury handles ETH and fixed-recipient grants. The sponsorship example
  omits refunds, withdrawals, and operator rotation. The
  [threat model](threat-model.md) describes trusted inputs and untested cases.
  [Independent developer feedback](reviewer-feedback.md) remains pending.
