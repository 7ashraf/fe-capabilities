# Phase 6 — local freeze and handoff

Prepared 15 November 2026, following the owner's instruction to proceed with
release preparation while independent developer feedback remains pending.
That feedback was not received, invented, or waived. The earlier self-imposed
ordering restriction has been removed; the outstanding task remains visible.

## Completed local preparation

- MIT license for project-authored work, upstream attribution/license copy, and
  explicit supplied-material/AI-assistance provenance.
- Setup/platform guidance and prerequisite doctor for Python 3.11+, the exact
  Fe release digest, eligible native host, and pinned Anvil/Cast version/commit.
- Bootstrap reuses verified local/FE_BIN binaries, rejects mismatched external
  files before executing them, validates downloads before replacing local Fe,
  and removes temporary downloads on failure.
- Source/spec freeze hashes and explicit build profile, optimization, arithmetic,
  backend, compiler, and dependency pins. Production code is unchanged.
- README quick start, eight-step asserted demo, complete handoff instructions,
  and an exact-commit/history-preserving local bundle packager.
- Clean-checkout demo and complete technical checks, then bundle clone verification.

The final environment and command outcome are recorded in
[evidence/handoff.json](evidence/handoff.json). The generated ignored bundle
manifest binds the final full Git commit to its artifact digest without a
self-referential commit field inside tracked documentation.

## Commands

```sh
python3 scripts/bootstrap-fe.py
source scripts/env.sh
python3 scripts/doctor.py
python3 scripts/demo.py
python3 scripts/verify-handoff.py
```

`verify-handoff.py` includes the entire technical review suite. It checks frozen
inputs before execution and retains the separate pending-review state. On a
clean committed branch, `python3 scripts/package-handoff.py` produces the source
bundle, SHA-256 file, and exact-commit manifest. Full instructions are in
[handoff.md](handoff.md); setup failures are covered in [setup.md](setup.md).

## Validation scope

The local validation host is Darwin arm64 with Python 3.14.6. Fe is
`26.5.0 (3dab95f)`, mac-arm64 SHA-256
`4968711c5bc02c1a3151cfaea0d81a48dc74803ea208362022af467c2a523fed`.
Foundry is `1.5.1-stable`, commit `b0a9dd9ceda36f63e2326ce530c10e6916f4b8a2`.
Execution remains Osaka, Sonatina optimization 1, release/test profiles, checked
arithmetic, with native pure tests on the same host.

The full suite covers 6 administration tests, 12 spending tests, 4 sponsorship
tests, three external effect/write controls and their intended compiler failures,
70 golden vectors per EVM/native backend, earlier reference/type/access tests,
four compiling seeded defects, ABI/source identity checks, local transaction
scenarios, and the demo's allowed payment plus at least three rejected actions.
The bundle includes all main-branch ancestry; the implementing agent's fresh
clone is reproduction evidence, not independent human review.

## Outstanding limitations

Independent developer feedback is still pending and recorded in
[reviewer-feedback.md](reviewer-feedback.md). No professional audit, universal
security claim, Linux execution, cross-client equivalence, or production readiness
is asserted. Unsupported/untested cases remain in [test-matrix.md](test-matrix.md)
and [threat-model.md](threat-model.md). The local preparation and history artifact
are complete without marking the outside-review task complete.
