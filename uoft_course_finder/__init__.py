"""Search the official University of Toronto academic calendars by keyword.

The package uses only the Python standard library at runtime. The public
surface is small:

* :func:`search` runs a keyword search across one or more campuses.
* :class:`Course` is the record type every search returns.
* :mod:`uoft_course_finder.cli` provides the ``uoft-course-finder`` command.
"""

from __future__ import annotations

from ._version import __version__
from .calendars import CALENDARS, Calendar
from .models import CampusError, Course, SearchResult
from .scrapers import search, search_campus

__all__ = [
    "CALENDARS",
    "Calendar",
    "CampusError",
    "Course",
    "SearchResult",
    "__version__",
    "search",
    "search_campus",
]
