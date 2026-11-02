"""Render a list of courses as a text table, JSON or CSV."""

from __future__ import annotations

import csv
import io
import json
import textwrap
from typing import Callable, Dict, Iterable, List, Sequence

from .calendars import CALENDARS
from .models import Course

FORMATS = ("table", "json", "csv")
CSV_COLUMNS = ("campus", "code", "title", "url", "description", "details", "score")
TABLE_DESCRIPTION_WIDTH = 60


def format_details(details: Dict[str, str]) -> str:
    """Flatten a details mapping into ``"Key: value | Key: value"``."""
    return " | ".join(f"{key}: {value}" for key, value in details.items())


def format_json(courses: Iterable[Course]) -> str:
    return json.dumps([course.to_dict() for course in courses], indent=2, ensure_ascii=False)


def format_csv(courses: Iterable[Course]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for course in courses:
        writer.writerow(
            [
                course.campus,
                course.code,
                course.title,
                course.url,
                course.description,
                format_details(course.details),
                course.score,
            ]
        )
    return buffer.getvalue()


def _campus_label(key: str) -> str:
    calendar = CALENDARS.get(key)
    return calendar.name if calendar else key


def format_table(
    courses: Sequence[Course], description_width: int = TABLE_DESCRIPTION_WIDTH
) -> str:
    """Render an aligned, human-readable table.

    Descriptions are shortened to ``description_width`` characters so that
    one course fits on one line.
    """
    headers = ("Campus", "Code", "Title", "Description")
    rows: List[Sequence[str]] = []
    for course in courses:
        description = " ".join(course.description.split())
        if description_width > 0:
            description = textwrap.shorten(description, width=description_width, placeholder="...")
        rows.append((_campus_label(course.campus), course.code, course.title, description))

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def render(row: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip()

    lines = [render(headers), "  ".join("-" * width for width in widths)]
    lines.extend(render(row) for row in rows)
    return "\n".join(lines) + "\n"


FORMATTERS: Dict[str, Callable[[Sequence[Course]], str]] = {
    "table": format_table,
    "json": format_json,
    "csv": format_csv,
}


def format_courses(courses: Sequence[Course], fmt: str) -> str:
    try:
        formatter = FORMATTERS[fmt]
    except KeyError:
        raise ValueError(f"unknown format {fmt!r}; choose from {', '.join(FORMATS)}") from None
    return formatter(courses)
