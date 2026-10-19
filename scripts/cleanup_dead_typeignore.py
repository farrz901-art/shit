#!/usr/bin/env python3
"""
批量删 [dead] type: ignore 实验脚本 (2026-07-08 P1.1)
策略: 对每个含 type: ignore 的 .py 文件, 删掉 ignore 注释, 跑 pyright 验证.
       失败 git checkout 恢复, 跳过该文件.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVICE_DIR = PROJECT_ROOT / "packages" / "service"
PYRIGHT_CMD = ["uv", "run", "pyright"]

# 匹配末尾的 `# type: ignore[xxx]` (可有可无 [xxx])
TYPE_IGNORE_INLINE_RE = re.compile(r"\s*#\s*type:\s*ignore(\[.*?\])?")


def find_files_with_ignore(root: Path) -> list[Path]:
    return [
        p for p in root.rglob("*.py")
        if "__pycache__" not in str(p) and ".venv" not in str(p) and "type: ignore" in p.read_text(encoding="utf-8")
    ]


def remove_ignore_comments(file_path: Path) -> int:
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    deleted = 0
    new_lines = []
    for line in lines:
        if "type: ignore" in line and "#" in line:
            new_line, n = TYPE_IGNORE_INLINE_RE.subn("", line)
            if n > 0:
                deleted += n
                line = new_line
        new_lines.append(line)
    if deleted > 0:
        file_path.write_text("\n".join(new_lines), encoding="utf-8")
    return deleted


def run_pyright() -> tuple[bool, int]:
    result = subprocess.run(PYRIGHT_CMD, cwd=SERVICE_DIR, capture_output=True, text=True)
    combined = result.stdout + result.stderr
    m = re.search(r"(\d+)\s+errors", combined)
    if m:
        return int(m.group(1)) == 0, int(m.group(1))
    return result.returncode == 0, -1


def main() -> int:
    files = find_files_with_ignore(SERVICE_DIR / "src")
    test_files = find_files_with_ignore(SERVICE_DIR / "tests")
    print(f"src 含 type:ignore 的文件: {len(files)}")
    print(f"test 含 type:ignore 的文件: {len(test_files)}")

    baseline_ok, baseline_errors = run_pyright()
    print(f"\n基线 pyright error: {baseline_errors}")

    deleted_total = 0
    failed_files: list[Path] = []

    for f in files + test_files:
        n = remove_ignore_comments(f)
        if n == 0:
            continue
        ok, errs = run_pyright()
        rel = f.relative_to(PROJECT_ROOT)
        if errs > baseline_errors:
            print(f"FAIL 恢复: {rel} (删了 {n} 条 ignore 后 pyright 报错 {errs} > 基线 {baseline_errors})")
            subprocess.run(["git", "checkout", "--", str(rel)], cwd=PROJECT_ROOT, check=False)
            failed_files.append(f)
        else:
            print(f"OK: {rel} (删了 {n} 条, pyright {errs} errors)")
            deleted_total += n

    print(f"\n=== 实验结束 ===")
    print(f"成功删除: {deleted_total} 条 type: ignore")
    print(f"失败文件: {len(failed_files)} 个")

    final_ok, final_errs = run_pyright()
    if final_errs > baseline_errors:
        print(f"FAIL: 最终 pyright 报错 ({final_errs} > 基线 {baseline_errors}), 整体回滚")
        subprocess.run(["git", "checkout", "--", "packages/service/src", "packages/service/tests"], cwd=PROJECT_ROOT, check=False)
        return 1

    print(f"OK: pyright {final_errs} errors 维持 (基线 {baseline_errors})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
