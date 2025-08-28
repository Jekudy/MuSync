#!/usr/bin/env python3
"""
Prepare release artifacts for MuSync v0.1.0.

- Reads VERSION
- Runs gating tests and smoke E2E
- Collects artifacts (coverage html, reports/, metrics/, logs/) into artifacts/<version>/
- Writes manifest.json with paths and summary
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_ROOT = ROOT / "artifacts"


def run(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 600) -> int:
    print(f"$ {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, cwd=cwd or ROOT, timeout=timeout)
        return res.returncode
    except subprocess.TimeoutExpired:
        print(f"Command timed out: {' '.join(cmd)}")
        return 124


def main() -> int:
    version = (ROOT / "VERSION").read_text().strip()
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    out_dir = ARTIFACTS_ROOT / f"{version}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Run gating
    rc = run(["python3", "scripts/run_tests_with_gating.py", "--timeout", "180"])  # includes coverage html
    if rc != 0:
        print("Gating failed; aborting release prep.")
        return rc

    # 2) Smoke E2E (simple)
    rc = run(["python3", "-m", "pytest", "app/tests/e2e/test_simple_e2e.py", "-q", "--timeout", "60"]) 
    if rc != 0:
        print("Smoke E2E failed; aborting release prep.")
        return rc

    # 3) Collect artifacts
    collected: dict = {"copied": [], "missing": []}

    def safe_copy(src: Path, dst: Path):
        if src.exists():
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            collected["copied"].append(str(dst.relative_to(ROOT)))
        else:
            collected["missing"].append(str(src.relative_to(ROOT)))

    safe_copy(ROOT / "htmlcov", out_dir / "coverage")
    safe_copy(ROOT / "reports", out_dir / "reports")
    safe_copy(ROOT / "metrics", out_dir / "metrics")
    safe_copy(ROOT / "logs", out_dir / "logs")

    # 4) Manifest
    manifest = {
        "version": version,
        "timestamp_utc": ts,
        "artifacts_dir": str(out_dir.relative_to(ROOT)),
        "copied": collected["copied"],
        "missing": collected["missing"],
        "commands": [
            "python3 scripts/run_tests_with_gating.py --timeout 180",
            "python3 -m pytest app/tests/e2e/test_simple_e2e.py -q --timeout 60"
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Release artifacts prepared at: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
