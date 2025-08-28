#!/usr/bin/env python3
"""
Cross-platform timeout runner.

Runs any command and stops it after the specified timeout, attempting
graceful shutdown first and then force-killing the whole process tree.

Usage:
  python -m scripts.run_with_timeout --timeout 90 -- python3 spotify_oauth_server.py --timeout 60

Notes:
  - Works on macOS/Linux/Windows.
  - Kills the entire process group to avoid zombies.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from typing import List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a command with a timeout")
    parser.add_argument(
        "--timeout",
        type=int,
        required=True,
        help="Timeout in seconds after which the command will be stopped",
    )
    parser.add_argument(
        "--grace",
        type=float,
        default=5.0,
        help="Seconds to wait after SIGINT before escalating to SIGKILL",
    )
    parser.add_argument(
        "cmd",
        nargs=argparse.REMAINDER,
        help="Command to execute after '--'",
    )
    args = parser.parse_args()
    # Strip the leading '--' if present
    if args.cmd and args.cmd[0] == "--":
        args.cmd = args.cmd[1:]
    if not args.cmd:
        parser.error("Command is required after '--'")
    return args


def terminate_process_tree(proc: subprocess.Popen, grace: float) -> None:
    """Try to gracefully stop the process, then kill it."""
    try:
        if os.name == "nt":
            # Windows: send CTRL_BREAK (if in new process group), then
            # terminate
            # type: ignore[attr-defined]
            proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
        else:
            # POSIX: send SIGINT to the whole group
            os.killpg(os.getpgid(proc.pid), signal.SIGINT)
    except Exception:
        pass

    try:
        proc.wait(timeout=grace)
        return
    except Exception:
        pass

    # Escalate
    try:
        if os.name == "nt":
            proc.kill()
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        pass


def main() -> int:
    args = parse_args()
    cmd: List[str] = args.cmd

    creationflags = 0
    preexec_fn = None
    if os.name != "nt":
        # Start a new process group so we can kill the whole tree
        preexec_fn = os.setsid  # type: ignore[assignment]
    else:
        # type: ignore[attr-defined]
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    try:
        proc = subprocess.Popen(
            cmd,
            preexec_fn=preexec_fn,
            creationflags=creationflags,
        )
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        return 127

    try:
        returncode = proc.wait(timeout=args.timeout)
        return returncode
    except subprocess.TimeoutExpired:
        print(f"⏳ Timeout {args.timeout}s reached. "
              f"Stopping command: {' '.join(cmd)}")
        terminate_process_tree(proc, args.grace)
        # Give a brief moment for cleanup
        time.sleep(0.2)
        return 124


if __name__ == "__main__":
    sys.exit(main())
