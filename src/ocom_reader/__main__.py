"""Enables `python -m ocom_reader ask "..."`."""

from __future__ import annotations

import sys

from ocom_reader.cli import main

if __name__ == "__main__":
    sys.exit(main())
