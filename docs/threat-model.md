# Threat model and engineering review notes

Scope: the ETH-only treasury, its pure policy package, and the small sponsorship
consumer at the pinned Fe/Osaka baseline. This is a Codex-assisted internal
engineering pass. The same development workflow authored code and tests;
independent developer feedback remains pending. It is not a professional audit
or formal verification.

## Assets, actors, and authority

The treasury holds ETH and persistent grant records. Its owner can create and
revoke permissions, including grants to malicious contracts, but cannot spend
under a grant unless also its delegate. A delegate may request a positive amount
only within the current active, unexpired grant's remaining cap and actual funds.
Payments go to that grant's fixed recipient. Any sender can explicitly deposit.

The owner is intentionally trusted for administration, not assumed benevolent.
There is no owner recovery/rotation, upgrade mechanism, signature authorization,
token adapter, delegate-selected recipient, or reserved-funds guarantee. Losing
owner control or choosing an unusable owner/recipient is outside the demonstrated
recovery model. Aggregate permission caps may exceed actual funds.

A recipient can reject, reenter, observe getters, emit logs, forward funds, or
otherwise control its own execution. A contract may simultaneously be owner,
delegate, and recipient. The tests deliberately use that role overlap so an
incorrect missing lock cannot be hidden by an unrelated authority rejection.

## Trusted computation and boundaries

- Fe 26.5.0, compiler-bundled core/std, generated dispatch/ABI decoding, stdlib
  Mutex/StorageMap/Call/Ctx, and Osaka EVM behavior are trusted dependencies.
  Pins/digests support reproduction; they do not prove those dependencies safe.
- The EVM boundary is trusted to load the current record, bind actual caller,
  timestamp and balance, evaluate under the shared lock, reserve accounting,
  end mutable projections, execute the stored payment, emit, and unlock.
- The pure library accepts ordinary values and a read-only application-owned
  context. It does not authenticate how an arbitrary host obtained those values.
  A Grant or SpendDecision is not an unforgeable credential or reusable ticket.
- The submitted safe interfaces make dependencies explicit. Missing-effect and
  immutable-access diagnostics are limited claims about those functions, not a
  sandbox against malicious trusted hosts or alternative broad providers.
- Thin Python tooling handles files/processes/RPC and test expectations. It does
  not implement production grant policy. Local Anvil uses ephemeral unlocked
  test accounts; no external RPC or funded real account is configured.

## Review of operation ordering

Constructor validates owner before initialization. Every treasury mutation first
passes compiler dispatch/nonpayability/decoding, then takes the same mutex.
Administration uses actual owner authority; spend establishes existence before
checking the stored delegate. Invalid amount, exclusive expiry, record integrity,
remaining cap, and actual balance follow the frozen order. Pure policy rejections
occur before persistent writes. Revocation preserves fields/existence and never
reuses an ID; inactive revocation explicitly unlocks without another event.

The successful spend writes only the proposed spent value into the current
snapshot, then makes one empty-calldata value call to the stored recipient.
No mutable storage projection is retained across that call. Call failure reverts
rather than returning a pure Err after mutation. Callback mutations meet the
already-held mutex; getters deliberately expose the reserved spent and current
post-transfer balance. A successful normal call unlocks before return.

The private cap-error mapper subtracts cap-spent only for CapExceeded, which the
pure evaluator can produce only after checking spent <= cap. The checked
addition is bounded by amount <= cap-spent. Mutants are applied only in temporary
copies and never shipped as production-source changes.

The sponsorship adapter performs the same trusted binding/execution steps around
one Grant and imports the same evaluators. Its numeric error mapping translates
categories, not validation rules. Its example scope has no refund/withdrawal:
unused funds remain held after cancellation or expiry. It uses only local test
ETH in the recorded demos; adding a real refund design would require a separate
specification and tests.

## Findings and disposition

| Finding | Disposition |
| --- | --- |
| The earlier equality evidence used actual block-context eth_call; the matching failed receipt could be mined later | Added a focused scenario with receipts and headers exactly at expiry-1, expiry, expiry+1; success/failure and unchanged state checked |
| Same-grant and cross-function callbacks were covered, but direct cross-grant spending reentry was not | Added a Fe test and real Anvil callback from authorized grant 1 into authorized grant 2; exact Reentrant and sibling preservation checked |
| Test count alone did not establish sensitivity to four required defects | Four compiling mutants fail existing targeted tests after passing identical unmodified controls |
| Independent developer reproduction/explanation has not been received | Prepared a history-preserving review bundle and feedback template; kept the full Phase 5 status pending |

This pass adds tests, tooling, and evidence. It introduces no change to the
policy, treasury, or sponsorship production source. No general conclusion of
absence of vulnerabilities follows from the results.

## Limits and assumptions

Requested recipient gas is fixed at 100,000; EVM caps and stipend apply. A
recipient requiring more can fail, and transaction-level gas exhaustion is not
a guaranteed typed application error. The stdlib path avoids copying recipient
returndata; a dedicated oversized-data stress experiment has not been performed.

Expiry uses the current block timestamp, not a trusted wall clock. Actual ETH
balance can change through unsolicited credit. No invariant equates balance with
deposit events minus spends; recipient code can forward/return received value.
Tests using simple recipients check net balance deltas only for those recipients.

Storage layout equivalence, arbitrary proxy upgrades, multi-client conformance,
exhaustive actor/action sequences, all gas settings, and every callback ordering
remain outside the evidence. The existing balance override is a transparent test
environment fixture, not an actual forced-ETH transaction. See the complete
[test matrix](test-matrix.md) for tested and untested combinations.
