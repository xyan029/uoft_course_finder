"""Offline parsing tests against the trimmed fixtures for every campus."""

from __future__ import annotations

import pytest

from uoft_course_finder.calendars import CALENDARS
from uoft_course_finder.parser import (
    ParseError,
    find_next_page,
    parse_results,
    split_heading,
    strip_tags,
)


def test_artsci_fixture_parses_three_courses(pages):
    courses = parse_results(pages["artsci"], CALENDARS["artsci"])
    assert [c.code for c in courses] == ["AMS320H1", "GGR107H1", "GGR246H1"]
    assert all(c.campus == "artsci" for c in courses)
    ggr = courses[2]
    assert ggr.title == "Geography of Canada"
    assert ggr.url == "https://artsci.calendar.utoronto.ca/course/GGR246H1"
    assert ggr.description.startswith("Social and economic differences")
    assert ggr.details["Hours"] == "24L"
    assert ggr.details["Exclusion"] == "GGR202H5"
    assert ggr.details["Breadth Requirements"] == "Society and its Institutions (3)"
    assert "GGR107H1" in ggr.details["Recommended Preparation"]


def test_artsci_truncated_aria_label_uses_visible_heading(pages):
    """The site emits aria-label=" Controversies in Public Memory" for AMS320H1."""
    ams = parse_results(pages["artsci"], CALENDARS["artsci"])[0]
    assert ams.code == "AMS320H1"
    assert ams.title == "Tearing Down Monuments: Controversies in Public Memory"
    assert ams.details["Previous Course Number"] == "AMS199H1"
    assert ams.details["Prerequisite"] == "6.0 credits"


def test_utm_fixture_parses_bullet_separated_headings(pages):
    courses = parse_results(pages["utm"], CALENDARS["utm"])
    assert [c.code for c in courses] == ["CSC104H5", "CSC263H5", "CSC373H5"]
    assert [c.title for c in courses] == [
        "The Why and How of Computing",
        "Data Structures and Analysis",
        "Algorithm Design and Analysis",
    ]
    csc373 = courses[2]
    assert csc373.url == "https://utm.calendar.utoronto.ca/course/CSC373H5"
    assert csc373.description.startswith("Standard algorithm design techniques")
    assert csc373.details["Prerequisites"] == "CSC263H5"
    assert csc373.details["Exclusions"] == "CSC373H1 or CSC375H1 or CSCC73H3"
    assert csc373.details["Total Instructional Hours"] == "24L/12T"
    assert csc373.details["Mode of Delivery"] == "In Class, Hybrid"
    assert csc373.details["Distribution Requirement"] == "Science"
    # The empty "nothing-1" spacer field must not leak into details.
    assert not any(key.lower().startswith("nothing") for key in csc373.details)


def test_utsc_fixture_parses_timetable_link(pages):
    courses = parse_results(pages["utsc"], CALENDARS["utsc"])
    assert [c.code for c in courses] == ["CSCB36H3", "CSCC11H3", "CSCC37H3"]
    cscc11 = courses[1]
    assert cscc11.title == "Introduction to Machine Learning and Data Mining"
    assert cscc11.details["Timetable"] == "https://ttb.utoronto.ca/cp/CSCC11H3"
    assert cscc11.details["Breadth Requirements"] == "Quantitative Reasoning"
    assert cscc11.details["Recommended Preparation"] == "CSCC37H3 , STAB57H3"
    assert "(CSC311H5)" in cscc11.details["Exclusion"]


@pytest.mark.parametrize("campus", ["artsci", "utm", "utsc"])
def test_every_course_has_text_and_no_markup(pages, campus):
    for course in parse_results(pages[campus], CALENDARS[campus]):
        assert course.code and course.title and course.description
        for value in (course.title, course.description, *course.details.values()):
            assert "<" not in value and ">" not in value
            assert "&amp;" not in value


def test_empty_result_page_parses_to_no_courses(pages):
    assert parse_results(pages["empty"], CALENDARS["artsci"]) == []


def test_unrecognised_page_raises_parse_error():
    with pytest.raises(ParseError, match="unexpected layout"):
        parse_results("<html><body><h1>Maintenance</h1></body></html>", CALENDARS["utm"])


def test_non_course_heading_with_shared_class_is_skipped():
    page = (
        '<div class="view-content">'
        '<h3 class="js-views-accordion-group-header">Filter results</h3>'
        '<div class="views-row"><h3 class="js-views-accordion-group-header">'
        '<div aria-label="CSC108H1 - Intro">CSC108H1 - Intro</div></h3>'
        '<div class="views-row"><div class="views-field views-field-body">'
        '<div class="field-content"><p>Hello &amp; welcome</p></div></div></div></div>'
        "</div>"
    )
    courses = parse_results(page, CALENDARS["artsci"])
    assert [(c.code, c.title, c.description) for c in courses] == [
        ("CSC108H1", "Intro", "Hello & welcome")
    ]


def test_heading_without_visible_code_falls_back_to_aria_label():
    page = (
        '<div class="view-content"><h3 class="js-views-accordion-group-header">'
        '<div aria-label="MAT137Y1 - Calculus with Proofs"><img alt=""></div></h3></div>'
    )
    (course,) = parse_results(page, CALENDARS["artsci"])
    assert (course.code, course.title) == ("MAT137Y1", "Calculus with Proofs")


def test_pager_text_does_not_leak_into_last_course(pages):
    last = parse_results(pages["artsci"], CALENDARS["artsci"])[-1]
    joined = " ".join([last.description, *last.details.values()])
    assert "Pagination" not in joined
    assert "Next page" not in joined


def test_find_next_page_resolves_relative_link(pages):
    url = CALENDARS["artsci"].build_search_url("geography")
    assert find_next_page(pages["artsci"], url) == (
        "https://artsci.calendar.utoronto.ca/search-courses?course_keyword=geography&page=1"
    )


@pytest.mark.parametrize("campus", ["utm", "utsc", "empty"])
def test_find_next_page_is_none_without_pager(pages, campus):
    assert find_next_page(pages[campus], "https://example.test/search") is None


def test_find_next_page_without_href():
    assert find_next_page('<a rel="next">next</a>', "https://example.test/") is None


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("CSC108H1 - Introduction to Programming", ("CSC108H1", "Introduction to Programming")),
        ("  CSC104H5 • The Why and How ", ("CSC104H5", "The Why and How")),
        ("CSCB36H3 - Theory", ("CSCB36H3", "Theory")),
        ("MAT137Y1: Calculus", ("MAT137Y1", "Calculus")),
        ("Primate Ecology &amp; Social Behavior", ("", "Primate Ecology & Social Behavior")),
        ("Weird ANT436H1 Order", ("ANT436H1", "Weird Order")),
    ],
)
def test_split_heading(heading, expected):
    assert split_heading(heading) == expected


def test_strip_tags_handles_breaks_entities_and_scripts():
    fragment = (
        "<p>First&nbsp;line<br/>Second line</p><script>evil()</script>"
        "<style>p{}</style><div>Third &amp; last</div>"
    )
    assert strip_tags(fragment) == "First line\nSecond line\nThird & last"
