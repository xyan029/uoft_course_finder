"""Scraper orchestration: pagination, per-campus isolation, campus selection."""

from __future__ import annotations

import pytest

from uoft_course_finder.calendars import ALL_CAMPUSES, CALENDARS
from uoft_course_finder.httpclient import FetchError
from uoft_course_finder.models import CampusError
from uoft_course_finder.scrapers import resolve_campuses, search, search_campus

from .conftest import FakeFetcher


def test_search_campus_follows_next_page_and_deduplicates(pages):
    artsci = CALENDARS["artsci"]
    # Page 0 and page 1 return the same fixture; page 1 still has a "next"
    # link, so the cap on pages must stop the loop.
    fetcher = FakeFetcher({artsci.base_url: pages["artsci"]})
    courses = search_campus(artsci, "geography", fetcher=fetcher, max_pages=3)
    assert [c.code for c in courses] == ["AMS320H1", "GGR107H1", "GGR246H1"]
    assert fetcher.urls == [
        "https://artsci.calendar.utoronto.ca/search-courses?course_keyword=geography",
        "https://artsci.calendar.utoronto.ca/search-courses?course_keyword=geography&page=1",
        "https://artsci.calendar.utoronto.ca/search-courses?course_keyword=geography&page=1",
    ]


def test_search_campus_stops_when_no_next_link(pages):
    utm = CALENDARS["utm"]
    fetcher = FakeFetcher({utm.base_url: pages["utm"]})
    courses = search_campus(utm, "algorithm", fetcher=fetcher)
    assert len(courses) == 3
    assert fetcher.urls == [
        "https://utm.calendar.utoronto.ca/course-search?course_keyword=algorithm"
    ]


def test_search_campus_passes_options_to_fetcher(pages):
    utsc = CALENDARS["utsc"]
    fetcher = FakeFetcher({utsc.base_url: pages["utsc"]})
    search_campus(utsc, "machine learning", fetcher=fetcher, timeout=4, allow_insecure_ssl=True)
    (call,) = fetcher.calls
    assert call["url"].endswith("course_keyword=machine+learning")
    assert call["timeout"] == 4
    assert call["allow_insecure_ssl"] is True


def test_search_campus_wraps_fetch_error():
    cause = FetchError("timed out fetching https://utm.calendar.utoronto.ca/...")
    fetcher = FakeFetcher({"utm": cause})
    with pytest.raises(CampusError) as excinfo:
        search_campus(CALENDARS["utm"], "x", fetcher=fetcher)
    assert excinfo.value.campus == "utm"
    assert excinfo.value.__cause__ is cause
    assert str(excinfo.value) == "utm: timed out fetching https://utm.calendar.utoronto.ca/..."


def test_search_campus_wraps_parse_error():
    fetcher = FakeFetcher({"utsc": "<html><body>Site redesigned</body></html>"})
    with pytest.raises(CampusError, match="may have changed"):
        search_campus(CALENDARS["utsc"], "x", fetcher=fetcher)


def test_search_all_campuses(fake_fetcher):
    result = search("algorithm", fetcher=fake_fetcher)
    assert result.ok and not result.partial
    assert [c.campus for c in result.courses] == ["artsci"] * 3 + ["utm"] * 3 + ["utsc"] * 3


def test_search_one_failure_keeps_other_campuses(pages):
    fetcher = FakeFetcher(
        {
            "page=1": pages["empty"],
            "artsci": pages["artsci"],
            "utm": FetchError("could not connect to https://utm.calendar.utoronto.ca/..."),
            "utsc": pages["utsc"],
        }
    )
    result = search("algorithm", fetcher=fetcher)
    assert result.partial and not result.ok
    assert sorted({c.campus for c in result.courses}) == ["artsci", "utsc"]
    assert [e.campus for e in result.errors] == ["utm"]


def test_search_unexpected_exception_becomes_campus_error(pages):
    fetcher = FakeFetcher({"utm": RuntimeError("kaboom"), "utsc": pages["utsc"]})
    result = search("x", ["utm", "utsc"], fetcher=fetcher)
    (error,) = result.errors
    assert error.campus == "utm"
    assert "RuntimeError: kaboom" in error.message
    assert isinstance(error.__cause__, RuntimeError)
    assert len(result.courses) == 3


def test_search_selected_campus_only(fake_fetcher):
    result = search("algorithm", ["utsc"], fetcher=fake_fetcher)
    assert {c.campus for c in result.courses} == {"utsc"}
    assert all("utsc" in url for url in fake_fetcher.urls)


def test_resolve_campuses():
    assert [c.key for c in resolve_campuses(None)] == list(ALL_CAMPUSES)
    assert [c.key for c in resolve_campuses([])] == list(ALL_CAMPUSES)
    assert [c.key for c in resolve_campuses(["all"])] == list(ALL_CAMPUSES)
    assert [c.key for c in resolve_campuses(["UTM", "utm", "artsci"])] == ["utm", "artsci"]
    assert [c.key for c in resolve_campuses(["utsc", "all"])] == ["utsc", "artsci", "utm"]
    with pytest.raises(ValueError, match="unknown campus 'mississauga'"):
        resolve_campuses(["mississauga"])


def test_build_search_url_encodes_keyword_and_page():
    utm = CALENDARS["utm"]
    assert utm.build_search_url("machine learning") == (
        "https://utm.calendar.utoronto.ca/course-search?course_keyword=machine+learning"
    )
    assert utm.build_search_url("a&b", page=2).endswith("course_keyword=a%26b&page=2")
