"""Keyword scoring and ranking tests."""

from __future__ import annotations

from uoft_course_finder.matching import rank, score_course
from uoft_course_finder.models import Course


def make(code="CSC108H1", title="", description="", details=None, campus="artsci"):
    return Course(
        campus=campus,
        code=code,
        title=title,
        url=f"https://example.test/course/{code}",
        description=description,
        details=details or {},
    )


def test_matching_is_case_insensitive():
    course = make(title="Introduction to ALGORITHMS", description="Covers Algorithm design.")
    assert score_course(course, "algorithm") == score_course(course, "ALGORITHM")
    assert score_course(course, "AlGoRiThM") > 0


def test_multi_word_phrase_matches_as_a_phrase():
    phrase = make(title="Machine Learning", description="Intro to machine learning.")
    scattered = make(title="Learning Theory", description="A machine for thinking.")
    assert score_course(phrase, "machine learning") > score_course(scattered, "machine learning")
    # Scattered words still get a small partial credit rather than zero.
    assert score_course(scattered, "machine learning") > 0
    assert score_course(scattered, "  Machine   Learning ") == score_course(
        scattered, "machine learning"
    )


def test_title_match_outranks_description_match():
    in_title = make(code="AAA100H1", title="Geography of Canada", description="")
    in_text = make(code="BBB100H1", title="Canada", description="A geography course.")
    assert score_course(in_title, "geography") > score_course(in_text, "geography")


def test_code_match_scores_highest():
    course = make(code="GGR246H1", title="Canada")
    assert score_course(course, "ggr246") >= 100


def test_description_hits_are_capped():
    spam = make(description="algorithm " * 50)
    modest = make(description="algorithm algorithm")
    assert score_course(spam, "algorithm") == 50
    assert score_course(modest, "algorithm") == 20


def test_details_contribute_with_cap():
    course = make(details={"Prerequisite": "data data data data data data"})
    assert score_course(course, "data") == 20


def test_aliases_boost_related_courses():
    course = make(title="Data Structures and Analysis", description="Complexity of programs.")
    # "data structures" also contains "data structure", so both aliases hit.
    assert score_course(course, "algorithm") == 25 + 25 + 15
    assert score_course(course, "algorithms") == score_course(course, "algorithm")
    unrelated = make(title="Pottery", description="Clay.")
    assert score_course(unrelated, "algorithm") == 0


def test_empty_keyword_scores_zero():
    assert score_course(make(title="anything"), "   ") == 0


def test_rank_orders_by_score_then_campus_then_code():
    courses = [
        make(code="ZZZ100H1", title="Nothing here", campus="utsc"),
        make(code="CSC373H5", title="Algorithm Design", campus="utm"),
        make(code="CSC373H1", title="Algorithm Design", campus="artsci"),
        make(code="AAA100H1", title="Nothing here", campus="artsci"),
        make(code="MAT100H1", description="an algorithm", campus="artsci"),
    ]
    ranked = rank(courses, "algorithm")
    assert [c.code for c in ranked] == ["CSC373H1", "CSC373H5", "MAT100H1", "AAA100H1", "ZZZ100H1"]
    assert ranked[0].score == 60
    assert ranked[-1].score == 0


def test_rank_keeps_zero_score_courses():
    """The server already matched the keyword; local scoring only orders."""
    ranked = rank([make(title="Unrelated")], "algorithm")
    assert len(ranked) == 1


def test_rank_limit():
    courses = [make(code=f"AAA10{i}H1", title="algorithm") for i in range(5)]
    assert len(rank(courses, "algorithm", limit=2)) == 2
    assert len(rank(courses, "algorithm", limit=0)) == 0
    assert len(rank(courses, "algorithm", limit=None)) == 5
    assert len(rank(courses, "algorithm", limit=99)) == 5
