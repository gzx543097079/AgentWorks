#!/usr/bin/env python3
"""Backward-compatible entry; use smoke_runner.py for new backends."""
import sys
from smoke_runner import main

if __name__ == "__main__":
    if "--backend" not in sys.argv and not any(v.startswith("--backend=") for v in sys.argv):
        sys.argv.extend(["--backend", "codex"])
    raise SystemExit(main())
