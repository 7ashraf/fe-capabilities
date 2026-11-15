#!/usr/bin/env python3
"""Install or reuse the pinned Fe release after verifying its SHA-256."""
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess


def main():
    root = Path(__file__).resolve().parent.parent
    manifest = json.loads((root / 'toolchain.json').read_text())
    system = {'Darwin': 'mac', 'Linux': 'linux'}.get(platform.system())
    arch = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'amd64', 'AMD64': 'amd64'}.get(platform.machine())
    if not system or not arch:
        raise SystemExit('Unsupported compiler installer platform; see docs/setup.md.')
    asset = manifest['fe']['assets'][f'fe_{system}_{arch}']
    expected_version = 'fe 26.5.0 (3dab95f)'

    def trusted(path):
        return path.is_file() and 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest() == asset['digest']

    def check_version(path):
        if not os.access(path, os.X_OK):
            raise SystemExit(f'Pinned compiler is not executable: {path}')
        version = subprocess.check_output([str(path), '--version'], text=True).strip()
        if version != expected_version:
            raise SystemExit(f'Unexpected compiler version: {version}')
        print(version)

    configured = os.environ.get('FE_BIN')
    if configured:
        path = Path(configured).resolve()
        if not trusted(path):
            raise SystemExit('FE_BIN must point to the pinned release binary; checksum mismatch or missing file.')
        check_version(path)
        print('Reused verified FE_BIN; external file unchanged.')
        return
    destination = root / '.tools/bin/fe'
    destination.parent.mkdir(parents=True, exist_ok=True)
    if trusted(destination):
        check_version(destination)
        print('Reused verified repository-local compiler.')
        return
    temporary = destination.with_suffix('.download')
    try:
        subprocess.run(['curl', '-fL', '--retry', '3', '--connect-timeout', '20',
                        '--max-time', '600', asset['url'], '-o', str(temporary)], check=True)
        if not trusted(temporary):
            raise SystemExit('Compiler checksum mismatch; installation aborted.')
        temporary.chmod(0o755)
        # Verify before replacing an existing local installation.
        check_version(temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
