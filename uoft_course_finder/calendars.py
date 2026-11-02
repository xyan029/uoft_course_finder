"""Static configuration for the three official U of T academic calendars."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from urllib.parse import urlencode


@dataclass(frozen=True)
class Calendar:
    """One campus calendar site and how to query its course search."""

    key: str
    name: str
    base_url: str
    search_path: str
    keyword_param: str = "course_keyword"

    @property
    def search_url(self) -> str:
        return self.base_url + self.search_path

    def build_search_url(self, keyword: str, page: int = 0) -> str:
        """Return the absolute URL for ``keyword`` on zero-based ``page``."""
        params = {self.keyword_param: keyword}
        if page:
            params["page"] = str(page)
        return f"{self.search_url}?{urlencode(params)}"


CALENDARS: Dict[str, Calendar] = {
    "artsci": Calendar(
        key="artsci",
        name="UTSG Arts & Science",
        base_url="https://artsci.calendar.utoronto.ca",
        search_path="/search-courses",
    ),
    "utm": Calendar(
        key="utm",
        name="UTM",
        base_url="https://utm.calendar.utoronto.ca",
        search_path="/course-search",
    ),
    "utsc": Calendar(
        key="utsc",
        name="UTSC",
        base_url="https://utsc.calendar.utoronto.ca",
        search_path="/search-courses",
    ),
}

ALL_CAMPUSES = tuple(CALENDARS)
