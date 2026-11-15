# Setup and troubleshooting

Run commands from the `fe-capabilities` repository root. The project has no
Python package dependencies, Node dependency install, Solidity compiler, public
RPC, wallet connection, or sibling-project checkout requirement.

## Host and tools

The complete suite includes native Fe reference/vector tests. Eligible native
hosts for this pinned compiler are **macOS arm64** and **Linux amd64**. This
handoff was executed on macOS arm64; Linux has not been locally validated here.
Other Fe release assets may support EVM-only commands, but the complete handoff
runner does not claim them as verified native hosts.

Required:

- Python 3.11 or newer (`tomllib` is used by the reuse runner).
- Git to clone/package the history-preserving bundle.
- curl for downloading the pinned Fe compiler, unless using an existing binary.
- Fe `26.5.0 (3dab95f)` with the release digest in `toolchain.json`.
- Anvil and Cast `1.5.1-stable`, commit
  `b0a9dd9ceda36f63e2326ce530c10e6916f4b8a2`, on PATH.

If Foundryup is already installed, its checked install option is:

```sh
foundryup --install v1.5.1
```

This selects that version in the user's Foundry installation. An isolated PATH
containing the matching Anvil/Cast binaries can also be used. The primary release
is [Foundry v1.5.1](https://github.com/foundry-rs/foundry/releases/tag/v1.5.1).
The project checks the exact version/commit and does not silently upgrade tools.

## Quick start

```sh
python3 scripts/bootstrap-fe.py
source scripts/env.sh
python3 scripts/doctor.py
python3 scripts/demo.py
python3 scripts/verify-handoff.py
```

The bootstrap downloads only the matching pinned platform asset into ignored
`.tools/bin/fe`, verifies SHA-256 before execution, checks its version, and
atomically replaces the local file. A valid existing local binary is reused.
A failed or mismatched download is not installed. A partial temporary download
is removed.

To reuse an already installed pinned release instead:

```sh
export FE_BIN=/absolute/path/to/fe
python3 scripts/bootstrap-fe.py
python3 scripts/doctor.py
python3 scripts/demo.py
python3 scripts/verify-handoff.py
```

The selected external file must match the expected release digest and be
executable. It is verified and used without replacement. `FE_BIN` takes
precedence in the Python runners; `source scripts/env.sh` puts the local compiler
on PATH for direct `fe` commands. Use an absolute FE_BIN path.

## Common setup failures

| Symptom | Resolution |
| --- | --- |
| Fe missing | Run the bootstrap or set FE_BIN to a matching release binary. |
| Fe digest mismatch | Use the pinned platform release. A source build, renamed different version, or corrupt binary will not satisfy the release digest check. |
| Wrong Anvil/Cast | Select the exact pinned Foundry tools on PATH; doctor reports the mismatch before the long suite. |
| Unsupported native host | Use macOS arm64 or Linux amd64 for the full suite; EVM-only use on other hosts is outside this handoff's validation. |
| Python lacks tomllib | Use Python 3.11+. No pip installation is needed for this repo. |
| Installer network error | Retry the bootstrap or reuse a verified release via FE_BIN. The installer leaves the previous local binary intact until validation succeeds. |
| Deliberate compile failure | Use the documented runners. `fe test tests` includes negative fixtures and is not an all-passing suite. |
| Wrong working directory | Change to the repository root before sourcing env.sh; the script checks that location. |

The demo and transaction checks start fresh loopback-only Anvil processes on
selected ports and terminate them afterward. Their accounts and wei are local
fixtures. The full suite separates expected compiler/runtime negatives from
infrastructure failures and does not accept a tool crash as a detected defect.
