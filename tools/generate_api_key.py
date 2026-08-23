#!/usr/bin/env python3
"""Generate a private Wi-Fi Radar API key file without printing the secret."""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="private destination outside source control")
    parser.add_argument("--force", action="store_true", help="replace an existing key")
    args = parser.parse_args()
    path = args.path.expanduser().resolve()
    if path.exists() and not args.force:
        print(f"refusing to replace existing key: {path}", file=sys.stderr)
        return 2
    parent_existed = path.parent.exists()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not parent_existed:
        os.chmod(path.parent, 0o700)
    if path.parent.stat().st_mode & 0o077:
        print(f"refusing non-private parent directory: {path.parent}", file=sys.stderr)
        return 2
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(secrets.token_hex(32) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    print(f"API key created with mode 600: {path}")
    print("The key value was not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
