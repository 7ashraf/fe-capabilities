# Source from the repository root: source scripts/env.sh
if [ ! -f "$PWD/toolchain.json" ] || [ ! -d "$PWD/policy" ]; then
    printf '%s\n' 'Source scripts/env.sh from the fe-capabilities repository root.' >&2
    return 1
fi
export PATH="$PWD/.tools/bin:$PATH"
