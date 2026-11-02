"""End-to-end CLI tests with the network replaced by fixture pages."""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys

import pytest

from uoft_course_finder import __version__
from uoft_course_finder.cli import (
    EXIT_ALL_FAILED,
    EXIT_OK,
    EXIT_PARTIAL,
    EXIT_USAGE,
    main,
    parse_args,
)
from uoft_course_finder.httpclient import FetchError

from .conftest import FakeFetcher

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(argv, fetcher, patch_fetch):
    patch_fetch(fetcher)
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


# --- argument parsing -------------------------------------------------------


def test_defaults():
    args = parse_args(["algorithm"])
    assert args.keyword == "algorithm"
    assert args.campus is None
    assert args.limit is None
    assert args.format == "table"
    assert args.allow_insecure_ssl is False
    assert args.timeout == 30
    assert args.max_pages == 5


def test_multi_word_keyword_is_joined_either_way():
    assert parse_args(["machine", "learning"]).keyword == "machine learning"
    assert parse_args(["machine learning"]).keyword == "machine learning"


def test_campus_repeatable_and_short_flags():
    args = parse_args(["x", "--campus", "utm", "-c", "utsc", "-n", "5", "-f", "json"])
    assert args.campus == ["utm", "utsc"]
    assert args.limit == 5
    assert args.format == "json"


def test_allow_insecure_ssl_and_timeout_flags():
    args = parse_args(["x", "--allow-insecure-ssl", "--timeout", "2.5", "--max-pages", "1"])
    assert args.allow_insecure_ssl is True
    assert args.timeout == 2.5
    assert args.max_pages == 1


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["x", "--campus", "mississauga"],
        ["x", "--format", "xml"],
        ["x", "-n", "-1"],
        ["x", "-n", "five"],
        ["x", "--max-pages", "0"],
        ["x", "--timeout", "0"],
        ["   "],
    ],
)
def test_usage_errors_exit_2(argv, capsys):
    with pytest.raises(SystemExit) as excinfo:
        parse_args(argv)
    assert excinfo.value.code == EXIT_USAGE
    assert "usage:" in capsys.readouterr().err


def test_version(capsys):
    with pytest.raises(SystemExit) as excinfo:
        parse_args(["--version"])
    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out


# --- main() -----------------------------------------------------------------


def test_table_output_all_campuses(fake_fetcher, patch_fetch):
    code, out, err = run(["algorithm"], fake_fetcher, patch_fetch)
    assert code == EXIT_OK
    assert err == ""
    lines = out.splitlines()
    assert lines[0].startswith("Campus")
    assert len(lines) == 2 + 9
    # Algorithm Design and Analysis (UTM) carries the keyword in its title.
    assert "CSC373H5" in lines[2]
    assert any("UTSG Arts & Science" in line for line in lines)


def test_limit_and_campus_filter(fake_fetcher, patch_fetch):
    code, out, _ = run(["algorithm", "--campus", "utsc", "-n", "2"], fake_fetcher, patch_fetch)
    assert code == EXIT_OK
    lines = out.splitlines()
    assert len(lines) == 4
    assert all(line.startswith("UTSC") for line in lines[2:])
    assert all("utsc" in url for url in fake_fetcher.urls)


def test_json_output(fake_fetcher, patch_fetch):
    argv = ["geography", "--campus", "artsci", "--format", "json"]
    code, out, _ = run(argv, fake_fetcher, patch_fetch)
    assert code == EXIT_OK
    data = json.loads(out)
    # "Geography of Canada" matches in the title; the other two tie on a
    # single description hit and fall back to course-code order.
    assert [c["code"] for c in data] == ["GGR246H1", "AMS320H1", "GGR107H1"]
    assert data[0]["details"]["Hours"] == "24L"
    assert data[0]["score"] > data[1]["score"] == data[2]["score"] > 0


def test_csv_output(fake_fetcher, patch_fetch):
    code, out, _ = run(["algorithm", "-c", "utm", "-f", "csv"], fake_fetcher, patch_fetch)
    assert code == EXIT_OK
    rows = list(csv.reader(io.StringIO(out)))
    assert rows[0][:3] == ["campus", "code", "title"]
    assert len(rows) == 4
    assert {row[0] for row in rows[1:]} == {"utm"}


def test_options_reach_the_fetcher(fake_fetcher, patch_fetch):
    run(["x", "-c", "utm", "--allow-insecure-ssl", "--timeout", "3"], fake_fetcher, patch_fetch)
    (call,) = fake_fetcher.calls
    assert call["allow_insecure_ssl"] is True
    assert call["timeout"] == 3


def test_max_pages_caps_pagination(pages, patch_fetch):
    fetcher = FakeFetcher({"artsci": pages["artsci"]})  # always has a next link
    code, _, _ = run(["geography", "-c", "artsci", "--max-pages", "2"], fetcher, patch_fetch)
    assert code == EXIT_OK
    assert len(fetcher.calls) == 2


def test_one_campus_down_reports_error_and_returns_others(pages, patch_fetch):
    fetcher = FakeFetcher(
        {
            "page=1": pages["empty"],
            "artsci": pages["artsci"],
            "utm": FetchError("timed out fetching https://utm.calendar.utoronto.ca/course-search"),
            "utsc": pages["utsc"],
        }
    )
    code, out, err = run(["algorithm", "--format", "json"], fetcher, patch_fetch)
    assert code == EXIT_PARTIAL
    assert err.splitlines() == [
        "error: UTM (utm): timed out fetching https://utm.calendar.utoronto.ca/course-search"
    ]
    assert sorted({c["campus"] for c in json.loads(out)}) == ["artsci", "utsc"]


def test_every_campus_down_exits_1_with_no_output(patch_fetch):
    fetcher = FakeFetcher(
        {
            "artsci": FetchError("could not connect to artsci"),
            "utm": FetchError("could not connect to utm"),
            "utsc": FetchError("HTTP 503 Service Unavailable for utsc"),
        }
    )
    code, out, err = run(["algorithm"], fetcher, patch_fetch)
    assert code == EXIT_ALL_FAILED
    assert out == ""
    assert "UTSG Arts & Science (artsci): could not connect to artsci" in err
    assert "UTM (utm): could not connect to utm" in err
    assert "UTSC (utsc): HTTP 503" in err
    assert err.strip().endswith("every campus failed; no results available")


def test_selected_campus_down_exits_1(patch_fetch, pages):
    fetcher = FakeFetcher({"utm": FetchError("nope"), "utsc": pages["utsc"]})
    code, out, _ = run(["x", "-c", "utm"], fetcher, patch_fetch)
    assert code == EXIT_ALL_FAILED
    assert out == ""


def test_no_matches_exits_0_with_note(pages, patch_fetch):
    fetcher = FakeFetcher({"calendar.utoronto.ca": pages["empty"]})
    code, out, err = run(["zzqqxxyy"], fetcher, patch_fetch)
    assert code == EXIT_OK
    assert "No courses found for 'zzqqxxyy'." in err
    assert out.splitlines()[0].startswith("Campus")
    code, out, _ = run(["zzqqxxyy", "-f", "json"], fetcher, patch_fetch)
    assert json.loads(out) == []


def test_site_layout_change_is_reported_per_campus(pages, patch_fetch):
    fetcher = FakeFetcher(
        {"artsci": "<html><body>new site</body></html>", "utm": pages["utm"], "utsc": pages["utsc"]}
    )
    code, _, err = run(["algorithm"], fetcher, patch_fetch)
    assert code == EXIT_PARTIAL
    assert "UTSG Arts & Science (artsci)" in err
    assert "calendar site may have changed" in err


# --- entry points (no network) ---------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        [sys.executable, "uoft_course_finder.py"],
        [sys.executable, "-m", "uoft_course_finder"],
    ],
)
def test_entry_points_run_offline(command):
    proc = subprocess.run(
        [*command, "--version"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == f"uoft-course-finder {__version__}"

    proc = subprocess.run([*command], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == EXIT_USAGE
    assert "usage: uoft-course-finder" in proc.stderr
