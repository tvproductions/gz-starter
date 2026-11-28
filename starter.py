"""Compatibility entry point; implementation lives in the installed package."""

from gzlite.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
