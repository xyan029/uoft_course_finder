#!/usr/bin/env python3
"""Backwards-compatible shim: ``python3 uoft_course_finder.py ...``.

The implementation lives in the ``uoft_course_finder`` package; prefer the
``uoft-course-finder`` console script once the package is installed.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from uoft_course_finder.cli import main

if __name__ == "__main__":
    sys.exit(main())
