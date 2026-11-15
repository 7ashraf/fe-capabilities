# Local handoff — 0.1.0

Prepared 15 November 2026. Implementation and local verification are complete.
Independent developer feedback remains pending. The owner authorized Phase 6
preparation in parallel; this records a sequencing decision, not a review waiver.
See [feedback status](reviewer-feedback.md), [threat notes](threat-model.md), and
[the test matrix](test-matrix.md).

## What is included

| Area | Deliverable |
| --- | --- |
| `policy/` | Reusable Fe ingot; pure current-state grant/budget decisions |
| `treasury/` | Persistent ETH treasury; owner administration, delegate spending, shared lock |
| `examples/sponsorship/` | Independent consumer of the same unchanged policy inputs |
| `spec/` | Treasury behavior, full target ABI, historical administrative ABI |
| `tests/` and `scripts/` | Runtime, native/vector, compile-fail, mutation, transaction and demo checks |
| `docs/evidence/` | Historical raw results plus final local environment/handoff record |
| `LICENSE`, `NOTICE.md`, `licenses/` | MIT project license, source/AI provenance, upstream Fe license |

All local ingots live in this repository and resolve by relative paths. Fe
core/std are compiler-bundled; there are no remote ingot dependencies or missing
sibling repositories. Exact compiler release hashes, source commit, build/test
settings, Foundry version/commit, and frozen application/spec hashes are in
`toolchain.json`. The absence of a Fe dependency lockfile is not replaced by an
unpinned branch dependency.

## Install, run the demo, verify

Prerequisites and version selection are described in [setup.md](setup.md).
From the repository root:

```sh
python3 scripts/bootstrap-fe.py
source scripts/env.sh
python3 scripts/doctor.py
python3 scripts/demo.py
python3 scripts/verify-handoff.py
```

An existing pinned compiler may be selected with an absolute FE_BIN path. The
bootstrap and doctor verify its digest/version before use. A valid local binary
is reused. Foundry's pinned Anvil/Cast must be on PATH; the project does not
switch their global version automatically.

The demo builds current artifacts and runs a fresh local Osaka chain. It creates
a grant, makes an allowed payment, and reproduces overspend, unapproved-caller,
and revoked-grant rejections with exact error bytes. It also demonstrates blocked
reentry and two later legitimate payments in one transaction. Printed outcomes
follow actual assertions; the node stops afterward.

The handoff runner checks the frozen source/spec inputs and complete technical
suite: both consumers, full ABI, shared library inputs, external access pairs,
70 vectors on each backend, prior phase checks, four compiling mutants, mined
expiry boundaries, cross-grant callbacks, and the demo. It reports independent
review separately. It does not update tracked evidence unless --record is used.

## Exact revision and history-preserving artifact

The committed handoff record is [handoff.json](evidence/handoff.json). It records
the environment and frozen inputs without embedding its own commit (which would
create a circular commit dependency). Identify the checked-out revision with:

```sh
git rev-parse HEAD
git status --short
```

After committing all intended changes and running the checks:

```sh
python3 scripts/package-handoff.py
```

This creates ignored local artifacts:

- `.tools/fe-capabilities-handoff.bundle`: current named branch and complete ancestry.
- `.tools/fe-capabilities-handoff.bundle.sha256`: file checksum.
- `.tools/handoff-manifest.json`: exact full commit, branch, history count,
  compiler/tool pins, frozen input hashes, license, review status, and bundle digest.

The packager requires a clean working tree and matching frozen inputs. It
packages committed source/history; run the verification command first.
Checksums identify the artifact; they are not a signed release or an independent
security endorsement. Tool downloads, caches, build outputs, and test account
secrets are not included in the Git bundle. Recorded account addresses belong
to local Anvil fixtures.

A recipient can clone the bundle and keep all commits:

```sh
git clone --branch main fe-capabilities-handoff.bundle fe-capabilities
cd fe-capabilities
python3 scripts/bootstrap-fe.py
source scripts/env.sh
python3 scripts/doctor.py
python3 scripts/demo.py
python3 scripts/verify-handoff.py
git status --short
```

The final bundle is validated by cloning it and running the full handoff checks.
A future remote can be added to that same repository and the existing branch
pushed without recreating history. Remote publication, contest forms, and live
fund deployment are separate from this local handoff.

## Limits retained in this handoff

Local execution is verified on macOS arm64. The full native suite requires
macOS arm64 or Linux amd64; no local Linux run is claimed. Runtime behavior is
pinned to Osaka, not every EVM client/fork. Recipient gas is requested at 100,000;
more expensive recipients may fail. No application unsafe code is introduced;
compiler-bundled stdlib/EVM internals remain trusted.

Outside developer feedback and a professional audit are absent. The selected
four-mutant result is not a general defect-detection rate. The test matrix lists
untested combinations, including actual forced-ETH opcode transfers and broad
gas/returndata stress. Ordinary policy data is constructible, so the trusted EVM
boundary must bind actual current context under its lock. Sponsorship is a narrow
example with no refund/withdrawal or operator rotation.

Project originality, supplied reference material, upstream primitives, generated
scaffolding, and Codex assistance are recorded in [NOTICE.md](../NOTICE.md).
