#!/usr/bin/env python3
"""Cross-platform oversize-file scanner for oversize-files-audit skill.

Usage:
    python scan-script.py <root> [min_lines]

Outputs JSON to stdout: [{path, lines}, ...] sorted by lines desc.
ASCII-only to avoid Windows console encoding issues.
"""
import json
import sys
from pathlib import Path

EXCLUDE_DIRS = {
    "__generated__", "node_modules", ".next", "dist", "build",
    ".venv", "venv", ".pytest_cache", ".ruff_cache", "coverage",
    "graphify-out", ".git", ".turbo", "out",
}
EXCLUDE_PATH_PATTERNS = (
    "migrations/versions/", ".generated.", "node_modules/",
    "__snapshots__/", "fixtures/",
    "test_", "_test.", ".test.", ".spec.",
)
EXTS = (".py", ".ts", ".tsx")


def should_skip(fp: Path) -> bool:
    s = str(fp)
    for pat in EXCLUDE_PATH_PATTERNS:
        if pat in s:
            return True
    for part in fp.parts:
        if part in EXCLUDE_DIRS:
            return True
    if fp.suffix not in EXTS:
        return True
    return False


def count_lines(fp: Path) -> int:
    try:
        with fp.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: scan-script.py <root> [min_lines]", file=sys.stderr)
        return 2
    root_arg = sys.argv[1] if len(sys.argv) > 1 else "."
    root = Path(root_arg).resolve()
    min_lines = int(sys.argv[2]) if len(sys.argv) > 2 else 300

    results = []
    for fp in root.rglob("*"):
        if not fp.is_file() or should_skip(fp):
            continue
        n = count_lines(fp)
        if n >= min_lines:
            results.append({"path": str(fp.relative_to(root)).replace("\\", "/"), "lines": n})

    results.sort(key=lambda r: -r["lines"])
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
