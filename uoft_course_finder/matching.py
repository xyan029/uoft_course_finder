"""Rank scraped courses by how well they match the search keyword.

The calendar sites already filter server-side, so nothing is discarded here.
Scoring only decides the order: courses whose code or title contains the
phrase come first, then those that mention it in the description, then the
rest in code order.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .calendars import ALL_CAMPUSES
from .models import Course

CODE_WEIGHT = 100
TITLE_WEIGHT = 60
DESCRIPTION_WEIGHT = 10
DESCRIPTION_CAP = 50
DETAILS_WEIGHT = 5
DETAILS_CAP = 20
PARTIAL_WORD_WEIGHT = 3

# Phrases that commonly describe the same topic as a keyword. Each hit adds
# its weight once; useful because calendars vary in vocabulary.
KEYWORD_ALIASES: Dict[str, Sequence[Tuple[str, int]]] = {
    "algorithm": (
        ("data structures", 25),
        ("data structure", 25),
        ("complexity", 15),
        ("abstract data types", 15),
    ),
    "ai": (("artificial intelligence", 80), ("machine learning", 35)),
    "nlp": (("natural language processing", 80), ("language", 10)),
    "ml": (("machine learning", 80),),
}
KEYWORD_ALIASES["algorithms"] = KEYWORD_ALIASES["algorithm"]


def normalize_keyword(keyword: str) -> str:
    return re.sub(r"\s+", " ", keyword).strip().lower()


def _count(phrase: str, text: str) -> int:
    return text.count(phrase) if phrase else 0


def score_course(course: Course, keyword: str) -> int:
    """Return a non-negative relevance score for ``course``."""
    phrase = normalize_keyword(keyword)
    if not phrase:
        return 0

    code = course.code.lower()
    title = normalize_keyword(course.title)
    description = normalize_keyword(course.description)
    details = normalize_keyword(" ".join(f"{k} {v}" for k, v in course.details.items()))

    score = 0
    if phrase in code:
        score += CODE_WEIGHT
    if phrase in title:
        score += TITLE_WEIGHT
    score += min(_count(phrase, description) * DESCRIPTION_WEIGHT, DESCRIPTION_CAP)
    score += min(_count(phrase, details) * DETAILS_WEIGHT, DETAILS_CAP)

    words = phrase.split()
    if len(words) > 1 and score == 0:
        everything = " ".join((code, title, description, details))
        score += PARTIAL_WORD_WEIGHT * sum(1 for word in words if word in everything)

    everything = " ".join((title, description, details))
    for alias, weight in KEYWORD_ALIASES.get(phrase, ()):
        if alias in everything:
            score += weight
    return score


def rank(courses: Iterable[Course], keyword: str, limit: Optional[int] = None) -> List[Course]:
    """Score, sort and optionally truncate ``courses``.

    Sorting is stable and deterministic: score descending, then campus in
    calendar order, then course code.
    """
    campus_order = {campus: index for index, campus in enumerate(ALL_CAMPUSES)}
    scored: List[Course] = []
    for course in courses:
        course.score = score_course(course, keyword)
        scored.append(course)
    scored.sort(key=lambda c: (-c.score, campus_order.get(c.campus, len(campus_order)), c.code))
    if limit is not None and limit >= 0:
        scored = scored[:limit]
    return scored
