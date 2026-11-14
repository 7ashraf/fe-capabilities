# Single-campaign sponsorship example

A second independent consumer of `capabilities_policy`. A creator deploys one
campaign with a fixed operator, beneficiary, cap, and exclusive expiry. Anyone
may fund it; only its operator can sponsor a payment under the shared grant
policy, and only the original creator can cancel it. Cancellation is permanent;
repeat cancellation is a successful no-op without another event.

The ingot imports only `../../policy`, not the treasury. It calls
`evaluate_create`, `evaluate_spend`, and `evaluate_revoke`; it contains no copy of
the caller, amount, expiry, cap, existence, or active-state validation algorithm.
Its own boundary binds real Ctx, stores one `Mutex<Grant>`, maps error categories,
performs payments, and emits application-specific events. Beneficiary and
operator cannot be replaced after deployment.

This is a narrow example using local test ETH. There is no refund/withdrawal,
operator rotation, or production wallet UI; unused campaign funds remain held
when it is cancelled or expires. The test Receiver and Proxy are separate test
fixtures, not application roles for a production deployment.

## Run

From the repository root, after setting up the pinned compiler and Foundry:

```sh
python3 scripts/verify-reuse.py
```

This runs the treasury checks, sponsorship's four Fe EVM tests, the three new
external compile-fail pairs and positive runtime controls, metadata/source
identity checks, and local Anvil sponsorship transactions. The generated
[ABI snapshot](abi.json) is checked against the compiler output.

## Interface

Constructor arguments: operator address, beneficiary address, limit in wei,
expiry in Unix seconds. The creator is bound from the actual constructor caller.

| Signature | Behavior |
| --- | --- |
| `fund()` payable | Any caller funds; positive amount emits Funded, zero emits none. |
| `sponsor(uint256)` nonpayable | Current operator asks to pay the fixed beneficiary; shared policy chooses a valid transition. |
| `cancel()` nonpayable | Creator deactivates; repeated cancellation is a no-op. |
| `campaignSponsor()` view | Original creator address. |
| `status()` view | Seven flat outputs: exists, operator, beneficiary, cap, spent, expiry, active. |

Every mutation shares the same stdlib transient mutex. Payment reserves spent
before the empty-calldata value call (requested gas 100,000). Failure reverts
with PaymentFailed and restores accounting and ETH; success emits Sponsored.
A later legitimate payment in the same transaction works after rollback or unlock.
Getters can expose reserved spent during callbacks, as in the treasury.
This example has its own ABI; it does not claim treasury ABI compatibility.

| Event | Indexed | Data |
| --- | --- | --- |
| `Funded(address,uint256)` | sender | amount |
| `Sponsored(address,address,uint256,uint256)` | operator, beneficiary | amount, newSpent |
| `Cancelled()` | none | none |

Policy rejections use `PolicyRejected(uint256 code)`:

| Code | Shared PolicyError |
| --- | --- |
| 1 | InvalidOwner |
| 2 | Unauthorized |
| 3 | UnknownGrant |
| 4 | InactiveGrant |
| 5 | InvalidAddress |
| 6 | InvalidAmount |
| 7 | InvalidExpiry |
| 8 | GrantIdExhausted |
| 9 | Expired |
| 10 | InvalidGrantState |
| 11 | CapExceeded |
| 12 | InsufficientBalance |

The mapping is category translation, not a second policy implementation. Some
categories are unreachable for a valid single-campaign deployment. PaymentFailed,
Reentrant, and UnsupportedCall are separate no-argument boundary errors.
The pinned compiler rejects value on nonpayable calls and malformed ABI input.

See [Phase 4 results](../../docs/phase4.md) for exact tests, raw evidence, shared
source hashes, and the limits of the compile-time boundary claims.
