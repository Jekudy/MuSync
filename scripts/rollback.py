#!/usr/bin/env python3
"""
Rollback helper: forces DRY-RUN via MUSYNC_ROLLBACK=1 and runs CLI transfer.
Usage:
  python3 scripts/rollback.py --source yandex --target spotify [--playlists ...]
"""
import os
import subprocess
import sys


def main() -> int:
    os.environ["MUSYNC_ROLLBACK"] = "1"
    cmd = ["python3", "musync_cli.py", "transfer"] + sys.argv[1:]
    print(f"$ {' '.join(cmd)} (with MUSYNC_ROLLBACK=1)")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
