# capabilities_policy 0.1.0

A reusable Fe ingot for pure grant creation, revocation, and bounded ETH-spending
decisions. The same package is consumed by the multi-grant treasury and the
single-campaign sponsorship example. Domain validation and checked budget math
live here; storage, actual context construction, payment, events, and rollback
belong to each trusted EVM boundary.

The public exports are `GrantId`, `Grant`, `GrantRequest`, `PolicyContext`,
`PolicyError`, `SpendDecision`, `CreateDecision`, `validate_owner`,
`evaluate_create`, `evaluate_revoke`, and `evaluate_spend`.
The evaluators require a read-only application-owned context; no evaluator
requires Call, Log, a mutable grant store, or a mutable context.
`evaluate_spend` includes the checked budget transition, so consumers do not
need to duplicate or import the Phase 0 spike's mutable reserve demonstration.

See [the API and trust notes](../docs/policy-api.md) and
[the capability/dependency table](../docs/capability-boundaries.md).

## Depend on this package

The actual in-repository manifests are:

```toml
# treasury/fe.toml
[dependencies]
capabilities = { path = "../policy" }
```

```toml
# examples/sponsorship/fe.toml
[dependencies]
capabilities = { path = "../../policy" }
```

Consumers import the alias, for example:

```fe
use capabilities::{GrantId, PolicyContext, evaluate_spend}
```

No registry installation or unpublished remote is required. Both examples work
from one independent checkout of this repository. Once using a remote git
source, pin the full repository commit and the `policy` ingot path; a release tag
alone is not an exact revision pin. No external dependency is added by this
package; core/std come from the pinned Fe compiler.

## Verify reuse

From the repository root, with Python 3.11+ and the pinned Fe/Foundry tools:

```sh
python3 scripts/verify-reuse.py
python3 scripts/verify-policy.py
```

The reuse runner compares both compiler metadata inputs against the same source
files and hashes recorded in `toolchain.json`. It also checks the manifest paths,
executes both consumers' runtime tests, and verifies the external access pairs.
The source and ingot manifest are unchanged from the policy introduced in commit
`6a4fa0629d9432eb522b49f6cb121cd7e820a7d6`; Phase 4 adds packaging documentation,
a second consumer, and evidence without changing its core.

A Grant or decision is ordinary constructible data. It is not an unforgeable
permission object. Use the current stored grant and real context within the
protected invocation, then apply and execute the decision immediately. Do not
cache a decision or accept user-supplied caller/time/balance as runtime authority.
