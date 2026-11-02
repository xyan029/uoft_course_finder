"""Output format tests."""

from __future__ import annotations

import csv
import io
import json

import pytest

from uoft_course_finder.formatters import (
    CSV_COLUMNS,
    format_courses,
    format_csv,
    format_details,
    format_json,
    format_table,
)
from uoft_course_finder.models import Course

COURSES = [
    Course(
        campus="artsci",
        code="CSC108H1",
        title="Introduction to Computer Programming",
        url="https://artsci.calendar.utoronto.ca/course/CSC108H1",
        description="Programming in a language such as Python.\n\nSecond paragraph, with é.",
        details={"Hours": "24L/12T", "Exclusion": 'CSC148H1, "quoted"'},
        score=60,
    ),
    Course(
        campus="utm",
        code="CSC108H5",
        title="Introduction to Computer Programming",
        url="https://utm.calendar.utoronto.ca/course/CSC108H5",
        description="",
        details={},
        score=0,
    ),
]


def test_table_has_header_rule_and_one_row_per_course():
    table = format_table(COURSES)
    lines = table.splitlines()
    assert lines[0].split() == ["Campus", "Code", "Title", "Description"]
    assert set(lines[1]) == {"-", " "}
    assert len(lines) == 2 + len(COURSES)
    assert lines[2].startswith("UTSG Arts & Science  CSC108H1  Introduction to Computer")
    assert lines[3].startswith("UTM")
    assert table.endswith("\n")


def test_table_columns_are_aligned():
    lines = format_table(COURSES).splitlines()
    code_column = lines[0].index("Code")
    assert all(line[code_column:].startswith(("Code", "----", "CSC108")) for line in lines)


def test_table_shortens_long_descriptions_and_flattens_newlines():
    row = format_table(COURSES, description_width=30).splitlines()[2]
    assert "\n" not in row
    assert row.rstrip().endswith("...")
    assert "Programming in a" in row


def test_table_with_no_courses_is_just_the_header():
    lines = format_table([]).splitlines()
    assert len(lines) == 2


def test_json_round_trips_all_fields_and_unicode():
    data = json.loads(format_json(COURSES))
    assert [c["code"] for c in data] == ["CSC108H1", "CSC108H5"]
    first = data[0]
    assert first["details"] == {"Hours": "24L/12T", "Exclusion": 'CSC148H1, "quoted"'}
    assert first["score"] == 60
    assert "é" in first["description"]
    assert "é" in format_json(COURSES)  # ensure_ascii=False
    assert format_json([]) == "[]"


def test_csv_has_header_and_flattened_details():
    rows = list(csv.reader(io.StringIO(format_csv(COURSES))))
    assert rows[0] == list(CSV_COLUMNS)
    assert len(rows) == 3
    first = dict(zip(CSV_COLUMNS, rows[1]))
    assert first["code"] == "CSC108H1"
    assert first["details"] == 'Hours: 24L/12T | Exclusion: CSC148H1, "quoted"'
    assert first["score"] == "60"
    assert "Second paragraph" in first["description"]
    second = dict(zip(CSV_COLUMNS, rows[2]))
    assert second["details"] == ""
    assert second["description"] == ""


def test_csv_with_no_courses_is_header_only():
    assert format_csv([]).strip() == ",".join(CSV_COLUMNS)


def test_format_details():
    assert format_details({}) == ""
    assert format_details({"A": "1", "B": "2"}) == "A: 1 | B: 2"


@pytest.mark.parametrize("fmt", ["table", "json", "csv"])
def test_format_courses_dispatch(fmt):
    assert "CSC108H1" in format_courses(COURSES, fmt)


def test_format_courses_unknown_format():
    with pytest.raises(ValueError, match="unknown format"):
        format_courses(COURSES, "xml")
